# coding=utf-8
"""上公网(Cloudflare Tunnel)前 interface.py / bot/startup.py 的加固:
可信代理、会话 Cookie、CSRF、请求体上限、访问日志转义、auth_method 失败即拒绝。"""
import configparser
import datetime
import logging
import os
import sys

import pytest
from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import util  # noqa: E402
import variables as var  # noqa: E402


@pytest.fixture
def config(monkeypatch):
    cfg = configparser.ConfigParser(interpolation=None, allow_no_value=True)
    cfg.read(util.solve_filepath('configuration.default.ini'), encoding='utf-8')
    monkeypatch.setattr(var, 'config', cfg)
    return cfg


@pytest.fixture
def interface(config, monkeypatch):
    monkeypatch.setattr(var, 'bot', None)
    import constants
    constants.load_lang('en_US')
    import interface as mod
    mod.reset_bans()
    mod.web.secret_key = 'test'
    yield mod
    mod.reset_bans()


# =====================================================================
#  ReverseProxied:只信任 trusted_proxies 里的对端
# =====================================================================

def proxied(environ_extra, peer='172.22.0.3', **kwargs):
    from interface import ReverseProxied
    seen = {}

    def app(environ, start_response):
        seen.update(environ)
        return []

    environ = {'REMOTE_ADDR': peer, 'PATH_INFO': '/zz/api/logs', 'SCRIPT_NAME': '', 'wsgi.url_scheme': 'http'}
    environ.update(environ_extra)
    ReverseProxied(app, **kwargs)(environ, None)
    return seen


def test_untrusted_peer_cannot_spoof_client_ip(config):
    env = proxied({'HTTP_CF_CONNECTING_IP': '203.0.113.7', 'HTTP_X_REAL_IP': '198.51.100.2'}, peer='198.51.100.9')
    assert env['REMOTE_ADDR'] == '198.51.100.9'


def test_trusted_docker_peer_supplies_client_ip(config):
    # cloudflared 在 docker bridge 上,地址不固定:默认信任私有网段
    assert proxied({'HTTP_CF_CONNECTING_IP': '203.0.113.7'}, peer='172.31.5.4')['REMOTE_ADDR'] == '203.0.113.7'
    assert proxied({'HTTP_X_REAL_IP': '2001:db8::1'}, peer='::1')['REMOTE_ADDR'] == '2001:db8::1'
    # IPv4-mapped 的对端地址也认
    assert proxied({'HTTP_CF_CONNECTING_IP': '203.0.113.7'}, peer='::ffff:10.1.2.3')['REMOTE_ADDR'] == '203.0.113.7'


def test_garbage_client_ip_header_is_ignored(config):
    env = proxied({'HTTP_CF_CONNECTING_IP': '1.2.3.4\r\nINFO fake line'})
    assert env['REMOTE_ADDR'] == '172.22.0.3'


def test_trusted_proxies_from_config(config):
    config.set('webinterface', 'trusted_proxies', '198.51.100.0/24, not-a-net')
    assert proxied({'HTTP_CF_CONNECTING_IP': '203.0.113.7'}, peer='198.51.100.9')['REMOTE_ADDR'] == '203.0.113.7'
    # 配置了就只信这些,默认的私有网段不再信
    assert proxied({'HTTP_CF_CONNECTING_IP': '203.0.113.7'}, peer='172.22.0.3')['REMOTE_ADDR'] == '172.22.0.3'


def test_script_name_and_scheme_ignored_by_default(config):
    # /zz/api/logs + X-Script-Name: /zz 以前会被当成 /api/logs,绕过只保护 /api/logs 的 Access 策略
    env = proxied({'HTTP_X_SCRIPT_NAME': '/zz', 'HTTP_X_SCHEME': 'https'})
    assert env['SCRIPT_NAME'] == '' and env['PATH_INFO'] == '/zz/api/logs'
    assert env['wsgi.url_scheme'] == 'http'


def test_script_name_honoured_only_when_enabled_and_trusted(config):
    config.set('webinterface', 'honor_script_name', 'True')
    env = proxied({'HTTP_X_SCRIPT_NAME': '/zz', 'HTTP_X_SCHEME': 'https'})
    assert env['SCRIPT_NAME'] == '/zz' and env['PATH_INFO'] == '/api/logs'
    assert env['wsgi.url_scheme'] == 'https'

    env = proxied({'HTTP_X_SCRIPT_NAME': '/zz', 'HTTP_X_SCHEME': 'https'}, peer='198.51.100.9')
    assert env['SCRIPT_NAME'] == '' and env['PATH_INFO'] == '/zz/api/logs'
    assert env['wsgi.url_scheme'] == 'http'

    env = proxied({'HTTP_X_SCHEME': 'javascript'}, honor_script_name=True)
    assert env['wsgi.url_scheme'] == 'http'


# =====================================================================
#  会话 Cookie / 请求体上限 / waitress
# =====================================================================

def test_session_cookie_flags(config):
    from bot import startup
    config.set('webinterface', 'public_url', 'https://discord.example.org')
    app = Flask('t')
    startup.configure_session(app)
    assert app.config['SESSION_COOKIE_SAMESITE'] == 'Lax'
    assert app.config['SESSION_COOKIE_HTTPONLY'] is True
    assert app.config['SESSION_COOKIE_SECURE'] is True
    assert app.config['PERMANENT_SESSION_LIFETIME'] == datetime.timedelta(days=7)

    config.set('webinterface', 'public_url', '')
    app = Flask('t')
    startup.configure_session(app)
    assert app.config['SESSION_COOKIE_SECURE'] is False


def test_request_body_limits(interface):
    from bot import startup
    assert interface.web.config['MAX_CONTENT_LENGTH'] == 1024 * 1024
    assert startup.web_server_options()['max_request_body_size'] == 33 * 1024 * 1024


def test_oversized_api_body_rejected(interface):
    rv = interface.web.test_client().post('/api/logs/client', data=b'x' * (1024 * 1024 + 1),
                                          content_type='application/json')
    assert rv.status_code == 413


# =====================================================================
#  访问日志
# =====================================================================

def test_access_log_escapes_control_chars(caplog):
    from bot.startup import AccessLog

    def app(environ, start_response):
        start_response('404 Not Found', [])
        return []

    logger = logging.getLogger('test.access.core')
    environ = {'REMOTE_ADDR': '1.2.3.4\nfake', 'PATH_INFO': '/a\r\n203.0.113.1 "GET /admin" 200\x1b[31m' + 'y' * 2000,
               'REQUEST_METHOD': 'GET'}
    with caplog.at_level(logging.INFO, logger='test.access.core'):
        AccessLog(app, logger)(environ, lambda status, headers, exc_info=None: None)
    line = caplog.records[-1].getMessage()
    assert '\n' not in line and '\r' not in line and '\x1b' not in line
    assert line.startswith('1.2.3.4\\nfake "GET /a\\r\\n203.0.113.1')
    assert len(line) < 700


# =====================================================================
#  CSRF
# =====================================================================

def csrf(interface, path='/api/queue', method='POST', headers=None, **kwargs):
    with interface.web.test_request_context(path, method=method, headers=headers or {},
                                            base_url='http://bot.local', **kwargs):
        rv = interface._csrf_protect()
    return None if rv is None else rv[1]


def test_csrf_allows_spa_requests(interface):
    same = {'Origin': 'http://bot.local', 'Sec-Fetch-Site': 'same-origin'}
    assert csrf(interface, headers=same, json={'a': 1}) is None
    assert csrf(interface, headers=same) is None                      # 没有请求体(/auth/logout、上传 finish)
    assert csrf(interface, method='PUT', headers=same, data=b'x', content_type='application/octet-stream') is None
    assert csrf(interface, json={'a': 1}) is None                     # 不带 Origin / Sec-Fetch 的客户端(curl)
    assert csrf(interface, method='GET', headers={'Origin': 'https://evil.example'}) is None


def test_csrf_rejects_cross_site(interface):
    assert csrf(interface, headers={'Sec-Fetch-Site': 'cross-site'}, json={}) == 403
    assert csrf(interface, headers={'Sec-Fetch-Site': 'same-site'}, json={}) == 403
    assert csrf(interface, headers={'Origin': 'https://evil.example'}, json={}) == 403
    assert csrf(interface, headers={'Origin': 'null'}, json={}) == 403
    assert csrf(interface, path='/auth/logout', headers={'Origin': 'https://evil.example'}) == 403


@pytest.mark.parametrize('ctype', ['application/x-www-form-urlencoded', 'multipart/form-data; boundary=x',
                                   'text/plain;charset=UTF-8'])
def test_csrf_rejects_simple_content_types(interface, ctype):
    # 跨站 <form> / no-cors fetch 能发的类型;就算浏览器不带 Origin 也拒绝
    assert csrf(interface, data=b'a=1', content_type=ctype) == 403


def test_csrf_allows_same_origin_form(interface, config):
    # 本站页面里的 <form method=post>(退出登录确认页)发的是 urlencoded,浏览器会带同源证明
    config.set('webinterface', 'public_url', 'https://discord.example.org')
    assert csrf(interface, path='/auth/logout', data=b'', content_type='application/x-www-form-urlencoded',
                headers={'Origin': 'https://discord.example.org'}) is None
    assert csrf(interface, path='/auth/logout', data=b'', content_type='application/x-www-form-urlencoded',
                headers={'Sec-Fetch-Site': 'same-origin'}) is None
    assert csrf(interface, path='/auth/logout', data=b'', content_type='application/x-www-form-urlencoded',
                headers={'Sec-Fetch-Site': 'cross-site'}) == 403


def test_csrf_only_guards_api_and_auth(interface):
    assert csrf(interface, path='/', data=b'a=1', content_type='text/plain') is None


def test_csrf_uses_public_url_origin(interface, config):
    config.set('webinterface', 'public_url', 'https://Discord.Example.org/')
    assert csrf(interface, headers={'Origin': 'https://discord.example.org'}, json={}) is None
    assert csrf(interface, headers={'Origin': 'http://bot.local'}, json={}) == 403


def test_csrf_allows_activity_origin_and_bearer(interface, config, monkeypatch):
    monkeypatch.delenv('DISCORD_CLIENT_SECRET', raising=False)
    config.set('webinterface', 'public_url', 'https://discord.example.org')
    activity = {'Origin': 'https://123456.discordsays.com', 'Sec-Fetch-Site': 'same-origin'}
    assert csrf(interface, path='/api/activity/token', headers=activity, json={}) == 403
    config.set('webinterface', 'activity_enabled', 'True')
    config.set('webinterface', 'discord_client_id', '123456')
    config.set('webinterface', 'discord_client_secret', 'shh')
    assert csrf(interface, path='/api/activity/token', headers=activity, json={}) is None
    assert csrf(interface, headers={'Origin': 'https://999.discordsays.com'}, json={}) == 403
    # Bearer 不是浏览器自动带的,不受 CSRF 影响
    assert csrf(interface, headers={'Authorization': 'Bearer abc', 'Origin': 'https://999.discordsays.com'},
                data=b'x', content_type='text/plain') is None


def test_csrf_bearer_exempt_only_when_activity_uses_it(interface, config, monkeypatch):
    monkeypatch.delenv('DISCORD_CLIENT_SECRET', raising=False)
    evil = {'Origin': 'https://evil.example'}
    # Activity 没开:Bearer 不被认,requires_auth 会退回 Cookie 会话,所以照样查
    assert csrf(interface, headers=dict(evil, Authorization='Bearer abc'), json={}) == 403
    config.set('webinterface', 'activity_enabled', 'True')
    config.set('webinterface', 'discord_client_id', '123456')
    config.set('webinterface', 'discord_client_secret', 'shh')
    assert csrf(interface, headers=dict(evil, Authorization='Bearer abc'), json={}) is None
    # 空令牌 / 非 /api/ 路径(/auth/logout 只看 Cookie)都不跳过
    assert csrf(interface, headers=dict(evil, Authorization='Bearer '), json={}) == 403
    assert csrf(interface, path='/auth/logout', headers=dict(evil, Authorization='Bearer abc')) == 403


def test_csrf_end_to_end(interface):
    client = interface.web.test_client()
    rv = client.post('/auth/logout', headers={'Origin': 'https://evil.example'})
    assert rv.status_code == 403 and rv.get_json() == {'error': 'csrf'}
    rv = client.post('/auth/logout', headers={'Origin': 'http://localhost', 'Sec-Fetch-Site': 'same-origin'})
    assert rv.status_code == 200 and rv.get_json() == {'ok': True}
    rv = client.post('/api/logs/client', data={'message': 'x'})
    assert rv.status_code == 403


# =====================================================================
#  auth_method
# =====================================================================

def guarded(interface, monkeypatch):
    monkeypatch.setattr(interface, '_with_identity', lambda f, user, args, kwargs: f(*args, **kwargs))
    with interface.web.test_request_context('/api/status'):
        rv = interface.requires_auth(lambda: 'ok')()
    return rv


@pytest.mark.parametrize('value', ['None', ' none ', 'NONE'])
def test_auth_method_none_is_normalised(interface, config, monkeypatch, value):
    config.set('webinterface', 'auth_method', value)
    assert guarded(interface, monkeypatch) == 'ok'


@pytest.mark.parametrize('value', ['', 'nope', 'disabled', 'off'])
def test_unknown_auth_method_fails_closed(interface, config, monkeypatch, caplog, value):
    config.set('webinterface', 'auth_method', value)
    interface._bad_auth_methods_logged.clear()
    with caplog.at_level(logging.ERROR, logger='bot'):
        rv = guarded(interface, monkeypatch)
    assert rv != 'ok' and rv[1] == 503
    assert any('auth_method' in r.getMessage() for r in caplog.records)


def test_auth_method_discord_is_normalised(interface, config, monkeypatch):
    config.set('webinterface', 'auth_method', ' Discord ')
    rv = guarded(interface, monkeypatch)
    assert rv != 'ok' and rv[1] == 401


# =====================================================================
#  启动时的警告
# =====================================================================

def warnings_for(config, caplog, **options):
    from bot import startup
    for key, value in options.items():
        section = 'discord' if key == 'allowed_guilds' else 'webinterface'
        config.set(section, key, value)
    caplog.clear()
    logger = logging.getLogger('test.startup.core')
    with caplog.at_level(logging.WARNING, logger='test.startup.core'):
        startup.warn_insecure_web_config(logger)
    return [r for r in caplog.records if r.name == 'test.startup.core']


def test_warns_when_public_without_auth(config, caplog):
    records = warnings_for(config, caplog, auth_method='none', public_url='https://x.example', allowed_guilds='1')
    assert len(records) == 1 and 'auth_method = none' in records[0].getMessage()
    records = warnings_for(config, caplog, auth_method='none', public_url='', activity_enabled='True')
    assert len(records) == 1 and 'auth_method = none' in records[0].getMessage()


def test_warns_when_public_without_allowed_guilds(config, caplog):
    records = warnings_for(config, caplog, auth_method='discord', public_url='https://x.example', allowed_guilds='')
    assert len(records) == 1 and 'allowed_guilds' in records[0].getMessage()


def test_no_warning_for_safe_config(config, caplog):
    assert warnings_for(config, caplog, auth_method='discord', public_url='https://x.example',
                        allowed_guilds='123') == []
    assert warnings_for(config, caplog, auth_method='none', public_url='', activity_enabled='False') == []


def test_error_for_unknown_auth_method(config, caplog):
    records = warnings_for(config, caplog, auth_method='discrod')
    assert any(r.levelno == logging.ERROR and 'discrod' in r.getMessage() for r in records)


# =====================================================================
#  上线后外部探测发现的:编码斜杠绕过 Access、/api 错误要 JSON、未带哈希的资源不缓存
# =====================================================================

@pytest.mark.parametrize('raw', ['/api%2flogs', '/api/logs%2Fdownload', '/api%2fcache', '/api/logs%5cdebug'])
def test_encoded_path_separators_rejected(interface, config, raw):
    # Access 按原始路径比较,/api%2flogs 不在它的保护范围里;解码后却会路由到 /api/logs
    client = interface.web.test_client()
    rv = client.get(raw, environ_overrides={'REQUEST_URI': raw})
    assert rv.status_code == 400
    assert rv.get_json() == {'error': 'bad_path'}


def test_plain_paths_and_encoded_query_still_work(interface, config):
    client = interface.web.test_client()
    rv = client.get('/api/activity/config?next=%2Fqueue',
                    environ_overrides={'REQUEST_URI': '/api/activity/config?next=%2Fqueue'})
    assert rv.status_code == 200


def test_api_errors_are_json(interface, config):
    client = interface.web.test_client()
    rv = client.get('/api/no-such-thing')
    assert rv.status_code == 404 and rv.get_json() == {'error': 'not_found'}
    rv = client.put('/api/activity/config')
    assert rv.status_code == 405 and rv.get_json() == {'error': 'method_not_allowed'}
    assert 'GET' in rv.headers['Allow']
    rv = client.get('/no-such-page')
    assert rv.status_code == 404 and rv.get_json(silent=True) is None


def test_unhashed_assets_are_revalidated(interface):
    assert interface._HASHED_ASSET.search('index-C6vpD2Eh.js')
    assert interface._HASHED_ASSET.search('LibraryPage-DFSKy9t_.js')
    assert interface._HASHED_ASSET.search('index-CiqVPKEr.css')
    assert not interface._HASHED_ASSET.search('theme-init.js')


def test_html_responses_forbid_edge_rewriting(interface, config):
    # Cloudflare Rocket Loader 改写 <script>:HTML 一律带 no-transform,JSON 不受影响
    client = interface.web.test_client()
    rv = client.get('/no-such-page')
    assert 'no-transform' in rv.headers['Cache-Control'] and 'no-store' in rv.headers['Cache-Control']
    rv = client.get('/api/no-such-thing')
    assert 'no-transform' not in rv.headers.get('Cache-Control', '')
