"""Web 请求操作的是哪个会话(服务器),以及这个用户能碰哪些服务器。

Web 代码不直接用 var.bot / var.playlist,统一从这里取。

- 选哪个服务器:请求头 X-DJ-Guild(前端每个请求都带),没有就看 ?guild=,都没有就是
  允许的服务器里的第一个(主服务器优先)。选了不允许的服务器 → 403 JSON。
- 能碰哪些服务器(access()):
    * bot 主人([bot] admin 里的 Discord id,按身份关联的 Discord 账号认)→ 全部,都能管理;
    * 用 Discord 登录 → 自己所在的服务器 ∩ bot 所在的服务器(Hub 能查成员时再和它对一遍,被踢了
      立刻生效);有 管理员 / 管理服务器 权限的能管理;
    * 其他登录方式(令牌 / 密码 / Cloudflare)但 /bind 过 Discord → 自己是成员的服务器,不能管理;
    * 令牌用户 → 发 /web 的那个服务器(web_token_guild 里记着;之前发的令牌算主服务器);
    * Discord Activity 的 Bearer 令牌 → 和 Discord 登录一样,另外打开 Activity 的服务器只要还是
      成员就在内,也是默认服务器;
    * 都不是 → 没有。
- 封禁:选好服务器后,关联的 Discord 账号被 user_ban 封了(全局或本服务器,规则同斜杠命令)→ 403 user_banned。
- 没有 Hub(var.hub 为 None,旧的单服务器部署 / 测试)时只有 var.bot 一个会话,
  所有通过了登录门禁的人照旧都能操作它,请求头里的服务器不看。

Hub 约定:sessions()、session_for(guild_id, create=True)、guild_ids()、guild_info(guild_id)、
home_guild_id、is_member(guild_id, user_id)。
"""

import json
import logging
import types

from flask import abort, g, has_request_context, jsonify, make_response, request
from flask import session as flask_session

import variables as var
import web_activity

log = logging.getLogger("bot")

GUILD_HEADER = 'X-DJ-Guild'
TOKEN_GUILD_SECTION = 'web_token_guild'


def hub():
    return getattr(var, 'hub', None)


def _deny(status, error):
    abort(make_response(jsonify({'error': error}), status))


# =====================================================================
#  权限
# =====================================================================

def owner_ids():
    """[bot] admin 里的 Discord 用户 id(角色 id 也会在里面,但不会和用户 id 撞)。"""
    raw = var.config.get('bot', 'admin', fallback='') if var.config is not None else ''
    return {a.strip() for a in (raw or '').replace(';', ',').split(',') if a.strip().isdigit()}


def linked_discord_id(ident):
    """身份对应的 Discord 账号:用 Discord 登录的就是它,否则看 /bind 的绑定。"""
    if ident is None:
        return None
    if getattr(ident, 'discord_id', None):
        return str(ident.discord_id)
    if ident.key and var.user_db is not None:
        try:
            return var.user_db.discord_id_for(ident.key)
        except Exception:
            log.debug("web: discord_link lookup failed for %s", ident.key, exc_info=True)
    return None


def token_guild_id():
    """令牌登录的会话能操作的服务器:发 /web 时记下的;令牌是加这个功能之前发的 → 主服务器。
    会话里的令牌已经换掉了就看这个用户现在的令牌。没有令牌 → None。"""
    if not has_request_context() or var.db is None:
        return None
    tokens = [flask_session.get('token')]
    user = flask_session.get('user')
    if user:
        try:
            tokens.append(json.loads(var.db.get('user', user, fallback='{}')).get('token'))
        except (TypeError, ValueError):
            pass
    for token in tokens:
        if not token or var.db.get('web_token', token, fallback=None) is None:
            continue
        guild_id = var.db.get(TOKEN_GUILD_SECTION, token, fallback=None)
        if guild_id:
            return str(guild_id)
        h = hub()
        return str(h.home_guild_id) if h is not None and h.home_guild_id else None
    return None


def member_state(guild_id, user_id):
    """按 bot 这边(Hub 的成员查询,有缓存)看 user 是不是这个服务器的成员:True / False;
    回答不了(没有 Hub、Hub 还没连上 Discord、没有 user id)→ None。

    Hub.is_member 查不了时也返回 False,所以只有连上了(有 client)的 Hub 说 False 才当真。"""
    h = hub()
    if h is None or not user_id:
        return None
    try:
        status = getattr(h, 'member_status', None)
        if callable(status):
            return status(str(guild_id), str(user_id))
        if h.is_member(str(guild_id), str(user_id)):
            return True
    except Exception:
        log.debug("web: is_member(%s, %s) failed", guild_id, user_id, exc_info=True)
        return None
    return False if getattr(h, 'client', None) is not None else None


def user_banned(discord_id, guild_id, manage=False):
    """这个 Discord 账号在这个服务器被封禁了没有(user_ban 规则)。规则和斜杠命令完全一样
    (bot.core.DJBot.banned):全局规则管除 bot 主人以外的所有人,本服务器的规则管不到能管理的人。"""
    if not discord_id:
        return False
    from bot.core import DJBot

    owner = str(discord_id) in owner_ids()
    # 不需要真的会话(可能在休眠):banned() 只用到 store 和 guild_id
    probe = types.SimpleNamespace(store=getattr(var, 'store', None), guild_id=str(guild_id or ''))
    try:
        return DJBot.banned(probe, 'user_ban', str(discord_id), admin=owner or manage, owner=owner)
    except Exception:
        log.warning("web: ban lookup for %s in %s failed", web_activity._for_log(discord_id),
                    web_activity._for_log(guild_id), exc_info=True)
        return False


class Access:
    """当前用户能操作的服务器 {guild_id: 能否管理},顺序 = 显示顺序。"""

    def __init__(self, guilds, owner=False, names=None):
        self.guilds = guilds
        self.owner = owner
        self.names = names or {}  # Discord 登录时用户那边看到的服务器名 / 图标,Hub 不知道时兜底

    def allows(self, guild_id):
        return str(guild_id) in self.guilds

    def can_manage(self, guild_id):
        return bool(self.guilds.get(str(guild_id)))


def _compute_access():
    import web_auth_discord
    from web_users import current_identity

    ident = current_identity()
    h = hub()
    if h is None:
        bot = var.bot
        guild_id = str(getattr(bot, 'guild_id', '') or '')
        manage = _legacy_can_manage(ident, guild_id)
        return Access({guild_id: manage}, owner=linked_discord_id(ident) in owner_ids())

    bot_ids = [str(i) for i in h.guild_ids()]
    discord_id = linked_discord_id(ident)
    if discord_id and discord_id in owner_ids():
        return Access({gid: True for gid in bot_ids}, owner=True)

    guilds, names = {}, {}
    if getattr(ident, 'discord_user', None):
        mine = {gd['id']: gd for gd in web_auth_discord.discord_guilds()}
        for gid in bot_ids:
            # OAuth 的列表最多缓存 GUILDS_TTL:被踢了以 bot 这边看到的为准,立刻生效
            if gid in mine and member_state(gid, discord_id) is not False:
                guilds[gid] = web_auth_discord.can_manage(mine[gid])
                names[gid] = mine[gid]
    elif discord_id:
        for gid in bot_ids:
            try:
                if h.is_member(gid, discord_id):
                    guilds[gid] = False
            except Exception:
                log.debug("web: is_member(%s, %s) failed", gid, discord_id, exc_info=True)
    token_gid = token_guild_id()
    if token_gid and token_gid in bot_ids:
        guilds.setdefault(token_gid, False)
    # Activity 令牌:签发时核对过这个服务器(成员 + 在语音频道里)
    # 之后被踢了就不再算(用 bot 这边的成员查询;OAuth 列表里有的上面已经算过)
    activity_gid = web_activity.current_guild_id()
    if activity_gid and activity_gid in bot_ids and activity_gid not in guilds \
            and member_state(activity_gid, discord_id):
        guilds[activity_gid] = False
    # 按 Hub 给的顺序
    return Access({gid: guilds[gid] for gid in bot_ids if gid in guilds}, names=names)


def _legacy_can_manage(ident, guild_id):
    """单服务器旧模式:bot 主人,或用 Discord 登录、在这个服务器有管理权限的人。"""
    import web_auth_discord

    if linked_discord_id(ident) in owner_ids():
        return True
    if getattr(ident, 'discord_user', None) and guild_id:
        return web_auth_discord.can_manage(web_auth_discord.find_guild(None, guild_id))
    return False


def access():
    """当前请求的 Access(一个请求只算一次)。"""
    cached = getattr(g, 'web_access', None)
    if cached is None:
        cached = _compute_access()
        g.web_access = cached
    return cached


def is_owner():
    return access().owner


# =====================================================================
#  选中的服务器 / 会话
# =====================================================================

def requested_guild_id():
    raw = request.headers.get(GUILD_HEADER) or request.args.get('guild') or ''
    raw = raw.strip()
    return raw if raw.isdigit() else None


def default_guild_id(acc=None):
    acc = acc or access()
    activity_gid = web_activity.current_guild_id()
    if activity_gid and acc.allows(activity_gid):
        return activity_gid
    h = hub()
    home = str(h.home_guild_id) if h is not None and h.home_guild_id else None
    if home and acc.allows(home):
        return home
    return next(iter(acc.guilds), None)


def guild_id():
    """这个请求操作的服务器 id。不允许 → 403。"""
    cached = getattr(g, 'web_guild_id', None)
    if cached is not None:
        return cached
    acc = access()
    if hub() is None:
        selected = next(iter(acc.guilds))  # 只有一个会话;请求头不看
    else:
        wanted = requested_guild_id()
        if wanted is not None:
            if not acc.allows(wanted):
                _deny(403, 'guild_forbidden')
            selected = wanted
        else:
            selected = default_guild_id(acc)
            if selected is None:
                _deny(403, 'no_guild_access')
    _refuse_banned(acc, selected)
    g.web_guild_id = selected
    return selected


def _refuse_banned(acc, selected):
    from web_users import current_identity

    discord_id = linked_discord_id(current_identity())
    if discord_id and user_banned(discord_id, selected, manage=acc.can_manage(selected)):
        _deny(403, 'user_banned')


def can_manage():
    """能不能改这个服务器的设置(公告频道、最大音量、封禁、频道设置)。"""
    return access().can_manage(guild_id())


def require_manage():
    if not can_manage():
        _deny(403, 'manage_required')


def session():
    """这个请求要操作的会话(DJBot)。"""
    h = hub()
    if h is None:
        return var.bot
    gid = guild_id()
    bot = h.session_for(gid, create=True)
    if bot is None:
        _deny(503, 'guild_unavailable')
    return bot


def any_session():
    """不需要服务器权限、只读点全局信息(命令名、版本)时用:选中的会话,拿不到就退回主会话。"""
    h = hub()
    if h is None:
        return var.bot
    try:
        return session()
    except Exception:
        home = h.home_guild_id
        return h.session_for(home, create=False) if home else var.bot


def playlist():
    """这个会话的队列。测试替身没有 playlist 属性时退回 var.playlist。"""
    bot = session()
    queue = getattr(bot, 'playlist', None) if bot is not None else None
    return queue if queue is not None else var.playlist


def set_playlist(new):
    """换队列对象(切换播放模式)。"""
    bot = session()
    if bot is not None and hasattr(bot, 'set_playlist'):
        bot.set_playlist(new)
    else:
        var.playlist = new
