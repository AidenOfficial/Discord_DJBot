"""Discord Activity(Embedded App SDK 的 iframe)里的控制面板:登录换令牌、Bearer 鉴权、外部图片代理。

Activity 只是个遥控器:声音照旧由 bot 推进语音频道,iframe 里显示打开它的那个服务器的队列 / 搜索 / 控制。

登录流程(前端 webui/src/activity.ts):
  SDK authorize() 拿到 code → POST /api/activity/token {code, guild_id, channel_id}
  → 服务端用 client secret 换 Discord access token,读 /users/@me 和 /users/@me/guilds
  → 核对 SDK 给的服务器和语音频道(客户端说的不算:用户必须是这个服务器的成员,
     并且按 bot 网关的语音状态,此刻就在这个语音频道里)
  → 发我们自己的短期 Bearer 令牌(itsdangerous 签名 + 过期时间 + jti,可撤销),
     同时把 Discord access token 交回去给 SDK 的 authenticate() 用。
前端只把令牌放在内存里,每个 API 请求带 Authorization: Bearer <令牌>(iframe 里第三方 Cookie 不可靠)。

- 令牌是 Discord 登录:身份、bot 主人判断、按服务器的权限都和 /auth/discord/login 登录的一样
  (web_context 的规则),令牌里的服务器作为默认服务器,也一定在允许列表里(签发时核对过)。
- 撤销:单个令牌按 jti(登出 / 刷新时旧令牌作废),或一个 Discord 账号此前发的全部令牌。
  撤销记录存在设置库里,重启后照样有效;过期的记录顺手清掉。
- [webinterface] activity_enabled = False 时这些都不存在(接口 404,Bearer 一律不认)。
"""

import ipaddress
import logging
import secrets
import threading
import time
from collections import OrderedDict
from urllib.parse import urlparse

import requests
from flask import Blueprint, Response, abort, current_app, g, has_request_context, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

import variables as var
import web_auth_discord

log = logging.getLogger("bot")

TOKEN_SALT = 'djbot-activity-token'
TOKEN_VERSION = 1
DEFAULT_TTL = 900
MIN_TTL = 60
MAX_TTL = 86400
REVOKED_SECTION = 'activity_revoked'            # jti -> 过期时间
REVOKED_USER_SECTION = 'activity_revoked_user'  # Discord user id -> 撤销时间(之前签发的都不认)
ACTIVITY_SCOPES = ('identify', 'guilds')

# Discord 打开 Activity 时 iframe 地址里带的参数
LAUNCH_PARAMS = ('frame_id', 'instance_id')


# =====================================================================
#  配置
# =====================================================================

def enabled():
    if var.config is None:
        return False
    try:
        on = var.config.getboolean('webinterface', 'activity_enabled', fallback=False)
    except ValueError:
        on = False
    return on and web_auth_discord.configured()


def token_ttl():
    try:
        ttl = var.config.getint('webinterface', 'activity_token_ttl', fallback=DEFAULT_TTL)
    except ValueError:
        ttl = DEFAULT_TTL
    return max(MIN_TTL, min(MAX_TTL, ttl))


def _serializer():
    return URLSafeTimedSerializer(current_app.secret_key, salt=TOKEN_SALT)


# =====================================================================
#  撤销
# =====================================================================

_revoked_lock = threading.Lock()
_revoked = {'db': None, 'jti': {}, 'user': {}}


def _revocations():
    """撤销表(内存一份,和设置库同步;换了库——测试——就重新读)。调用方持有 _revoked_lock。"""
    db = var.db
    if _revoked['db'] is not db:
        jti, user = {}, {}
        if db is not None:
            try:
                jti = {k: float(v) for k, v in db.items(REVOKED_SECTION)}
                user = {k: float(v) for k, v in db.items(REVOKED_USER_SECTION)}
            except Exception:
                log.warning("web: could not load revoked Activity tokens", exc_info=True)
        _revoked.update(db=db, jti=jti, user=user)
    return _revoked


def revoke(jti, expires_at):
    """作废一个令牌(到它本来的过期时间为止)。"""
    now = time.time()
    with _revoked_lock:
        table = _revocations()
        table['jti'][jti] = float(expires_at)
        db = table['db']
        if db is not None:
            db.set(REVOKED_SECTION, jti, str(float(expires_at)))
        for old in [k for k, exp in table['jti'].items() if exp < now]:
            table['jti'].pop(old, None)
            if db is not None:
                db.remove_option(REVOKED_SECTION, old)


def revoke_user(discord_id):
    """作废这个 Discord 账号到现在为止签发的所有 Activity 令牌。"""
    now = time.time()
    with _revoked_lock:
        table = _revocations()
        table['user'][str(discord_id)] = now
        if table['db'] is not None:
            table['db'].set(REVOKED_USER_SECTION, str(discord_id), str(now))


def _is_revoked(claims):
    with _revoked_lock:
        table = _revocations()
        if claims['jti'] in table['jti']:
            return True
        since = table['user'].get(str(claims['u']['id']))
        return since is not None and claims['iat'] <= since


# =====================================================================
#  令牌
# =====================================================================

def issue(user, guild_id, channel_id):
    """签发令牌 → (令牌, 过期时间戳)。user 是 fetch_user() 的结果。"""
    now = time.time()
    claims = {
        'v': TOKEN_VERSION,
        'jti': secrets.token_urlsafe(16),
        'iat': now,
        'exp': now + token_ttl(),
        'u': {k: user.get(k) or '' for k in ('id', 'username', 'global_name', 'avatar')},
        'g': str(guild_id),
        'c': str(channel_id),
    }
    return _serializer().dumps(claims), claims['exp']


def verify(token):
    """令牌有效 → claims;签名不对 / 过期 / 已撤销 → None。"""
    if not token or len(token) > 4096:
        return None
    try:
        # max_age 和 exp 双保险:改小了 activity_token_ttl,已经发出去的长令牌也立刻按新的算
        claims = _serializer().loads(token, max_age=token_ttl())
    except SignatureExpired:
        return None
    except BadSignature:
        return None
    if not isinstance(claims, dict) or claims.get('v') != TOKEN_VERSION:
        return None
    try:
        if float(claims['exp']) < time.time() or not claims['u'].get('id') or not claims.get('g'):
            return None
    except (KeyError, TypeError, ValueError, AttributeError):
        return None
    if _is_revoked(claims):
        return None
    return claims


def bearer_token():
    header = request.headers.get('Authorization', '')
    scheme, _, value = header.partition(' ')
    if scheme.lower() != 'bearer':
        return None
    return value.strip() or None


def current_claims():
    """这个请求用的 Activity 令牌(已校验);不是 Bearer 登录返回 None。"""
    if not has_request_context():
        return None
    return getattr(g, 'activity_claims', None)


def current_guild_id():
    claims = current_claims()
    return claims['g'] if claims else None


def check_bearer():
    """requires_auth 一开头调用:
    - 没带 Bearer(或 Activity 没开)→ None,走原来的登录方式;
    - Bearer 有效 → True(身份已经挂在 g 上);
    - Bearer 无效 / 过期 / 撤销 → 401 JSON 响应。"""
    if not enabled():
        return None
    token = bearer_token()
    if token is None:
        return None
    claims = verify(token)
    if claims is None:
        return jsonify({'error': 'activity_token_invalid'}), 401
    g.activity_claims = claims
    # web_auth_discord.session_user() 看到这个就当成 Discord 登录
    g.activity_user = dict(claims['u'])
    return True


def serves_shell():
    """Activity 开着时,iframe 第一次打开页面还没有令牌:index.html(带着 Discord 的启动参数)和打包好的
    静态资源不用登录。里面没有数据,数据都在要令牌的 /api/ 后面。"""
    if not enabled():
        return False
    if request.path.startswith('/assets/'):
        return True
    return all(request.args.get(p) for p in LAUNCH_PARAMS)


# =====================================================================
#  核对 SDK 给的上下文
# =====================================================================

class Rejected(Exception):
    def __init__(self, error, status=403):
        super().__init__(error)
        self.error = error
        self.status = status


def _hub():
    return getattr(var, 'hub', None)


def voice_channel_of(guild_id, user_id):
    """按 bot 网关的语音状态,这个用户现在在哪个语音频道(字符串 id);不在语音里 / 查不到 → None。"""
    h = _hub()
    if h is not None:
        channel = h.voice_channel_of(guild_id, user_id)
        return str(channel) if channel else None
    link = getattr(getattr(var, 'bot', None), 'link', None)
    if link is None or str(getattr(link, 'guild_id', '')) != str(guild_id):
        return None
    try:
        user = link.users.get(int(user_id))
    except (TypeError, ValueError):
        return None
    channel = getattr(user, 'channel_id', None) if user is not None else None
    return str(channel) if channel else None


def is_member(guild_id, user_id, oauth_guilds):
    if any(gd['id'] == guild_id for gd in oauth_guilds):
        return True
    h = _hub()
    if h is not None:
        try:
            return bool(h.is_member(guild_id, user_id))
        except Exception:
            log.debug("web: is_member(%s, %s) failed", guild_id, user_id, exc_info=True)
    return False


def check_context(user_id, guild_id, channel_id, oauth_guilds):
    """guild / channel 是 SDK 在客户端给的,一律按服务端知道的核对;不对就抛 Rejected。"""
    if guild_id not in web_auth_discord.bot_guild_ids():
        raise Rejected('guild_not_served')
    if not is_member(guild_id, user_id, oauth_guilds):
        raise Rejected('not_a_member')
    if voice_channel_of(guild_id, user_id) != channel_id:
        raise Rejected('not_in_voice_channel')


def _snowflake(value):
    value = str(value or '').strip()
    return value if value.isdigit() and len(value) <= 20 else None


# =====================================================================
#  外部图片代理
# =====================================================================

# Activity 的 iframe 只能访问自己的域名(其他域名要在 Developer Portal 一个个登记 URL Mapping),
# 所以封面、头像、服务器图标都从这里转一道。只代理这些图床,防 SSRF。
IMAGE_HOSTS = ('ytimg.com', 'ggpht.com', 'googleusercontent.com', 'hdslb.com',
               'cdn.discordapp.com', 'media.discordapp.net', 'scdn.co', 'sndcdn.com')
IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif', 'image/avif'}
IMAGE_MAX_BYTES = 4 * 1024 * 1024
IMAGE_CACHE_MAX = 256
IMAGE_CACHE_TTL = 3600
IMAGE_TIMEOUT = 8

_image_lock = threading.Lock()
_image_cache = OrderedDict()  # url -> (取到的时间, content type, bytes)


def allowed_image_url(url):
    try:
        parsed = urlparse(url or '')
    except ValueError:
        return False
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        return False
    if parsed.port not in (None, 443):
        return False
    host = parsed.hostname.lower().rstrip('.')
    try:
        ipaddress.ip_address(host)
        return False  # 不认 IP 地址
    except ValueError:
        pass
    return any(host == h or host.endswith('.' + h) for h in IMAGE_HOSTS)


def _fetch_image(url):
    with _image_lock:
        hit = _image_cache.get(url)
        if hit is not None and time.time() - hit[0] < IMAGE_CACHE_TTL:
            _image_cache.move_to_end(url)
            return hit[1], hit[2]
    try:
        # 不跟随重定向:跳到哪里都可能(包括内网),要跟就得再核对一次,图床基本不跳
        resp = requests.get(url, timeout=IMAGE_TIMEOUT, stream=True, allow_redirects=False,
                            headers={'User-Agent': 'Discord-DJBot image proxy'})
    except requests.RequestException as e:
        log.debug("web: image proxy failed for %s: %s", url, e)
        return None
    try:
        ctype = (resp.headers.get('Content-Type') or '').split(';')[0].strip().lower()
        if resp.status_code != 200 or ctype not in IMAGE_TYPES:
            return None
        data = b''
        for chunk in resp.iter_content(64 * 1024):
            data += chunk
            if len(data) > IMAGE_MAX_BYTES:
                return None
    except requests.RequestException:
        return None
    finally:
        resp.close()
    with _image_lock:
        _image_cache[url] = (time.time(), ctype, data)
        _image_cache.move_to_end(url)
        while len(_image_cache) > IMAGE_CACHE_MAX:
            _image_cache.popitem(last=False)
    return ctype, data


# =====================================================================
#  路由
# =====================================================================

def _error(error, status):
    return jsonify({'error': error}), status


def create_blueprint(requires_auth):
    api = Blueprint('activity', __name__, url_prefix='/api')

    @api.route('/activity/config', methods=['GET'])
    def activity_config():
        """前端初始化 SDK 要 client id(公开信息)。Activity 没开 → enabled false。"""
        if not enabled():
            return jsonify({'enabled': False})
        return jsonify({'enabled': True, 'client_id': web_auth_discord.client_id(),
                        'scopes': list(ACTIVITY_SCOPES), 'token_ttl': token_ttl()})

    @api.route('/activity/token', methods=['POST'])
    def activity_token():
        if not enabled():
            abort(404)
        body = request.get_json(silent=True) or {}
        code = body.get('code')
        guild_id = _snowflake(body.get('guild_id'))
        channel_id = _snowflake(body.get('channel_id'))
        if not isinstance(code, str) or not code or len(code) > 512:
            return _error('code_required', 400)
        if guild_id is None or channel_id is None:
            # 私信 / 群组里打开的 Activity 没有服务器,bot 没法在那里放歌
            return _error('guild_required', 400)
        try:
            token = web_auth_discord.exchange_activity_code(code)
            user = web_auth_discord.fetch_user(token['access_token'])
            guilds = web_auth_discord.fetch_guilds(token['access_token'])
        except web_auth_discord.DiscordError as e:
            log.warning("web: Activity login failed: %s", e)
            if e.status in (400, 401):
                return _error('discord_auth_failed', 401)
            return _error('discord_unavailable', 502)
        try:
            check_context(user['id'], guild_id, channel_id, guilds)
        except Rejected as e:
            log.info("web: Activity login of discord:%s for %s/%s refused: %s",
                     user['id'], guild_id, channel_id, e.error)
            return _error(e.error, e.status)

        identity = web_auth_discord._link_on_login(user)
        web_auth_discord._store(user['id'], token=token, guilds=guilds)
        ours, expires_at = issue(user, guild_id, channel_id)
        log.info("web: %s (discord:%s) opened the Activity in %s/%s as %s",
                 web_auth_discord.display_name(user), user['id'], guild_id, channel_id, identity)
        return jsonify({
            'token': ours,
            'expires_at': expires_at,
            'expires_in': int(expires_at - time.time()),
            'guild_id': guild_id,
            'channel_id': channel_id,
            # SDK 的 authenticate() 要 Discord 的 access token
            'access_token': token['access_token'],
            'user': user,
        })

    @api.route('/activity/refresh', methods=['POST'])
    @requires_auth
    def activity_refresh():
        """换一个新令牌(旧的作废)。重新核对语音频道:人已经离开了就不续。"""
        claims = current_claims()
        if claims is None:
            return _error('activity_token_required', 401)
        user = claims['u']
        guilds = web_auth_discord.discord_guilds()
        try:
            check_context(user['id'], claims['g'], claims['c'], guilds)
        except Rejected as e:
            revoke(claims['jti'], claims['exp'])
            return _error(e.error, e.status)
        ours, expires_at = issue(user, claims['g'], claims['c'])
        revoke(claims['jti'], claims['exp'])
        return jsonify({'token': ours, 'expires_at': expires_at,
                        'expires_in': int(expires_at - time.time()),
                        'guild_id': claims['g'], 'channel_id': claims['c']})

    @api.route('/activity/logout', methods=['POST'])
    @requires_auth
    def activity_logout():
        claims = current_claims()
        if claims is None:
            return _error('activity_token_required', 401)
        revoke(claims['jti'], claims['exp'])
        return jsonify({'ok': True})

    @api.route('/thumbnail/external', methods=['GET'])
    @requires_auth
    def external_thumbnail():
        url = request.args.get('url', '')
        if not allowed_image_url(url):
            abort(400)
        result = _fetch_image(url)
        if result is None:
            abort(404)
        ctype, data = result
        return Response(data, mimetype=ctype, headers={
            'Cache-Control': 'private, max-age=86400',
            'X-Content-Type-Options': 'nosniff',
        })

    return api

