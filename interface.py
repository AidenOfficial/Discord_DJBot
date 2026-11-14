#!/usr/bin/python3
import hmac
import html
import ipaddress
import json
import logging
import os
import time
from functools import wraps
from urllib.parse import urlparse

from flask import Flask, render_template, request, redirect, send_from_directory, Response, abort, session, g, \
    jsonify

import util
import variables as var
from constants import tr_web


# 默认信任回环和私有网段:cloudflared / nginx 一般在同一个 docker 网络里,地址不固定
DEFAULT_TRUSTED_PROXIES = "127.0.0.0/8, ::1/128, 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7"


def parse_networks(value):
    networks = []
    for part in (value or '').split(','):
        part = part.strip()
        if not part:
            continue
        try:
            networks.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            logging.getLogger("bot").warning("web: ignoring invalid [webinterface] trusted_proxies entry %r", part)
    return networks


def _parse_ip(value):
    try:
        addr = ipaddress.ip_address((value or '').strip())
    except ValueError:
        return None
    if addr.version == 6 and addr.ipv4_mapped:
        return addr.ipv4_mapped
    return addr


class ReverseProxied(object):
    """Wrap the application in this middleware and configure the
    front-end server to add these headers, to let you quietly bind
    this to a URL other than / and to an HTTP scheme that is
    different than what is used locally.

    In nginx:
    location /myprefix {
        proxy_pass http://192.168.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Scheme $scheme;
        proxy_set_header X-Script-Name /myprefix;
        }

    The headers are only believed when the socket peer is in [webinterface] trusted_proxies.
    X-Script-Name / X-Scheme additionally need [webinterface] honor_script_name = True: behind
    Cloudflare any visitor could send them, poison the cache, or reach /api/logs as /zz/api/logs
    past a path-based Access policy.

    :param app: the WSGI application
    """

    def __init__(self, app, trusted_proxies=None, honor_script_name=None):
        self.app = app
        conf = var.config
        if trusted_proxies is None:
            trusted_proxies = conf.get('webinterface', 'trusted_proxies', fallback='') if conf is not None else ''
        if honor_script_name is None:
            honor_script_name = conf.getboolean('webinterface', 'honor_script_name', fallback=False) \
                if conf is not None else False
        # 留空等于默认;一个代理都不信就把 is_web_proxified 关掉
        self.trusted = parse_networks((trusted_proxies or '').strip() or DEFAULT_TRUSTED_PROXIES)
        self.honor_script_name = honor_script_name

    def is_trusted(self, remote_addr):
        addr = _parse_ip(remote_addr)
        return addr is not None and any(addr in net for net in self.trusted)

    def __call__(self, environ, start_response):
        if not self.is_trusted(environ.get('REMOTE_ADDR')):
            return self.app(environ, start_response)

        if self.honor_script_name:
            script_name = environ.get('HTTP_X_SCRIPT_NAME', '')
            if script_name:
                environ['SCRIPT_NAME'] = script_name
                path_info = environ.get('PATH_INFO', '')
                if path_info.startswith(script_name):
                    environ['PATH_INFO'] = path_info[len(script_name):]

            scheme = environ.get('HTTP_X_SCHEME', '').lower()
            if scheme in ('http', 'https'):
                environ['wsgi.url_scheme'] = scheme
        # 访问者的真实 IP:Cloudflare Tunnel(cloudflared)放在 Cf-Connecting-IP,nginx 一般用 X-Real-IP。
        # 不认的话所有人都是 cloudflared 容器的地址,输错令牌的 IP 封禁会把所有人一起封掉
        real_ip = _parse_ip(environ.get('HTTP_CF_CONNECTING_IP', '') or environ.get('HTTP_X_REAL_IP', ''))
        if real_ip is not None:
            environ['REMOTE_ADDR'] = str(real_ip)
        return self.app(environ, start_response)


import web_activity
import web_api
import web_auth_discord
import web_cache
import web_channels
import web_guilds
import web_library
import web_logs
import web_security
import web_upload
import web_users

root_dir = os.path.dirname(__file__)
web = Flask(__name__, template_folder=os.path.join(root_dir, "templates"))
# API 的请求体都是小 JSON;上传分片的路由自己放宽这个上限
web.config['MAX_CONTENT_LENGTH'] = 1024 * 1024
log = logging.getLogger("bot")


def init_proxy():
    if var.is_proxified:
        web.wsgi_app = ReverseProxied(web.wsgi_app)


# https://stackoverflow.com/questions/29725217/password-protect-one-webpage-in-flask-app


def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """

    # 配置里的账号:两项都填了才生效,否则空用户名+空密码的 Basic Auth 也能登录
    conf_user = var.config.get("webinterface", "user")
    conf_password = var.config.get("webinterface", "password")
    if conf_user and conf_password and \
            hmac.compare_digest((username or "").encode(), conf_user.encode()) and \
            hmac.compare_digest((password or "").encode(), conf_password.encode()):
        return True

    web_users = json.loads(var.db.get("privilege", "web_access", fallback='[]'))
    if username in web_users:
        user_dict = json.loads(var.db.get("user", username, fallback='{}'))
        if 'password' in user_dict and 'salt' in user_dict and \
                util.verify_password(password, user_dict['password'], user_dict['salt']):
            return True

    return False


def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response('Could not verify your access level for that URL.\n'
                    'You have to login with proper credentials', 401,
                    {'WWW-Authenticate': 'Basic realm="Login Required"'})


# 输错令牌 / 密码的次数和封禁(ip -> 到期时间,time.monotonic())。
# 封禁只拦再拿凭据来试的请求,已登录的会话照常用(见 web_security 里的说明)
bad_access_count = {}
banned_ip = {}


def reset_bans():
    bad_access_count.clear()
    banned_ip.clear()


def _ip_banned(ip):
    until = banned_ip.get(ip)
    if until is None:
        return False
    if time.monotonic() >= until:
        banned_ip.pop(ip, None)
        bad_access_count.pop(ip, None)
        return False
    return True


def _log_safe(value):
    # 用户名、IP(来自请求头)都是访问者给的:去掉换行,免得伪造出多行日志
    return str(value).replace('\r', '').replace('\n', '')[:200]


def _record_failure(ip, what):
    count = bad_access_count.get(ip, 0) + 1
    bad_access_count[ip] = count
    log.info("web: %s from ip %s, %d attempts.", _log_safe(what), _log_safe(ip), count)
    if count > var.config.getint("webinterface", "max_attempts", fallback=10):
        seconds = web_security.ban_seconds()
        banned_ip[ip] = time.monotonic() + seconds
        log.info("web: login attempts from %s blocked for %d min", _log_safe(ip), seconds // 60)


def _with_identity(f, auth_user, args, kwargs):
    # 鉴权通过后解析身份(Cloudflare Access 邮箱 / Web 用户名),供点歌署名和个人歌单使用
    g.web_identity = web_users.resolve_identity(auth_user)
    return f(*args, **kwargs)


AUTH_METHODS = ('none', 'password', 'token', 'discord')
_bad_auth_methods_logged = set()


def configured_auth_method():
    """规范化后的 auth_method。不认识的值(包括留空)不在 AUTH_METHODS 里:requires_auth 一律拒绝,不当成 none。"""
    return (var.config.get("webinterface", "auth_method", fallback='') or '').strip().lower()


def _log_bad_auth_method(value):
    if value not in _bad_auth_methods_logged:
        _bad_auth_methods_logged.add(value)
        log.error("web: unknown [webinterface] auth_method %r (expected one of %s), refusing web requests",
                  _log_safe(value), ', '.join(AUTH_METHODS))


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Discord Activity 的 Bearer 令牌:开了 Activity 就认,不管 auth_method 是什么。
        # 这里不按 IP 封禁:Activity 的请求都来自 Discord 代理的 IP,封一个 IP 等于封所有人;
        # 输错令牌 / 密码的 IP 封禁只拦登录尝试(见下面各分支)
        bearer = web_activity.check_bearer()
        if bearer is True:
            return _with_identity(f, None, args, kwargs)
        if bearer is not None:
            return bearer

        auth_method = configured_auth_method()
        if auth_method not in AUTH_METHODS:
            _log_bad_auth_method(auth_method)
            return jsonify({'error': 'auth_misconfigured'}), 503

        if auth_method == 'discord':
            if web_auth_discord.session_user() is None:
                return web_auth_discord.unauthenticated()
            if not web_auth_discord.shares_guild_with_bot():
                return web_auth_discord.forbidden()
            return _with_identity(f, None, args, kwargs)

        if auth_method == 'password':
            auth = request.authorization
            if not auth:
                return authenticate()
            if _ip_banned(request.remote_addr):
                abort(403)
            if not check_auth(auth.username, auth.password):
                _record_failure(request.remote_addr, f"failed login attempt, user: {auth.username}")
                return authenticate()
        if auth_method == 'token':
            # 配置了 Discord 登录时,和 bot 在同一服务器的 Discord 账号可以代替令牌
            if web_auth_discord.session_user() is not None and 'token' not in request.args \
                    and web_auth_discord.shares_guild_with_bot():
                return _with_identity(f, None, args, kwargs)
            if 'user' in session and 'token' not in request.args:
                return _with_identity(f, session['user'], args, kwargs)
            elif 'token' in request.args:
                if _ip_banned(request.remote_addr):
                    abort(403)
                wait = web_security.check('token')
                if wait:
                    return web_security.too_many(wait)
                token = request.args.get('token')
                token_user = var.db.get("web_token", token, fallback=None)
                if token_user is not None:
                    user_info = var.db.get("user", token_user, fallback=None)
                    user_dict = json.loads(user_info)
                    user_dict['IP'] = request.remote_addr
                    var.db.set("user", token_user, json.dumps(user_dict))

                    log.debug(
                        f"web: new user access, token validated for the user: {token_user}, from ip {request.remote_addr}.")
                    session['token'] = token
                    session['user'] = token_user
                    return _with_identity(f, token_user, args, kwargs)

                _record_failure(request.remote_addr, "bad token")

            command = "/" + (var.bot.command_name('requests_webinterface_access') if var.bot else 'web')
            bot_name = (var.bot.link.bot_name if var.bot else '') or 'the bot'
            discord_login = web_auth_discord.configured()
            return render_template('need_token.html',
                                   lang=var.language.split('_')[0],
                                   title=tr_web('token_required'),
                                   message=tr_web('token_required_message',
                                                  name=html.escape(bot_name),
                                                  command=html.escape(command)),
                                   token_label=tr_web('token'),
                                   submit=tr_web('submit'),
                                   discord_login_url=web_auth_discord.login_url(request.script_root + request.path)
                                   if discord_login else None,
                                   discord_login_label=tr_web('login_with_discord') if discord_login else None)

        auth_user = request.authorization.username \
            if auth_method == 'password' and request.authorization else None
        return _with_identity(f, auth_user, args, kwargs)

    return decorated


@web.after_request
def _security_headers(response):
    return web_security.apply_security_headers(response)


# 跨站表单 / no-cors fetch 不经过 CORS 预检就能发的 Content-Type
CSRF_SIMPLE_CONTENT_TYPES = ('application/x-www-form-urlencoded', 'multipart/form-data', 'text/plain')
CSRF_SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')


def _origin_of(url):
    parts = urlparse(url)
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}".lower()


def allowed_origins():
    public_url = (var.config.get('webinterface', 'public_url', fallback='') or '').strip()
    origins = {_origin_of(public_url) or _origin_of(request.host_url)}
    if web_activity.enabled():
        # Activity 的 iframe 由 Discord 代理成 https://<app id>.discordsays.com,请求从那里同源发出
        origins.add(f"https://{web_auth_discord.client_id()}.discordsays.com".lower())
    return origins


def _csrf_rejected():
    return jsonify({'error': 'csrf'}), 403


@web.before_request
def _csrf_protect():
    """会话 Cookie / Basic Auth 是浏览器自动带的:改状态的请求必须来自本站。
    带 Bearer 的(Activity)不靠 Cookie,不用查。"""
    if request.method in CSRF_SAFE_METHODS:
        return None
    if not (request.path.startswith('/api/') or request.path.startswith('/auth/')):
        return None
    # 只有 requires_auth 真的会用这个 Bearer 时才跳过:Activity 没开(或 /auth/ 下)它会退回去用 Cookie
    if request.path.startswith('/api/') and web_activity.enabled() and web_activity.bearer_token() is not None:
        return None
    fetch_site = request.headers.get('Sec-Fetch-Site')
    if fetch_site is not None and fetch_site.lower() not in ('same-origin', 'none'):
        return _csrf_rejected()
    origin = request.headers.get('Origin')
    if origin is not None and origin.lower().rstrip('/') not in allowed_origins():
        return _csrf_rejected()
    if request.mimetype in CSRF_SIMPLE_CONTENT_TYPES:
        return _csrf_rejected()
    return None


def requires_auth_or_activity_shell(f):
    """页面外壳(index.html、打包的静态资源):Activity 的 iframe 第一次打开时还没有令牌,放行;
    其余照旧要登录。"""
    authed = requires_auth(f)

    @wraps(f)
    def decorated(*args, **kwargs):
        if web_activity.serves_shell():
            return f(*args, **kwargs)
        return authed(*args, **kwargs)

    return decorated


# 用 Discord 登录(/auth/discord/login、/auth/discord/callback、/auth/logout),不经过 requires_auth
web.register_blueprint(web_auth_discord.create_blueprint())
# JSON API for the new web interface (all routes under /api/)
web.register_blueprint(web_api.create_blueprint(requires_auth))
web.register_blueprint(web_users.create_blueprint(requires_auth))
web.register_blueprint(web_cache.create_blueprint(requires_auth))
web.register_blueprint(web_upload.create_blueprint(requires_auth))
web.register_blueprint(web_channels.create_blueprint(requires_auth))
web.register_blueprint(web_guilds.create_blueprint(requires_auth))
web.register_blueprint(web_library.create_blueprint(requires_auth))
web.register_blueprint(web_logs.create_blueprint(requires_auth))
# Discord Activity:/api/activity/*(换令牌)和外部图片代理 /api/thumbnail/external
web.register_blueprint(web_activity.create_blueprint(requires_auth))


# The web interface: webui/ (Vue + Vite), built into webui/dist.
webui_dist = os.path.join(root_dir, "webui", "dist")


@web.route("/", methods=['GET'])
@requires_auth_or_activity_shell
def index():
    if not os.path.isfile(os.path.join(webui_dist, "index.html")):
        return "Web interface not built (run `npm ci && npm run build` in webui/).", 404
    return send_from_directory(webui_dist, "index.html")


@web.route("/assets/<path:path>", methods=['GET'])
@requires_auth_or_activity_shell
def webui_assets(path):
    return send_from_directory(os.path.join(webui_dist, "assets"), path)


@web.route("/favicon.svg", methods=['GET'])
def webui_favicon():
    return send_from_directory(webui_dist, "favicon.svg")


# Old mount point of the new UI - kept so bookmarks keep working.
@web.route("/app", methods=['GET'])
@requires_auth
def webui_root():
    return redirect("./app/", code=302)


@web.route("/app/", defaults={'path': 'index.html'}, methods=['GET'])
@web.route("/app/<path:path>", methods=['GET'])
@requires_auth
def webui_app(path):
    if not os.path.isdir(webui_dist):
        abort(404)
    return send_from_directory(webui_dist, path)
