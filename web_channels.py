"""频道 API(/api/channels*):语音频道树、默认频道、跟随设置、立即移动 / 离开。逻辑在 bot/channels.py。

改设置要能管理这个服务器(多服务器时);移动 / 离开是普通操作,能操作这个服务器就行,但多服务器时
不能管理的人只看得到自己在 Discord 里看得见的语音频道,只能让 bot 去自己能连的频道,
只有自己和 bot 在同一个语音频道时才能让它离开。

Discord 的频道 / 用户 ID 是 64 位整数,超过 JavaScript Number 的安全范围(2^53),
所以 JSON 里一律转成字符串;收到的也按字符串解析。
"""

import logging
import threading
import time

from flask import Blueprint, abort, jsonify, request

import web_context
from bot.channels import FOLLOW_MODES
from web_users import current_identity, current_user_name

log = logging.getLogger("bot")

PERMS_TTL = 30  # 频道树轮询很勤;成员不在缓存里时要走一次 REST
_perms_lock = threading.Lock()
_perms_cache = {}


def _payload():
    return request.get_json(silent=True) or request.form or {}


def _sid(value):
    return None if value is None else str(value)


def _node(node):
    """频道树节点里的 ID 转字符串。"""
    if node is None:
        return None
    out = dict(node)
    out['id'] = _sid(node['id'])
    out['users'] = [dict(u, session=_sid(u['session'])) for u in node.get('users', [])]
    out['children'] = [_node(c) for c in node.get('children', [])]
    return out


def _parse_id(raw):
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        abort(400)


def unrestricted():
    """单服务器旧模式(没有 Hub)和能管理这个服务器的人不受成员频道权限限制。"""
    return web_context.hub() is None or web_context.can_manage()


def _requester_id():
    raw = web_context.linked_discord_id(current_identity())
    return int(raw) if raw and str(raw).isdigit() else None


def _fetch_voice_perms(guild_id, user_id):
    """在 Discord 事件循环里算这个成员对每个语音 / 舞台频道的 (view_channel, connect)。
    查不到成员 / 连接不可用 → None。"""
    import discord

    h = web_context.hub()
    dc = getattr(h, 'client', None) if h is not None else None
    if dc is None:
        return None

    async def collect():
        guild = dc.client.get_guild(int(guild_id))
        if guild is None:
            return None
        member = guild.get_member(user_id)
        if member is None:
            # 没开 members intent:只有在语音里的成员在缓存里
            try:
                member = await guild.fetch_member(user_id)
            except discord.HTTPException:
                return None
        out = {}
        for channel in list(guild.voice_channels) + list(guild.stage_channels):
            perms = channel.permissions_for(member)
            out[channel.id] = (bool(perms.view_channel), bool(perms.connect and perms.view_channel))
        return out

    try:
        result = dc.call(collect(), timeout=10)
    except Exception:
        log.debug("web: could not resolve voice permissions of %s in %s", user_id, guild_id, exc_info=True)
        return None
    return result if isinstance(result, dict) else None


def voice_perms(bot):
    """请求者对这个服务器各语音频道的 {channel_id: (能看见, 能连接)};不知道是谁 / 查不到 → {}
    (按什么都看不见处理)。"""
    user_id = _requester_id()
    guild_id = str(getattr(bot, 'guild_id', '') or web_context.guild_id())
    if user_id is None or not guild_id.isdigit():
        return {}
    key = (guild_id, user_id)
    now = time.monotonic()
    with _perms_lock:
        hit = _perms_cache.get(key)
        if hit is not None and hit[1] > now:
            return hit[0]
    perms = _fetch_voice_perms(guild_id, user_id)
    if perms is None:
        return {}  # 查不了不缓存,下次再查
    with _perms_lock:
        if len(_perms_cache) > 5000:
            _perms_cache.clear()
        _perms_cache[key] = (perms, now + PERMS_TTL)
    return perms


def _visible_tree(node, perms):
    """去掉看不见的语音 / 舞台频道(连同里面的人),以及因此变空的分类。"""
    if node is None:
        return None
    kind = node.get('kind', 'voice')
    if kind in ('voice', 'stage') and not perms.get(node['id'], (False, False))[0]:
        return None
    out = dict(node)
    children = [_visible_tree(c, perms) for c in node.get('children', [])]
    out['children'] = [c for c in children if c is not None]
    if kind == 'category' and not out['children']:
        return None
    return out


def overview():
    bot = web_context.session()
    settings = bot.channel_settings()
    tree = bot.channel_tree()
    by_channel = bot.humans_by_channel()
    if tree is not None and not unrestricted():
        perms = voice_perms(bot)
        tree = _visible_tree(tree, perms)
        by_channel = {cid: users for cid, users in by_channel.items()
                      if perms.get(cid, (False, False))[0]}
    humans = sorted({u.name for users in by_channel.values() for u in users},
                    key=str.lower)
    default_id = bot.find_channel_by_path(settings['default']) if settings['default'] else None
    return {
        'tree': _node(tree),
        'server_name': getattr(bot.link, 'guild_name', '') or '',
        'current_channel_id': _sid(bot.my_channel_id()),
        'settings': {
            'default_path': settings['default'],
            'default_channel_id': _sid(default_id),
            'follow': settings['follow'],
            'follow_user': settings['follow_user'],
            'return_home': settings['return_home'],
            'idle_pause_minutes': settings['idle_pause_minutes'],
            'idle_resume': settings['idle_resume'],
        },
        'online_users': humans,
        'can_edit_settings': can_edit_settings(),
    }


def _requester_in(bot, channel_id):
    """请求者现在在不在这个语音频道里(按网关的语音状态快照)。"""
    user_id = _requester_id()
    if user_id is None:
        return False
    return any(getattr(u, 'user_id', u.session) == user_id and u.channel_id == channel_id
               for u in bot.link.users.values())


def can_edit_settings():
    """改频道设置要能管理这个服务器;单服务器旧模式(没有 Hub)照旧谁都能改。"""
    return unrestricted()


def create_blueprint(requires_auth):
    api = Blueprint('channels', __name__, url_prefix='/api/channels')

    @api.route('', methods=['GET'])
    @requires_auth
    def channels():
        return jsonify(overview())

    @api.route('/settings', methods=['POST'])
    @requires_auth
    def channel_settings():
        if not can_edit_settings():
            web_context.require_manage()
        payload = _payload()
        changes = {}
        if 'default_channel_id' in payload:
            raw = payload['default_channel_id']
            if raw in (None, ''):
                changes['default'] = []  # 不自动进频道
            else:
                cid = _parse_id(raw)
                if not web_context.session()._joinable(cid):
                    abort(404)
                changes['default'] = web_context.session().channel_path(cid)
        if 'follow' in payload:
            if payload['follow'] not in FOLLOW_MODES:
                abort(400)
            changes['follow'] = payload['follow']
        if 'follow_user' in payload:
            name = str(payload['follow_user'] or '').strip()
            if len(name) > 128:
                abort(400)
            changes['follow_user'] = name
        if 'return_home' in payload:
            changes['return_home'] = bool(payload['return_home'])
        if 'idle_pause_minutes' in payload:
            try:
                minutes = int(payload['idle_pause_minutes'])
            except (TypeError, ValueError):
                abort(400)
            if not 0 <= minutes <= 24 * 60:
                abort(400)
            changes['idle_pause_minutes'] = minutes
        if 'idle_resume' in payload:
            changes['idle_resume'] = bool(payload['idle_resume'])
        if not changes:
            abort(400)
        web_context.session().save_channel_settings(**changes)
        log.info("web: %s changed channel settings: %s", current_user_name(), changes)
        return jsonify(overview())

    @api.route('/join', methods=['POST'])
    @requires_auth
    def channel_join():
        cid = _parse_id(_payload().get('channel_id'))
        if not web_context.session()._joinable(cid):
            abort(404)
        if not unrestricted() and not voice_perms(web_context.session()).get(cid, (False, False))[1]:
            return jsonify({'error': 'channel_forbidden'}), 403
        if not web_context.session().move_to_channel(cid, f"requested by {current_user_name()} on the web") \
                and web_context.session().my_channel_id() != cid:
            abort(502)
        return jsonify(overview())

    @api.route('/leave', methods=['POST'])
    @requires_auth
    def channel_leave():
        current = web_context.session().my_channel_id()
        if current is not None and not unrestricted() and not _requester_in(web_context.session(), current):
            return jsonify({'error': 'not_in_channel'}), 403
        if current is not None:
            log.info("web: %s asked the bot to leave the voice channel", current_user_name())
            web_context.session().pause()
            web_context.session().leave_voice()
        return jsonify(overview())

    return api
