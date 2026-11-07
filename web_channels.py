"""频道 API(/api/channels*):语音频道树、默认频道、跟随设置、立即移动 / 离开。逻辑在 bot/channels.py。

Discord 的频道 / 用户 ID 是 64 位整数,超过 JavaScript Number 的安全范围(2^53),
所以 JSON 里一律转成字符串;收到的也按字符串解析。
"""

import logging

from flask import Blueprint, abort, jsonify, request

import web_context
from bot.channels import FOLLOW_MODES
from web_users import current_user_name

log = logging.getLogger("bot")


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


def overview():
    bot = web_context.session()
    settings = bot.channel_settings()
    tree = bot.channel_tree()
    humans = sorted({u.name for users in bot.humans_by_channel().values() for u in users},
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
    }


def create_blueprint(requires_auth):
    api = Blueprint('channels', __name__, url_prefix='/api/channels')

    @api.route('', methods=['GET'])
    @requires_auth
    def channels():
        return jsonify(overview())

    @api.route('/settings', methods=['POST'])
    @requires_auth
    def channel_settings():
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
        if not web_context.session().move_to_channel(cid, f"requested by {current_user_name()} on the web") \
                and web_context.session().my_channel_id() != cid:
            abort(502)
        return jsonify(overview())

    @api.route('/leave', methods=['POST'])
    @requires_auth
    def channel_leave():
        if web_context.session().my_channel_id() is not None:
            log.info("web: %s asked the bot to leave the voice channel", current_user_name())
            web_context.session().pause()
            web_context.session().leave_voice()
        return jsonify(overview())

    return api
