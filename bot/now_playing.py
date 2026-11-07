# coding=utf-8
"""Discord 上的"正在播放"面板和语音频道状态。

bot 的 Discord 状态(Rich Presence)显示不了进度条和封面:bot 账号设置的活动只显示一行文字。
所以改在公告频道放一条 embed 面板(封面、歌名、歌手、专辑、进度条、控制按钮),
再把"🎵 歌名 — 歌手"写进 bot 所在语音频道的频道状态,频道列表里就能看到在放什么。

不 hook 播放器的每条分支:后台线程每秒看一眼播放状态(和 Web 播放页轮询 /api/status 一样),
状态有变化就更新;播放中每 PROGRESS_EVERY 秒刷新一次进度条。本模块不 import discord.py,
只产出普通的 dict,由 DiscordLink 转成 embed / 按钮。
"""

import base64
import logging
import os
import threading
import time
from io import BytesIO

import variables as var
from constants import tr_cli as tr

log = logging.getLogger("bot")

#: 检查播放状态的间隔(秒)
TICK = 1.0
#: 按了面板按钮后等多久再刷新(秒):命令在别的线程执行,暂停 / 切歌要先生效
POKE_DELAY = 0.3
#: 播放中刷新进度条的间隔(秒)。频道消息编辑的限速大约是每 5 秒 5 次,远用不完
PROGRESS_EVERY = 10.0
#: 更新失败后多久再试(秒),免得频道没权限时每秒打一次 API
RETRY_AFTER = 10.0
BAR_WIDTH = 18
LIVE_TYPES = ('radio', 'livestream')
#: Discord 语音频道状态的长度上限
VOICE_STATUS_MAX = 500
#: 面板按钮"循环"在这几个模式之间切换;随机 / 自动播放时点一下回到 one-shot
MODE_CYCLE = ('one-shot', 'repeat', 'single')
#: 没有封面时 embed 左边的颜色(Discord 蓝)
DEFAULT_COLOR = 0x5865F2


# =========================================================================
#   纯函数
# =========================================================================

def fmt_time(seconds):
    s = int(max(0, seconds or 0))
    h, rem = divmod(s, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def progress_bar(position, duration, width=BAR_WIDTH):
    """━━━━●──────:● 是当前位置。时长未知返回 ''。"""
    if not duration or duration <= 0:
        return ''
    frac = min(max(float(position) / float(duration), 0.0), 1.0)
    knob = min(int(frac * width), width - 1)
    return '━' * knob + '●' + '─' * (width - knob - 1)


def next_mode(mode):
    if mode in MODE_CYCLE:
        return MODE_CYCLE[(MODE_CYCLE.index(mode) + 1) % len(MODE_CYCLE)]
    return MODE_CYCLE[0]


def mode_label(mode):
    try:
        return tr(f'np_mode_{mode}')
    except KeyError:
        return mode


def _requester(wrapper):
    user = getattr(wrapper, 'user', '') or ''
    if not user:
        return ''
    try:
        from web_users import requester_display_name
        return requester_display_name(user) or user
    except Exception:
        return user


def _cover_source(item):
    """(key, path, b64):高清封面文件优先,没有就用条目自带的小缩略图。key 变了说明封面换了。"""
    from media import artwork
    path = None
    try:
        if artwork.has_hd(item.id):
            path = artwork.path_for(item.id)
    except Exception:
        path = None
    if path:
        try:
            mtime = os.path.getmtime(path)
        except OSError:
            mtime = 0
        return ('hd', item.id, mtime), path, None
    thumb = getattr(item, 'thumbnail', None)
    if thumb:
        return ('small', item.id, len(thumb)), None, thumb
    return None, None, None


def snapshot(bot):
    """当前播放状态 -> dict。队列空、没指向任何一首时返回 None。"""
    playlist = var.playlist
    if playlist is None or len(playlist) == 0 or playlist.current_index == -1:
        return None
    wrapper = playlist.current_item()
    if not wrapper:
        return None
    item = wrapper.item()
    item_type = getattr(item, 'type', '') or ''
    waiting = getattr(bot, 'is_waiting_for', None)
    if bot.is_pause:
        status = 'paused'
    elif waiting is not None and waiting(item.id):
        status = 'loading'
    else:
        status = 'playing'
    # 真的在出声(或在为这首做准备)。启动时恢复的队列 is_pause 是 False,但 ffmpeg 没在跑,不算在放
    active = status == 'loading' or (status == 'playing' and getattr(bot, 'thread', None) is not None)
    cover_key, cover_path, cover_b64 = _cover_source(item)
    url = getattr(item, 'url', '') or ''
    volume = getattr(getattr(bot, 'volume_helper', None), 'plain_volume_set', None)
    return {
        'id': item.id,
        'status': status,
        'active': active,
        'title': getattr(item, 'track', '') or item.format_title(),
        'artist': getattr(item, 'artist', '') or '',
        'album': getattr(item, 'album', '') or '',
        'url': url if url.startswith(('http://', 'https://')) else '',
        'live': item_type in LIVE_TYPES,
        'duration': getattr(item, 'duration', 0) or 0,
        'position': max(0.0, float(getattr(bot, 'playhead', 0) or 0)),
        'requester': _requester(wrapper),
        'mode': playlist.mode,
        'index': playlist.current_index + 1,
        'total': len(playlist),
        'volume': None if volume is None else int(round(volume * 100)),
        'cover_key': cover_key,
        'cover_path': cover_path,
        'cover_b64': cover_b64,
    }


def voice_status(snap):
    """语音频道状态文字:🎵 歌名 — 歌手(暂停时 ⏸)。没在放返回 ''(清除)。"""
    if snap is None:
        return ''
    name = snap['title'] + (f" — {snap['artist']}" if snap['artist'] else '')
    icon = '⏸' if snap['status'] == 'paused' else '🎵'
    return f"{icon} {name}"[:VOICE_STATUS_MAX]


def build_panel(snap):
    """snapshot -> 面板内容(DiscordLink.panel_show 用)。不含封面字节,由调用方按需加上。"""
    status = snap['status']
    if snap['live']:
        progress = f"🔴 {tr('np_live')} · `{fmt_time(snap['position'])}`"
    elif snap['duration'] > 0:
        position = min(snap['position'], snap['duration'])
        progress = (f"{progress_bar(position, snap['duration'])}\n"
                    f"`{fmt_time(position)} / {fmt_time(snap['duration'])}`")
    else:
        progress = f"`{fmt_time(snap['position'])}`"

    fields = []
    if snap['artist']:
        fields.append((tr('np_artist'), snap['artist']))
    if snap['album']:
        fields.append((tr('np_album'), snap['album']))

    footer = [tr('np_footer', mode=mode_label(snap['mode']), index=snap['index'], total=snap['total'])]
    if snap['volume'] is not None:
        footer.append(tr('np_volume', volume=snap['volume']))
    if snap['requester']:
        footer.append(tr('np_requester', name=snap['requester']))

    return {
        'author': tr(f'np_status_{status}'),
        'title': snap['title'],
        'url': snap['url'],
        'description': progress,
        'fields': fields,
        'footer': ' · '.join(footer),
        'has_cover': snap['cover_key'] is not None,
        'buttons': True,
    }


def build_ended(last):
    """队列放完:面板定格在最后一首,去掉进度条和按钮。"""
    return {
        'author': tr('np_status_ended'),
        'title': last['title'] if last else '',
        'url': last['url'] if last else '',
        'description': tr('np_ended'),
        'fields': [],
        'footer': '',
        'has_cover': bool(last and last['cover_key'] is not None),
        'buttons': False,
    }


def load_cover(snap):
    """(JPEG 字节, embed 颜色)。读不到返回 (None, None)。"""
    data = None
    try:
        if snap['cover_path']:
            with open(snap['cover_path'], 'rb') as f:
                data = f.read()
        elif snap['cover_b64']:
            data = base64.b64decode(snap['cover_b64'])
    except Exception:
        log.debug("now playing: could not read the cover", exc_info=True)
        return None, None
    if not data:
        return None, None
    return data, cover_color(data)


def cover_color(data):
    """封面的平均色,当 embed 左边那条的颜色;太暗的提亮一点,不然在深色主题上看不见。"""
    try:
        from PIL import Image
        with Image.open(BytesIO(data)) as im:
            r, g, b = im.convert('RGB').resize((1, 1), Image.BILINEAR).getpixel((0, 0))
    except Exception:
        return None
    peak = max(r, g, b)
    if peak < 96:
        scale = 96 / max(peak, 1)
        r, g, b = (min(255, int(c * scale)) for c in (r, g, b))
    return (r << 16) | (g << 8) | b


# =========================================================================
#   后台更新
# =========================================================================

class NowPlaying:
    """每秒看一眼播放状态,更新面板和语音频道状态。所有 link 调用都在本线程里,不阻塞播放。"""

    def __init__(self, bot, link, panel=True, voice=True):
        self.bot = bot
        self.link = link
        self.panel_enabled = panel
        self.voice_enabled = voice
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = None
        # 面板
        self._shown = False         # 面板上是一首正在进行的歌(不是"播放结束")
        self._track = None          # 面板上那首的 id
        self._key = None            # 上次渲染时的状态,变了就立刻更新
        self._cover_key = None
        self._color = None
        self._last_edit = 0.0
        self._retry_at = 0.0
        self._last_snap = None
        self._stale = False         # 接手了上次运行留下的面板,还没更新过
        self._saved_ref = None
        # 语音频道状态:(频道 id, 文字),上次成功(或确定不用再试)的
        self._voice = (None, '')

    # ---- 生命周期 ----

    def start(self):
        if not (self.panel_enabled or self.voice_enabled):
            return
        self._adopt_panel()
        self._thread = threading.Thread(target=self._run, name="NowPlaying", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._wake.set()

    def poke(self):
        """面板按钮刚按过:马上刷新一次,不等下一秒。"""
        self._wake.set()

    def _run(self):
        failures = 0
        while True:
            if self._wake.wait(TICK):
                self._wake.clear()
                time.sleep(POKE_DELAY)  # 命令在分发线程里执行,给它一点时间生效
            if self._stop.is_set():
                return
            try:
                self.tick()
                failures = 0
            except Exception:
                failures += 1
                if failures in (1, 60) or failures % 600 == 0:
                    log.exception("now playing: update failed")

    # ---- 一次检查 ----

    def tick(self, now=None):
        now = time.time() if now is None else now
        snap = snapshot(self.bot)
        if self.voice_enabled:
            self._update_voice(snap)
        if self.panel_enabled:
            self._update_panel(snap, now)

    def _update_voice(self, snap):
        channel_id = self.link.my_channel_id
        text = voice_status(snap) if channel_id is not None else ''
        if (channel_id, text) == self._voice:
            return
        if channel_id is not None:
            self.link.set_voice_status(text)
        # 失败(没权限等)也记下:文字下次变化时再试,不每秒重试
        self._voice = (channel_id, text)

    def _update_panel(self, snap, now):
        if now < self._retry_at:
            return
        if self._stale and (snap is None or not snap['active']):
            # 上次运行留下的面板:按钮还在,状态是旧的。先把按钮收掉,开始放歌时再接着用这条消息
            self._stale = False
            self.link.panel_end(None)
        if snap is None:
            if self._shown:
                ended = build_ended(self._last_snap)
                ended['color'] = self._color or DEFAULT_COLOR
                if self.link.panel_end(ended):
                    self._shown = False
                    self._track = None
                    self._key = None
                else:
                    self._retry_at = now + RETRY_AFTER
            return
        new_track = snap['id'] != self._track
        if new_track and not self._shown and not snap['active']:
            # 启动时恢复了上次的队列(暂停着,或还没开始放):等真正出声再发面板
            return
        key = tuple(snap[k] for k in ('id', 'status', 'title', 'artist', 'album', 'mode', 'index',
                                      'total', 'volume', 'requester', 'cover_key', 'duration'))
        due = snap['status'] == 'playing' and now - self._last_edit >= PROGRESS_EVERY
        if not new_track and key == self._key and not due:
            return

        panel = build_panel(snap)
        if new_track or snap['cover_key'] != self._cover_key:
            data, color = load_cover(snap) if snap['cover_key'] is not None else (None, None)
            panel['cover'] = data
            panel['has_cover'] = data is not None
            self._color = color
        panel['color'] = self._color or DEFAULT_COLOR

        if self.link.panel_show(panel, new_track=new_track):
            self._stale = False
            self._shown = True
            self._track = snap['id']
            self._key = key
            self._cover_key = snap['cover_key']
            self._last_edit = now
            self._last_snap = snap
            self._save_panel_ref()
        else:
            self._retry_at = now + RETRY_AFTER

    # ---- 按钮 ----

    def resolve_button(self, action):
        """面板按钮 -> (命令 key, 参数)。走和斜杠命令一样的权限检查和处理。"""
        if action == 'toggle':
            return ('play', {}) if self.bot.is_pause else ('pause', {})
        if action == 'skip':
            return 'skip', {}
        if action == 'stop':
            return 'stop', {}
        if action == 'mode':
            return 'mode', {'mode': next_mode(var.playlist.mode)}
        return None

    # ---- 重启后接着用上次的面板 ----

    def _adopt_panel(self):
        if not self.panel_enabled or var.db is None:
            return
        try:
            ref = var.db.get('discord', 'panel_message', fallback='')
            channel_id, message_id = (int(x) for x in ref.split(':'))
        except Exception:
            return
        self.link.panel_adopt(channel_id, message_id)
        self._saved_ref = (channel_id, message_id)
        self._stale = True

    def _save_panel_ref(self):
        ref = self.link.panel_ref
        if ref is None or ref == self._saved_ref or var.db is None:
            return
        try:
            var.db.set('discord', 'panel_message', f"{ref[0]}:{ref[1]}")
            self._saved_ref = ref
        except Exception:
            log.debug("now playing: could not remember the panel message", exc_info=True)
