"""JSON API blueprint for the new web interface.

All endpoints live under /api/ and return plain JSON (no HTML fragments,
unlike the legacy routes in interface.py). The blueprint is created via
create_blueprint() so interface.py can inject its requires_auth decorator
without a circular import.
"""

import base64
import hashlib
import math
import os
import time

from flask import Blueprint, Response, abort, jsonify, request, send_file

import media.playlist
import util
import variables as var
import web_context
import web_search
from media import artwork, lyrics
from media.cache import get_cached_wrapper_from_scrap
from web_users import current_user_name, requester_display_name


def _current_wrapper():
    if len(web_context.playlist()) == 0:
        return None
    wrapper = web_context.playlist().current_item()
    return wrapper or None


def _item_summary(wrapper, index):
    item = wrapper.item()
    summary = {
        'id': item.id,
        'index': index,
        'type': item.display_type(),
        'title': item.format_title(),
        'artist': getattr(item, 'artist', '') or '',
        'url': getattr(item, 'url', '') or '',
        'duration': getattr(item, 'duration', 0) or 0,
        'has_thumbnail': bool(getattr(item, 'thumbnail', None)) or artwork.has_hd(item.id),
        # 封面来源(album / video / embedded / ''),变了说明高清图换了,前端据此刷新图片
        'artwork': getattr(item, 'artwork', '') or '',
        'album': getattr(item, 'album', '') or '',
        # 匹配到专辑时曲库里的正式歌名(没有就是 ''),播放页用它代替视频标题
        'track': getattr(item, 'track', '') or '',
        # 点歌人:网页点的是 Web 显示名,聊天点的绑定了就换成 Web 显示名、否则是 Discord 名
        'requester': requester_display_name(getattr(wrapper, 'user', '') or ''),
    }
    if getattr(item, 'downloading', False):
        # 后台下载中(预下载/边下边播):队列里显示进度,播放条上画"已缓冲"部分
        summary['download'] = {
            'progress': round(getattr(item, 'progress', 0.0) or 0.0, 4),
            'speed': round(getattr(item, 'speed', 0.0) or 0.0),
            'eta': getattr(item, 'download_eta', None),
            'stage': getattr(item, 'stage', ''),
        }
    return summary


def _voice_channel(bot):
    try:
        cid = bot.my_channel_id()
        if cid is None:
            return None
        return {'id': str(cid), 'name': bot.channel_display_name(cid)}
    except Exception:
        return None


def _status_payload():
    bot = web_context.session()
    current = _current_wrapper()
    payload = {
        'version': web_context.playlist().version,
        'empty': current is None,
        'play': not bot.is_pause,
        'mode': web_context.playlist().mode,
        'volume': bot.volume_helper.plain_volume_set,
        # bot 所在的语音频道;None = 不在语音里(网页上提示去 Settings 选一个)
        'voice_channel': _voice_channel(bot),
        'playhead': bot.playhead if current is not None else 0,
        'queue_length': len(web_context.playlist()),
        'current_index': web_context.playlist().current_index,
        'server_time': time.time(),
        'current': None,
        'prep': None,
    }
    if current is not None:
        try:
            payload['current'] = _item_summary(
                current, web_context.playlist().current_index)
            # 正在播放的那首优先准备封面(已经有了就是一次文件检查)
            artwork.ensure(current.item(), urgent=True)
            # 歌词状态(off / waiting / pending / found / none / instrumental),found 时前端再来取
            lyrics.ensure(current.item(), urgent=True)
            payload['current']['lyrics'] = lyrics.status(current.item())
            # SponsorBlock 要跳过的片段,前端在进度条上标出来
            skip_for = getattr(bot, 'skip_segments_for', None)
            payload['current']['skip_segments'] = skip_for(current.id) if skip_for else []
            # 还没出声:告诉前端在等什么、还要多久
            waiting = getattr(bot, 'is_waiting_for', None)
            if waiting and waiting(current.id):
                payload['prep'] = bot.prep_status(current)
        except Exception:
            # an item mid-eviction must not break the poll
            payload['current'] = None
    return payload


# 其他蓝图(web_users)复用
status_payload = _status_payload


def _max_volume(session):
    """这个服务器的最大音量(0..1):管理员设过的(/maxvolume 或 Web)优先,否则配置文件的。"""
    limit = 1.0
    if var.config is not None:
        limit = var.config.getfloat('bot', 'max_volume', fallback=1.0)
    setting = getattr(session, 'setting', None)
    if setting is not None:
        try:
            saved = setting('max_volume')
            if saved is not None:
                limit = float(saved)
        except (TypeError, ValueError):
            pass
    return max(0.0, min(1.0, limit))


def _set_volume(value):
    session = web_context.session()
    value = max(0.0, min(_max_volume(session), round(float(value), 2)))
    session.volume_helper.set_volume(value)
    session.save_setting('volume', str(session.volume_helper.plain_volume_set))


def _set_mode(mode):
    """Same semantics as the legacy /post 'action' mode switches."""
    if mode not in ('one-shot', 'repeat', 'single', 'random', 'autoplay'):
        abort(400)
    if mode == 'random':
        if web_context.playlist().mode != 'random':
            web_context.set_playlist(media.playlist.get_playlist('random', web_context.playlist()))
        else:
            web_context.playlist().randomize()
        web_context.session().interrupt()
    else:
        web_context.set_playlist(media.playlist.get_playlist(mode, web_context.playlist()))
    web_context.session().save_setting('playback_mode', mode)


def _mark_current_skipped():
    if var.play_history is None:
        return
    try:
        current = web_context.playlist().current_item()
        if current and not web_context.session().is_pause:
            var.play_history.mark_skipped(current.id, web_context.session().guild_id or None)
    except Exception:
        pass


def _skip():
    """Same semantics as the legacy /post action=next."""
    _mark_current_skipped()
    web_context.playlist().skip_current()  # in single-loop mode, break out for one step
    if not web_context.session().is_pause:
        web_context.session().interrupt()
    else:
        web_context.playlist().next()
        web_context.session().wait_for_ready = True


def _stop():
    if var.config.getboolean('bot', 'clear_when_stop_in_oneshot') \
            and web_context.playlist().mode == 'one-shot':
        web_context.session().clear()
    else:
        web_context.session().stop()


def _queue_move(src, dst):
    playlist = web_context.playlist()
    with playlist.playlist_lock:
        n = len(playlist)
        if not (0 <= src < n and 0 <= dst < n):
            abort(400)
        if src == dst:
            return
        wrapper = list.pop(playlist, src)
        list.insert(playlist, dst, wrapper)
        _leave_group_if_detached(playlist, dst)
        ci = playlist.current_index
        if src == ci:
            playlist.current_index = dst
        elif src < ci <= dst:
            playlist.current_index = ci - 1
        elif dst <= ci < src:
            playlist.current_index = ci + 1
        playlist.version += 1


def _group_key(wrapper):
    return (getattr(wrapper, 'group', None) or {}).get('key')


def _leave_group_if_detached(playlist, index):
    """单曲被拖出了它所在的歌单(前后都不是同组):不再算这组的,单独显示。"""
    key = _group_key(playlist[index])
    if not key:
        return
    neighbours = [playlist[i] for i in (index - 1, index + 1) if 0 <= i < len(playlist)]
    if not any(_group_key(w) == key for w in neighbours):
        playlist[index].group = None


def _queue_remove(index):
    """Remove the index-th queue item; shared with /remove and the legacy /post."""
    playlist = web_context.playlist()
    if not (0 <= index < len(playlist)):
        abort(400)
    web_context.session().remove_from_queue(index)


def _search_result_url(source, url, video_id=None):
    """搜索结果 -> 真正入队用的链接(B 站统一成 av 号链接,和其他入口一致)。"""
    url = (url or '').strip()
    if source == 'bilibili':
        url = util.get_bilibili_url_from_input(video_id or url)
    return url


def _search_item_id(result):
    try:
        url = _search_result_url(result.get('source'), result.get('url'), result.get('id'))
    except Exception:
        return ''
    return hashlib.md5(url.encode()).hexdigest() if url else ''


def _stats_scope():
    """统计哪个服务器:?guild=<id>,?guild=all 是全部(只有 bot 主人)。不给就是当前选的服务器。
    加 guild_id 列之前的旧记录只算给主服务器。没有 Hub 的单服务器旧模式统计全部(和以前一样)。"""
    hub = web_context.hub()
    wanted = (request.args.get('guild') or '').strip()
    if wanted == 'all':
        if hub is not None and not web_context.is_owner():
            abort(403)
        return {}
    if hub is None:
        return {}
    if wanted:
        # 统计页自己的筛选优先于请求头里选的服务器
        if not wanted.isdigit() or not web_context.access().allows(wanted):
            abort(403)
        gid = wanted
    else:
        gid = web_context.guild_id()
    home = str(hub.home_guild_id or '')
    return {'guild_id': gid, 'include_unscoped': bool(home) and gid == home}


def create_blueprint(requires_auth):
    api = Blueprint('api', __name__, url_prefix='/api')

    @api.route('/status', methods=['GET'])
    @requires_auth
    def api_status():
        """Lightweight polling endpoint: everything the Now Playing screen
        needs except the thumbnail (fetched separately, keyed by item id,
        so polls stay small)."""
        return jsonify(_status_payload())

    @api.route('/controls', methods=['POST'])
    @requires_auth
    def api_controls():
        """Transport and bot controls. Body: {"action": ..., ...extras}.
        Mirrors the semantics of the legacy /post endpoint so both UIs
        behave identically."""
        payload = request.get_json(silent=True) or request.form
        action = payload.get('action') if payload else None
        if not action:
            abort(400)
        if action == 'pause':
            web_context.session().pause()
        elif action == 'resume':
            web_context.session().resume()
        elif action == 'skip':
            _skip()
        elif action == 'stop':
            _stop()
        elif action == 'clear':
            web_context.session().clear()
        elif action == 'mode':
            _set_mode(payload.get('mode'))
        elif action == 'volume':
            try:
                _set_volume(payload.get('volume'))
            except (TypeError, ValueError):
                abort(400)
        elif action == 'seek':
            try:
                position = float(payload.get('position'))
            except (TypeError, ValueError):
                abort(400)
            if not web_context.session().seek(position):
                abort(409)  # 没有在放 / 直播电台这类不能跳转的
        else:
            abort(400)
        return jsonify(_status_payload())

    @api.route('/queue', methods=['GET'])
    @requires_auth
    def api_queue():
        items = []
        with web_context.playlist().playlist_lock:
            wrappers = list(web_context.playlist())
            current_index = web_context.playlist().current_index
        for index, wrapper in enumerate(wrappers):
            try:
                summary = _item_summary(wrapper, index)
            except Exception:
                continue
            summary['is_current'] = index == current_index
            group = getattr(wrapper, 'group', None)
            summary['group'] = {'key': group.get('key'), 'name': group.get('name', ''),
                                'kind': group.get('kind', 'playlist')} if group else None
            items.append(summary)
        return jsonify({
            'items': items,
            'current_index': current_index,
            'version': web_context.playlist().version,
        })

    @api.route('/queue', methods=['POST'])
    @requires_auth
    def api_queue_edit():
        """Queue edits. Body: {"action": "move"|"top"|"remove"|"play"|"clear"|"remove_group",
        with "index" (and "to" for move, "group" for remove_group)}."""
        payload = request.get_json(silent=True) or request.form
        action = payload.get('action') if payload else None
        if not action:
            abort(400)
        try:
            index = int(payload.get('index', -1))
            to = int(payload.get('to', -1))
        except (TypeError, ValueError):
            abort(400)
        if action == 'move':
            _queue_move(index, to)
        elif action == 'top':
            # insert right after the currently playing item
            dst = min(max(web_context.playlist().current_index + 1, 0),
                      max(len(web_context.playlist()) - 1, 0))
            _queue_move(index, dst)
        elif action == 'remove':
            _queue_remove(index)
        elif action == 'play':
            if not (0 <= index < len(web_context.playlist())):
                abort(400)
            web_context.session().play(index)
        elif action == 'clear':
            web_context.session().clear()
        elif action == 'remove_group':
            key = str(payload.get('group') or '')
            if not key or not web_context.session().remove_group_from_queue(key):
                abort(400)
        else:
            abort(400)
        return jsonify(_status_payload())

    @api.route('/search', methods=['GET'])
    @requires_auth
    def api_search():
        query = (request.args.get('q') or '').strip()[:200]
        if len(query) < 2:
            abort(400)
        try:
            limit = min(12, max(1, int(request.args.get('limit', 6))))
        except (TypeError, ValueError):
            limit = 6
        results, failed = web_search.unified_search(query, limit)
        for result in results:
            # 和 /search/add 入队后的条目同一个 id,前端据此画收藏 ♥
            result['item_id'] = _search_item_id(result)
        return jsonify({'query': query, 'results': results, 'failed': failed})

    @api.route('/search/add', methods=['POST'])
    @requires_auth
    def api_search_add():
        """Add a search result to the queue. Bilibili results go through the
        av/BV normalization every other entry point uses."""
        payload = request.get_json(silent=True) or request.form
        if not payload:
            abort(400)
        url = _search_result_url(payload.get('source'), payload.get('url'), payload.get('id'))
        if not url or not url.lower().startswith(('http://', 'https://')):
            abort(400)
        music_wrapper = get_cached_wrapper_from_scrap(
            type='url', url=url, user=current_user_name())
        web_context.playlist().append(music_wrapper)
        if len(web_context.playlist()) == 2:
            # mirror the legacy add_url behavior: if this became the next
            # item, start downloading right away
            web_context.session().async_download_next()
        return jsonify(_status_payload())

    @api.route('/stats', methods=['GET'])
    @requires_auth
    def api_stats():
        if var.play_history is None:
            abort(503)
        stats = var.play_history.stats(**_stats_scope())
        if var.user_db is not None:
            # 绑定了 Discord 的人:聊天点歌(记的是 Discord 名)和网页点歌(记的是别名)合并成一行
            names = var.user_db.requester_display_names()
            merged = {}
            for row in stats.get('top_users', []):
                name = names.get(row['user'], row['user'])
                merged[name] = merged.get(name, 0) + row['count']
            stats['top_users'] = [{'user': u, 'count': c}
                                  for u, c in sorted(merged.items(), key=lambda kv: -kv[1])]
        return jsonify(stats)

    @api.route('/lyrics/<item_id>', methods=['GET'])
    @requires_auth
    def api_lyrics(item_id):
        """条目的歌词(media/lyrics.py)。还没查好时只有 status,前端看状态轮询里的
        current.lyrics 变成 found 再来取。"""
        item = var.cache.get_item_by_id(item_id)
        if item is None:
            abort(404)
        data = lyrics.get(item)
        if data is None:
            lyrics.ensure(item, urgent=True)
            return jsonify({'status': lyrics.status(item)})
        return jsonify(lyrics.to_json(data))

    @api.route('/lyrics/<item_id>/offset', methods=['POST'])
    @requires_auth
    def api_lyrics_offset(item_id):
        """手动调时间轴:offset 是条目时间比歌词时间晚多少秒,所有人共用。"""
        item = var.cache.get_item_by_id(item_id)
        payload = request.get_json(silent=True) or {}
        try:
            offset = float(payload.get('offset'))
        except (TypeError, ValueError):
            abort(400)
        if not math.isfinite(offset):
            abort(400)
        if item is None:
            abort(404)
        data = lyrics.set_offset(item, offset)
        if data is None:
            abort(409)
        return jsonify(lyrics.to_json(data))

    @api.route('/thumbnail/<item_id>', methods=['GET'])
    @requires_auth
    def api_thumbnail(item_id):
        """条目封面。默认给高清图(media/artwork.py 存的),还没准备好时先给 100px 的
        小图并在后台插队准备;?size=small 只要小图(队列行用)。
        前端在 URL 里带上 artwork 来源(?v=album),换图后地址就变了,所以可以长期缓存。"""
        if request.args.get('size') != 'small':
            path = artwork.path_for(item_id)
            if path and os.path.isfile(path):
                return send_file(path, mimetype='image/jpeg', max_age=86400, conditional=True)
        item = var.cache.get_item_by_id(item_id)
        if item is not None and request.args.get('size') != 'small':
            artwork.ensure(item, urgent=True)
            fallback = True
        else:
            fallback = False
        thumbnail = getattr(item, 'thumbnail', None) if item else None
        if not thumbnail:
            abort(404)
        try:
            data = base64.b64decode(thumbnail)
        except Exception:
            abort(404)
        # 高清图还没好:别让浏览器把小图缓存下来,好了以后同一地址还要能拿到高清的
        cache = 'no-cache' if fallback else 'private, max-age=86400'
        return Response(data, mimetype='image/jpeg', headers={'Cache-Control': cache})

    return api
