"""服务器选择和按服务器的管理设置(/api/guilds、/api/guild/*)。

GET    /api/guilds              当前用户能操作的服务器:[{id, name, icon, can_manage, selected}]
GET    /api/guild/settings      这个服务器的管理设置(要能管理)
POST   /api/guild/settings      {announce_channel?: id|null, max_volume?: 0..100}
GET    /api/guild/bans          这个服务器自己的封禁:{user_ban: [...], url_ban: [...]}(全局的不在这里)
POST   /api/guild/bans          {kind: user_ban|url_ban, value, note?}
DELETE /api/guild/bans          {kind, value}

哪个服务器由 X-DJ-Guild 请求头决定(web_context)。设置存在 GuildStore(var.store)里:
announce_channel、max_volume(0..1,和 /maxvolume 命令同一格式);封禁规则 scope = 服务器 id。
"""

import html
import logging

from flask import Blueprint, abort, jsonify, request

import util
import variables as var
import web_context
from web_users import current_identity, current_user_name

log = logging.getLogger("bot")

CDN_BASE = 'https://cdn.discordapp.com'
BAN_KINDS = ('user_ban', 'url_ban')
NOTE_MAX_LEN = 100


def _payload():
    return request.get_json(silent=True) or request.form or {}


def icon_url(guild_id, icon):
    """Discord 的图标 hash -> CDN 地址;已经是地址的原样返回。"""
    if not icon:
        return None
    if str(icon).startswith(('http://', 'https://')):
        return icon
    return f"{CDN_BASE}/icons/{guild_id}/{icon}.png?size=64"


def _guild_info(guild_id, acc):
    hub = web_context.hub()
    info = None
    if hub is not None:
        try:
            info = hub.guild_info(guild_id)
        except Exception:
            log.debug("web: guild_info(%s) failed", guild_id, exc_info=True)
    if not info:
        info = acc.names.get(guild_id)
    if not info and hub is None:
        link = getattr(var.bot, 'link', None)
        info = {'name': getattr(link, 'guild_name', '') or ''}
    info = info or {}
    return {'name': info.get('name') or guild_id, 'icon': icon_url(guild_id, info.get('icon'))}


def guilds_payload():
    acc = web_context.access()
    try:
        selected = web_context.guild_id()
    except Exception:
        selected = None  # 请求头里是不允许的服务器:列表照给,让前端换一个
    out = []
    for gid, manage in acc.guilds.items():
        out.append(dict(_guild_info(gid, acc), id=gid, can_manage=bool(manage), selected=gid == selected))
    return out


def _store():
    store = getattr(web_context.session(), 'store', None) or var.store
    if store is None:
        abort(503)
    return store


def _default_max_volume():
    return var.config.getfloat('bot', 'max_volume', fallback=1.0)


def _settings_payload():
    session = web_context.session()
    gid = web_context.guild_id()
    store = _store()
    announce = store.get(gid, 'announce_channel')
    try:
        max_volume = float(store.get(gid, 'max_volume'))
    except (TypeError, ValueError):
        max_volume = _default_max_volume()
    channels = []
    lister = getattr(session, 'text_channels', None)
    if callable(lister):
        try:
            channels = [{'id': str(c['id']), 'name': c.get('name', '')} for c in lister() or []]
        except Exception:
            log.debug("web: text_channels failed", exc_info=True)
    return {
        'guild_id': gid,
        'announce_channel': announce or None,
        'text_channels': channels,
        'max_volume': round(max_volume * 100),
        'default_max_volume': round(_default_max_volume() * 100),
    }


def _bans_payload():
    gid = web_context.guild_id()
    store = _store()
    return {kind: store.list_rules(kind, gid) for kind in BAN_KINDS}


def _ban_value(kind, raw):
    raw = str(raw or '').strip()
    if kind == 'user_ban':
        # Discord user id;也接受 <@123> 这种提及写法
        raw = raw.strip('<@!>')
        if not raw.isdigit() or len(raw) > 20:
            abort(400)
        return raw
    url = util.get_url_from_input(raw) if raw else ''
    if not url or len(url) > 2048:
        abort(400)
    return url


def create_blueprint(requires_auth):
    api = Blueprint('guilds', __name__, url_prefix='/api')

    @api.route('/guilds', methods=['GET'])
    @requires_auth
    def guilds():
        return jsonify({'guilds': guilds_payload(), 'owner': web_context.is_owner(),
                        'multi': web_context.hub() is not None})

    @api.route('/guild/settings', methods=['GET'])
    @requires_auth
    def guild_settings():
        web_context.require_manage()
        return jsonify(_settings_payload())

    @api.route('/guild/settings', methods=['POST'])
    @requires_auth
    def set_guild_settings():
        web_context.require_manage()
        payload = _payload()
        session = web_context.session()
        gid = web_context.guild_id()
        store = _store()
        changed = {}
        if 'announce_channel' in payload:
            raw = payload['announce_channel']
            if raw in (None, ''):
                raw = None
            else:
                raw = str(raw).strip()
                if not raw.isdigit() or len(raw) > 20:
                    abort(400)
            # 经过会话:存进库,并让正在运行的 GuildLink 立刻改用新频道
            setter = getattr(session, 'set_announce_channel', None)
            if setter is not None:
                setter(raw)
            elif raw is None:
                store.delete(gid, 'announce_channel')
            else:
                store.set(gid, 'announce_channel', raw)
            changed['announce_channel'] = raw
        if 'max_volume' in payload:
            try:
                percent = int(payload['max_volume'])
            except (TypeError, ValueError):
                abort(400)
            if not 0 <= percent <= 100:
                abort(400)
            max_vol = percent / 100.0
            store.set(gid, 'max_volume', max_vol)
            changed['max_volume'] = percent
            helper = getattr(session, 'volume_helper', None)
            if helper is not None and helper.plain_volume_set > max_vol:
                helper.set_volume(max_vol)
                store.set(gid, 'volume', str(max_vol))
        if not changed:
            abort(400)
        log.info("web: %s changed settings of guild %s: %s", current_user_name(), gid, changed)
        return jsonify(_settings_payload())

    @api.route('/guild/bans', methods=['GET'])
    @requires_auth
    def guild_bans():
        web_context.require_manage()
        return jsonify(_bans_payload())

    @api.route('/guild/bans', methods=['POST'])
    @requires_auth
    def add_guild_ban():
        web_context.require_manage()
        payload = _payload()
        kind = payload.get('kind')
        if kind not in BAN_KINDS:
            abort(400)
        value = _ban_value(kind, payload.get('value'))
        note = html.escape(str(payload.get('note') or '').strip()[:NOTE_MAX_LEN])
        gid = web_context.guild_id()
        ident = current_identity()
        _store().add_rule(gid, kind, value, created_by=ident.key or current_user_name(), note=note)
        log.info("web: %s added %s %s in guild %s", current_user_name(), kind, value, gid)
        return jsonify(_bans_payload())

    @api.route('/guild/bans', methods=['DELETE'])
    @requires_auth
    def remove_guild_ban():
        web_context.require_manage()
        payload = _payload()
        kind = payload.get('kind') or request.args.get('kind')
        if kind not in BAN_KINDS:
            abort(400)
        value = str(payload.get('value') or request.args.get('value') or '').strip()
        if not value:
            abort(400)
        gid = web_context.guild_id()
        if not _store().remove_rule(gid, kind, value):
            abort(404)
        log.info("web: %s removed %s %s in guild %s", current_user_name(), kind, value, gid)
        return jsonify(_bans_payload())

    return api
