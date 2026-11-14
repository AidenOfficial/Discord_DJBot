"""用 Discord 账号登录 Web 界面(OAuth2 authorization code,scope: identify guilds)。

流程:/auth/discord/login 跳到 Discord 授权页 → Discord 带 code 回调 /auth/discord/callback
→ 换 token、读 /users/@me 和 /users/@me/guilds → 写进会话 → 回到 Web 首页。

- 会话 Cookie 里只放 Discord 用户的基本信息(Flask 会话只签名不加密,token 不能放进去);
  token 和服务器列表放在本进程的内存缓存里,按 Discord user id 索引,超过 GUILDS_TTL 才在
  下次用到时重新拉取(遇到 429 按 retry_after 退避)。Discord 说 token 无效(400/401/403,
  比如用户取消了授权)就清空服务器列表;拉取一直失败、列表旧过 2*GUILDS_TTL 也不再认。
  重启后缓存为空,会话随之失效,要重新登录(prompt=none,授权过的人不用再点确认)。
- 换 token 的请求有熔断:Discord 回 429 后到 retry_after 为止不再请求;另外整个进程
  有个总预算(TOKEN_BUDGET),超了直接报 503,不去打 Discord。
- 身份:discord_link 里已经有 discord:<id>(用过 /bind)就用绑定的那个 Web 身份,
  个人歌单 / 收藏跟着走;否则身份就是 discord:<id>,并写一条 discord_link,
  这样不需要再 /bind。
- auth_method = discord 时这是 Web 界面的门禁:没登录的网页请求跳去登录,/api/ 返回
  401 JSON;登录了但和 bot 不在同一个服务器的账号 403。
  auth_method = token 时,配置了 Discord 登录也可以代替令牌(同样要求同服务器)。

之后的多服务器面板用 discord_user_id() / discord_guilds() / can_manage() 做按服务器的授权。
"""

import hmac
import logging
import os
import secrets
import threading
import time
from urllib.parse import urlencode

import requests
from flask import Blueprint, has_request_context, jsonify, redirect, render_template, request, session
from flask import g as request_globals
from markupsafe import Markup, escape

import variables as var

log = logging.getLogger("bot")

AUTHORIZE_URL = 'https://discord.com/oauth2/authorize'
API_BASE = 'https://discord.com/api/v10'
TOKEN_URL = API_BASE + '/oauth2/token'
CDN_BASE = 'https://cdn.discordapp.com'
SCOPES = 'identify guilds'
HTTP_TIMEOUT = 10
GUILDS_TTL = 600
# 拉取失败(网络 / 5xx / token 失效)后多久再试,避免每个请求都打一次 Discord
FAILURE_BACKOFF = 60
CACHE_MAX_USERS = 5000
# Discord 明确说 token 不能用了
_TOKEN_DEAD = (400, 401, 403)
# 进程内所有换 token 请求(登录、Activity、续期)的总预算:(次数, 秒)
TOKEN_BUDGET = (30, 60)
MIN_BACKOFF = 5

PERM_ADMINISTRATOR = 0x8
PERM_MANAGE_GUILD = 0x20

SESSION_USER = 'discord_user'
# 旧版本把 token 放在会话 Cookie 里;读到就删掉
LEGACY_SESSION_TOKEN = 'discord_token'
SESSION_STATE = 'discord_oauth_state'
SESSION_NEXT = 'discord_oauth_next'
# prompt=none 时 Discord 可能要求用户确认,回调带这些 error
_NEEDS_INTERACTION = ('interaction_required', 'consent_required', 'login_required')


# =====================================================================
#  配置
# =====================================================================

def _conf(option):
    return (var.config.get('webinterface', option, fallback='') or '').strip()


def client_id():
    return _conf('discord_client_id')


def client_secret():
    # 和 DISCORD_TOKEN 一样,环境变量优先,密钥可以不写进 ini
    return (os.environ.get('DISCORD_CLIENT_SECRET') or '').strip() or _conf('discord_client_secret')


def configured():
    """填了 client id 和 secret:可以用 Discord 登录(不一定是门禁)。"""
    return bool(client_id() and client_secret())


def is_gate():
    return var.config.get('webinterface', 'auth_method', fallback='none') == 'discord'


def redirect_uri():
    """必须和 Developer Portal 里登记的 Redirect 完全一致,所以优先用 public_url。"""
    base = _conf('public_url') or request.url_root
    return base.rstrip('/') + '/auth/discord/callback'


def login_url(next_path=None):
    """站内的登录入口(相对当前挂载点),给模板 / 前端用。"""
    url = request.script_root + '/auth/discord/login'
    if next_path:
        url += '?' + urlencode({'next': next_path})
    return url


def _safe_next(value):
    # 只接受站内相对路径,防开放重定向(//evil.com、/\evil.com)
    if not value or not value.startswith('/') or value.startswith('//') or value.startswith('/\\'):
        return None
    return value


def avatar_url(user):
    if not user or not user.get('id'):
        return None
    if user.get('avatar'):
        return f"{CDN_BASE}/avatars/{user['id']}/{user['avatar']}.png?size=128"
    try:
        index = (int(user['id']) >> 22) % 6
    except (TypeError, ValueError):
        index = 0
    return f"{CDN_BASE}/embed/avatars/{index}.png"


# =====================================================================
#  Discord HTTP
# =====================================================================

class DiscordError(Exception):
    def __init__(self, message, status=None, retry_after=None):
        super().__init__(message)
        self.status = status
        self.retry_after = retry_after


def _check(resp, what):
    if resp.status_code == 429:
        try:
            retry = float((resp.json() or {}).get('retry_after') or 0)
        except ValueError:
            retry = 0
        retry = retry or float(resp.headers.get('Retry-After') or 5)
        raise DiscordError(f"{what}: rate limited", 429, retry)
    if resp.status_code >= 400:
        raise DiscordError(f"{what}: HTTP {resp.status_code}", resp.status_code)
    try:
        return resp.json()
    except ValueError:
        raise DiscordError(f"{what}: invalid JSON", resp.status_code)


_breaker_lock = threading.Lock()
_token_backoff_until = 0.0  # time.monotonic():Discord 回 429 后到这个时间为止不再换 token


def _token_gate():
    """换 token 之前:还在 429 退避期 → DiscordError(429);超出进程预算 → DiscordError(503)。"""
    from web_security import limiter

    wait = _token_backoff_until - time.monotonic()
    if wait > 0:
        raise DiscordError('token: backing off after Discord rate limit', 429, wait)
    limit, window = TOKEN_BUDGET
    over = limiter.hit('oauth_token|process', limit, window)
    if over:
        raise DiscordError('token: exchange budget exhausted', 503, over)


def _token_request(data):
    global _token_backoff_until

    _token_gate()
    data = dict(data, client_id=client_id(), client_secret=client_secret())
    try:
        resp = requests.post(TOKEN_URL, data=data, timeout=HTTP_TIMEOUT,
                             headers={'Content-Type': 'application/x-www-form-urlencoded'})
    except requests.RequestException as e:
        raise DiscordError(f"token: {e}")
    try:
        payload = _check(resp, 'token')
    except DiscordError as e:
        if e.status == 429:
            with _breaker_lock:
                _token_backoff_until = max(_token_backoff_until,
                                           time.monotonic() + max(MIN_BACKOFF, e.retry_after or 0))
        raise
    if not payload.get('access_token'):
        raise DiscordError('token: no access_token in response')
    return {
        'access_token': payload['access_token'],
        'refresh_token': payload.get('refresh_token') or '',
        'expires_at': time.time() + float(payload.get('expires_in') or 0),
    }


def exchange_code(code):
    return _token_request({'grant_type': 'authorization_code', 'code': code, 'redirect_uri': redirect_uri()})


def exchange_activity_code(code):
    """Embedded App SDK 的 authorize() 拿到的 code:授权时没有 redirect_uri,换令牌时也不能带。"""
    return _token_request({'grant_type': 'authorization_code', 'code': code})


def refresh_access_token(refresh_token):
    return _token_request({'grant_type': 'refresh_token', 'refresh_token': refresh_token})


def _api_get(path, access_token):
    try:
        resp = requests.get(API_BASE + path, timeout=HTTP_TIMEOUT,
                            headers={'Authorization': f"Bearer {access_token}"})
    except requests.RequestException as e:
        raise DiscordError(f"{path}: {e}")
    return _check(resp, path)


def fetch_user(access_token):
    data = _api_get('/users/@me', access_token)
    if not data.get('id'):
        raise DiscordError('/users/@me: no id')
    return {
        'id': str(data['id']),
        'username': data.get('username') or '',
        'global_name': data.get('global_name') or '',
        'avatar': data.get('avatar') or '',
    }


def fetch_guilds(access_token):
    guilds = []
    for g in _api_get('/users/@me/guilds', access_token) or []:
        try:
            permissions = int(g.get('permissions') or 0)
        except (TypeError, ValueError):
            permissions = 0
        guilds.append({
            'id': str(g.get('id')),
            'name': g.get('name') or '',
            'icon': g.get('icon') or None,
            'owner': bool(g.get('owner')),
            'permissions': permissions,
        })
    return guilds


# =====================================================================
#  服务器列表缓存
# =====================================================================

_cache_lock = threading.Lock()
_cache = {}  # Discord user id -> {'guilds', 'fetched_at', 'retry_at', 'token', 'lock'}


def _store(user_id, token=None, guilds=None):
    with _cache_lock:
        entry = _cache.get(user_id)
        if entry is None:
            if len(_cache) >= CACHE_MAX_USERS:
                oldest = min(_cache, key=lambda k: _cache[k]['fetched_at'])
                _cache.pop(oldest, None)
            entry = {'guilds': [], 'fetched_at': 0.0, 'retry_at': 0.0, 'token': None,
                     'lock': threading.Lock()}
            _cache[user_id] = entry
        if token is not None:
            entry['token'] = token
        if guilds is not None:
            entry['guilds'] = guilds
            entry['fetched_at'] = time.time()
            entry['retry_at'] = 0.0
        return entry


def _entry(user_id):
    return _cache.get(user_id)


def _refresh(user_id, entry):
    token = entry['token']
    now = time.time()
    try:
        if not token:
            raise DiscordError('no token', 401)
        if token.get('expires_at', 0) - 60 < now:
            if not token.get('refresh_token'):
                raise DiscordError('access token expired', 401)
            token = refresh_access_token(token['refresh_token'])
            entry['token'] = token
        guilds = fetch_guilds(token['access_token'])
    except DiscordError as e:
        log.warning("web: could not refresh Discord guilds for %s: %s", user_id, e)
        if e.status in _TOKEN_DEAD:
            # 用户取消了授权 / refresh token 失效(invalid_grant):不能再按旧列表给权限
            entry['guilds'] = []
            entry['token'] = None
            entry['fetched_at'] = now
            entry['retry_at'] = now + GUILDS_TTL
            return
        entry['retry_at'] = now + (e.retry_after if e.retry_after else FAILURE_BACKOFF)
        return
    entry['guilds'] = guilds
    entry['fetched_at'] = time.time()
    entry['retry_at'] = 0.0


def discord_user_id(identity=None):
    """Discord 登录的 user id(字符串);identity 不是 Discord 登录的返回 None。
    identity 省略时用当前请求的会话。"""
    if identity is None:
        user = session_user()
        return user['id'] if user else None
    if isinstance(identity, (str, int)):
        return str(identity) or None
    return getattr(identity, 'discord_id', None)


def discord_guilds(identity=None, refresh=False):
    """这个 Discord 用户所在的服务器:[{id, name, icon, owner, permissions}],id 是字符串,
    permissions 是整数位域。超过 GUILDS_TTL 或 refresh=True 时先同步拉一次(暂时失败就用旧的,
    但旧过 2*GUILDS_TTL 就不认了)。不是 Discord 登录 / 没有 token 时返回 []。"""
    user_id = discord_user_id(identity)
    if not user_id:
        return []
    entry = _entry(user_id)
    if entry is None:
        return []
    now = time.time()
    stale = refresh or now - entry['fetched_at'] > GUILDS_TTL
    # 别的线程正在拉就直接用旧数据,不排队
    if stale and now >= entry['retry_at'] and entry['lock'].acquire(blocking=False):
        try:
            _refresh(user_id, entry)
        finally:
            entry['lock'].release()
    if time.time() - entry['fetched_at'] > 2 * GUILDS_TTL:
        return []
    return [dict(g) for g in entry['guilds']]


def find_guild(identity, guild_id):
    guild_id = str(guild_id)
    return next((g for g in discord_guilds(identity) if g['id'] == guild_id), None)


def can_manage(guild):
    """服务器主人,或有 管理员 / 管理服务器 权限。guild 是 discord_guilds() 里的一项。"""
    if not guild:
        return False
    if guild.get('owner'):
        return True
    try:
        perms = int(guild.get('permissions') or 0)
    except (TypeError, ValueError):
        return False
    return bool(perms & (PERM_ADMINISTRATOR | PERM_MANAGE_GUILD))


def bot_guild_ids():
    """bot 服务的服务器 id(字符串集合);bot 还没连上时为空。有 Hub 时是 Hub 管的全部服务器。"""
    hub = getattr(var, 'hub', None)
    if hub is not None:
        return {str(gid) for gid in hub.guild_ids()}
    link = getattr(getattr(var, 'bot', None), 'link', None)
    guild_id = getattr(link, 'guild_id', None)
    return {str(guild_id)} if guild_id else set()


def is_bot_owner(identity=None):
    """[bot] admin 里列了这个 Discord 账号:bot 主人,和 bot 不在同一服务器也能进。"""
    import web_context

    user_id = discord_user_id(identity)
    return bool(user_id) and user_id in web_context.owner_ids()


def shares_guild_with_bot(identity=None):
    if is_bot_owner(identity):
        return True
    bot_ids = bot_guild_ids()
    return bool(bot_ids) and any(g['id'] in bot_ids for g in discord_guilds(identity))


def forget(user_id):
    with _cache_lock:
        _cache.pop(str(user_id), None)


# =====================================================================
#  会话 / 身份
# =====================================================================

def session_user():
    """当前请求里登录的 Discord 用户 {id, username, global_name, avatar};没有返回 None。
    关掉 Discord 登录(删了 client id/secret)后旧会话一律不认;服务端没有这个人的 token
    (重启过 / 被挤出缓存)的会话也不认,重新登录一次。"""
    if not has_request_context() or not configured():
        return None
    # Activity 的 Bearer 令牌(web_activity.check_bearer 校验过才会有)
    bearer_user = getattr(request_globals, 'activity_user', None)
    if bearer_user:
        return bearer_user
    if LEGACY_SESSION_TOKEN in session:
        session.pop(LEGACY_SESSION_TOKEN, None)
    user = session.get(SESSION_USER)
    if not user or not user.get('id') or _entry(str(user['id'])) is None:
        return None
    return user


def display_name(user):
    return user.get('global_name') or user.get('username') or user.get('id') or 'Discord'


def discord_key(user_id):
    return f"discord:{user_id}"


def identity_key_for(user):
    """Discord 用户 -> Web 身份键。绑定过就用绑定的身份,否则 discord:<id>。"""
    key = discord_key(user['id'])
    if var.user_db is None:
        return key
    try:
        return var.user_db.identity_for_discord(key) or key
    except Exception:
        log.debug("web: discord_link lookup failed for %s", key, exc_info=True)
        return key


def _link_on_login(user):
    """登录时:没绑定过就把 discord:<id> 记成自己的身份;新身份顺便用 Discord 名字当别名。"""
    key = discord_key(user['id'])
    if var.user_db is None:
        return key
    try:
        identity, created = var.user_db.link_discord_login(key, display_name(user))
    except Exception:
        log.warning("web: could not link Discord login %s", key, exc_info=True)
        return key
    if created and not var.user_db.get_alias(identity):
        import web_users
        try:
            var.user_db.set_alias(identity, web_users._validate_alias_text(display_name(user)))
        except Exception:
            pass  # 名字不合法或被占用:显示名退回 Discord 名字,不影响登录
    return identity


# =====================================================================
#  门禁辅助(interface.requires_auth 调用)
# =====================================================================

def _wants_json():
    return request.path.startswith('/api/')


def _preferred_type():
    return request.accept_mimetypes.best_match(['application/json', 'text/html'])


def _prefers_json():
    return _preferred_type() == 'application/json'


def _prefers_html():
    return _preferred_type() == 'text/html'


# 会话里有这些就算还登录着(Discord 登录、令牌登录)
_LOGIN_KEYS = (SESSION_USER, 'user', 'token')


def _page(title, message, status=200, show_login=False, show_logout=False):
    from constants import tr_web

    return render_template(
        'need_token.html',
        lang=(var.language or 'en').split('_')[0],
        title=title,
        message=message,
        discord_login_url=login_url() if show_login and configured() else None,
        discord_login_label=tr_web('login_with_discord'),
        logout_url=request.script_root + '/auth/logout' if show_logout else None,
        logout_label=tr_web('logout'),
    ), status


def unauthenticated():
    """没登录:API 返回 401 JSON,网页跳去 Discord 登录(登录完回到原来的地址)。"""
    if _wants_json():
        return jsonify({'error': 'login_required', 'login_url': login_url()}), 401
    next_path = request.full_path if request.query_string else request.path
    return redirect(login_url(request.script_root + next_path), code=302)


def forbidden():
    from constants import tr_web

    if _wants_json():
        return jsonify({'error': 'not_a_member'}), 403
    return _page(tr_web('discord_not_member'), tr_web('discord_not_member_message'), 403, show_logout=True)


# =====================================================================
#  路由
# =====================================================================

def create_blueprint():
    from web_security import rate_limited

    bp = Blueprint('auth_discord', __name__)

    @bp.route('/auth/discord/login', methods=['GET'])
    @rate_limited('discord_auth')
    def login():
        if not configured():
            return jsonify({'error': 'discord_login_not_configured'}), 404
        state = secrets.token_urlsafe(24)
        session[SESSION_STATE] = state
        next_path = _safe_next(request.args.get('next'))
        if next_path:
            session[SESSION_NEXT] = next_path
        else:
            session.pop(SESSION_NEXT, None)
        params = {
            'response_type': 'code',
            'client_id': client_id(),
            'scope': SCOPES,
            'state': state,
            'redirect_uri': redirect_uri(),
            # 授权过就不再弹确认页;Discord 要求交互时回调会带 error,再用 consent 重来一次
            'prompt': 'consent' if request.args.get('prompt') == 'consent' else 'none',
        }
        return redirect(AUTHORIZE_URL + '?' + urlencode(params), code=302)

    @bp.route('/auth/discord/callback', methods=['GET'])
    @rate_limited('discord_auth')
    def callback():
        from constants import tr_web

        if not configured():
            return jsonify({'error': 'discord_login_not_configured'}), 404
        expected = session.pop(SESSION_STATE, None)
        next_path = session.pop(SESSION_NEXT, None)
        state = request.args.get('state', '')
        failed = (tr_web('discord_login_failed'), tr_web('discord_login_failed_message'))
        if not expected or not hmac.compare_digest(state.encode(), expected.encode()):
            log.info("web: Discord login with bad state from %s", request.remote_addr)
            return _page(*failed, status=400, show_login=True)
        if request.args.get('error') in _NEEDS_INTERACTION:
            query = {'prompt': 'consent'}
            if next_path:
                query['next'] = next_path
            return redirect(request.script_root + '/auth/discord/login?' + urlencode(query), code=302)
        if request.args.get('error') or not request.args.get('code'):
            # 用户在 Discord 上点了取消(error=access_denied)
            return _page(*failed, status=400, show_login=True)
        try:
            token = exchange_code(request.args['code'])
            user = fetch_user(token['access_token'])
            guilds = fetch_guilds(token['access_token'])
        except DiscordError as e:
            log.warning("web: Discord login failed: %s", e)
            return _page(*failed, status=502, show_login=True)

        identity = _link_on_login(user)
        _store(user['id'], token=token, guilds=guilds)
        session.clear()
        session.permanent = True
        session[SESSION_USER] = user
        log.info("web: %s (discord:%s) logged in with Discord as %s from %s",
                 display_name(user), user['id'], identity, request.remote_addr)
        return redirect(_safe_next(next_path) or request.script_root + '/', code=302)

    @bp.route('/auth/logout', methods=['GET', 'POST'])
    def logout():
        """只有 POST 退出(GET 能被别的网站用 <img> / 链接触发)。GET:还登录着就给一个退出按钮,
        已经退出了(前端先 POST 再跳过来)就是"已退出"页面。"""
        from constants import tr_web

        if request.method == 'POST':
            session.clear()
            if not _prefers_html():
                return jsonify({'ok': True})
        elif _prefers_json():
            return jsonify({'error': 'method_not_allowed'}), 405
        elif any(key in session for key in _LOGIN_KEYS):
            action = escape(request.script_root + '/auth/logout')
            form = Markup(f'<form method="post" action="{action}">'
                          f'<button type="submit">{escape(tr_web("logout"))}</button></form>')
            return _page(tr_web('logout'), form)
        if configured():
            # 不直接回首页:门禁会立刻跳去 Discord,prompt=none 又把人登录回来
            return _page(tr_web('logged_out'), tr_web('logged_out_message'), show_login=True)
        return redirect(request.script_root + '/', code=302)

    return bp
