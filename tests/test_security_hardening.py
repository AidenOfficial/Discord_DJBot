# coding=utf-8
"""上公网前的安全加固:响应头、按身份限流、令牌封禁、SSRF(入口检查 + 出站守卫)、waitress、容器出站过滤。"""
import configparser
import logging
import os
import socket
import sys
import types
from unittest import mock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import util  # noqa: E402
import variables as var  # noqa: E402
import web_security  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture
def config(monkeypatch):
    cfg = configparser.ConfigParser(interpolation=None, allow_no_value=True)
    cfg.read(util.solve_filepath('configuration.default.ini'), encoding='utf-8')
    monkeypatch.setattr(var, 'config', cfg)
    return cfg


class FakeSettingsDb:
    def __init__(self, data=None):
        self.data = dict(data or {})

    def get(self, section, option, fallback=None):
        return self.data.get((section, option), fallback)

    def set(self, section, option, value):
        self.data[(section, option)] = value


@pytest.fixture
def interface(config, monkeypatch):
    monkeypatch.setattr(var, 'db', FakeSettingsDb())
    monkeypatch.setattr(var, 'bot', None)
    import constants
    constants.load_lang('en_US')
    import interface as mod
    mod.reset_bans()
    mod.web.secret_key = 'test'
    yield mod
    mod.reset_bans()


# =====================================================================
#  1. 安全响应头
# =====================================================================

def test_security_headers_on_every_response(interface):
    rv = interface.web.test_client().get('/favicon.svg')
    csp = rv.headers['Content-Security-Policy']
    assert "frame-ancestors 'self' https://discord.com https://*.discord.com https://*.discordsays.com" in csp
    assert "script-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "base-uri 'self'" in csp
    assert 'unsafe-eval' not in csp
    assert rv.headers['X-Content-Type-Options'] == 'nosniff'
    assert rv.headers['Referrer-Policy'] == 'no-referrer'
    # 404 和 JSON 接口也带
    rv = interface.web.test_client().get('/no-such-page')
    assert 'frame-ancestors' in rv.headers['Content-Security-Policy']


def test_frame_ancestors_is_configurable(config):
    config.set('webinterface', 'frame_ancestors', "'self' https://example.com; script-src *")
    # 分号不能借机注入别的指令
    assert web_security.frame_ancestors() == "'self' https://example.com script-src *"
    assert web_security.content_security_policy().count(';') == len(web_security.CSP_DIRECTIVES)
    config.set('webinterface', 'frame_ancestors', '')
    assert web_security.frame_ancestors() == "'none'"


def test_route_can_override_header(config):
    from flask import Flask, Response
    app = Flask(__name__)
    app.after_request(web_security.apply_security_headers)

    @app.route('/x')
    def x():
        return Response('x', headers={'Referrer-Policy': 'same-origin'})

    rv = app.test_client().get('/x')
    assert rv.headers['Referrer-Policy'] == 'same-origin'
    assert rv.headers['X-Content-Type-Options'] == 'nosniff'


# =====================================================================
#  2. 限流:按身份 / 服务器,没有身份才按 IP
# =====================================================================

def _limited_app(monkeypatch, bucket, rules, identity_from_header=True, guild_from_header=False):
    from flask import Flask, g, request
    monkeypatch.setitem(web_security.RULES, bucket, rules)
    app = Flask(__name__)

    @app.route('/x')
    @web_security.rate_limited(bucket)
    def x():
        return 'ok'

    @app.before_request
    def ident():
        who = request.headers.get('X-Who')
        if identity_from_header and who:
            g.web_identity = types.SimpleNamespace(key=who)

    if guild_from_header:
        monkeypatch.setattr(web_security, 'guild_key',
                            lambda: 'guild:' + request.headers['X-Guild'] if request.headers.get('X-Guild') else None)
    return app.test_client()


def test_rate_limit_counts_identities_separately_behind_one_ip(config, monkeypatch):
    # Activity:所有人都从 Discord 代理的同一个 IP 来
    client = _limited_app(monkeypatch, 'search', (('client', 3, 60),))
    proxy = {'REMOTE_ADDR': '162.159.1.1'}
    for _ in range(3):
        assert client.get('/x', headers={'X-Who': 'discord:1'}, environ_base=proxy).status_code == 200
    rv = client.get('/x', headers={'X-Who': 'discord:1'}, environ_base=proxy)
    assert rv.status_code == 429
    assert rv.get_json()['error'] == 'rate_limited'
    assert int(rv.headers['Retry-After']) >= 1
    # 同一个 IP 的另一个人不受影响
    assert client.get('/x', headers={'X-Who': 'discord:2'}, environ_base=proxy).status_code == 200


def test_rate_limit_falls_back_to_ip_without_identity(config, monkeypatch):
    client = _limited_app(monkeypatch, 'search', (('client', 2, 60),))
    a, b = {'REMOTE_ADDR': '198.51.100.1'}, {'REMOTE_ADDR': '198.51.100.2'}
    assert client.get('/x', environ_base=a).status_code == 200
    assert client.get('/x', environ_base=a).status_code == 200
    assert client.get('/x', environ_base=a).status_code == 429
    assert client.get('/x', environ_base=b).status_code == 200


def test_rate_limit_per_guild(config, monkeypatch):
    client = _limited_app(monkeypatch, 'enqueue', (('client', 100, 60), ('guild', 2, 60)), guild_from_header=True)
    assert client.get('/x', headers={'X-Who': 'a', 'X-Guild': '1'}).status_code == 200
    assert client.get('/x', headers={'X-Who': 'b', 'X-Guild': '1'}).status_code == 200
    assert client.get('/x', headers={'X-Who': 'c', 'X-Guild': '1'}).status_code == 429  # 这个服务器满了
    assert client.get('/x', headers={'X-Who': 'c', 'X-Guild': '2'}).status_code == 200


def test_rate_limit_can_be_disabled(config, monkeypatch):
    config.set('webinterface', 'rate_limit', 'False')
    client = _limited_app(monkeypatch, 'search', (('client', 1, 60),))
    for _ in range(5):
        assert client.get('/x').status_code == 200


def test_sliding_window_expires():
    limiter = web_security.RateLimiter()
    assert limiter.hit('k', 2, 10, now=100) == 0
    assert limiter.hit('k', 2, 10, now=101) == 0
    assert limiter.hit('k', 2, 10, now=105) == 5
    assert limiter.hit('k', 2, 10, now=110.5) == 0  # 第一次已出窗口


def test_rate_limited_routes_are_wired():
    import inspect
    import web_api
    import web_auth_discord
    import web_library
    import web_users
    sources = {m.__name__: inspect.getsource(m) for m in (web_api, web_users, web_library, web_auth_discord)}
    assert "@rate_limited('search')" in sources['web_api']
    assert "@rate_limited('enqueue')" in sources['web_api']
    assert "@rate_limited('import')" in sources['web_users']
    assert "@rate_limited('enqueue')" in sources['web_library']
    assert sources['web_auth_discord'].count("@rate_limited('discord_auth')") == 2


def test_search_endpoint_returns_429(config, monkeypatch):
    from flask import Flask
    import web_api
    monkeypatch.setitem(web_security.RULES, 'search', (('client', 1, 60),))
    monkeypatch.setattr(web_api.web_search, 'unified_search', lambda q, limit: ([], []))
    monkeypatch.setattr(var, 'hub', None, raising=False)
    monkeypatch.setattr(var, 'bot', types.SimpleNamespace(guild_id='1'))
    app = Flask(__name__)
    app.register_blueprint(web_api.create_blueprint(lambda f: f))
    client = app.test_client()
    assert client.get('/api/search?q=hello').status_code == 200
    assert client.get('/api/search?q=hello').status_code == 429


# =====================================================================
#  令牌校验:限流 + 封禁只拦再试凭据的请求
# =====================================================================

def _protected(interface):
    @interface.requires_auth
    def protected():
        return 'ok'
    return protected


def test_bad_tokens_ban_only_new_attempts(interface, monkeypatch):
    config = var.config
    config.set('webinterface', 'auth_method', 'token')
    config.set('webinterface', 'max_attempts', '2')
    monkeypatch.setattr(interface.web_users, 'resolve_identity', lambda user: user)
    monkeypatch.setattr(interface, 'render_template', lambda *a, **k: 'need token')
    monkeypatch.setattr(interface.web_auth_discord, 'session_user', lambda: None)
    protected = _protected(interface)
    ip = {'REMOTE_ADDR': '162.159.1.1'}  # Discord 代理
    for _ in range(3):
        with interface.web.test_request_context('/?token=wrong', environ_base=ip):
            assert protected() == 'need token'
    assert '162.159.1.1' in interface.banned_ip
    with interface.web.test_request_context('/?token=wrong', environ_base=ip):
        with pytest.raises(Exception) as e:
            protected()
        assert getattr(e.value, 'code', None) == 403
    # 同一个 IP 上已经登录的会话照常能用(不再整 IP 封死)
    with interface.web.test_request_context('/', environ_base=ip):
        from flask import session
        session['user'] = 'alice'
        assert protected() == 'ok'
    # 不带令牌只是看登录页,不算一次失败
    interface.reset_bans()
    for _ in range(5):
        with interface.web.test_request_context('/', environ_base=ip):
            assert protected() == 'need token'
    assert interface.bad_access_count == {}


def test_ban_expires(interface, monkeypatch):
    var.config.set('webinterface', 'max_attempts', '0')
    var.config.set('webinterface', 'ban_minutes', '1')
    now = [1000.0]
    monkeypatch.setattr(interface.time, 'monotonic', lambda: now[0])
    interface._record_failure('203.0.113.9', 'bad token')
    assert interface._ip_banned('203.0.113.9')
    now[0] += 61
    assert not interface._ip_banned('203.0.113.9')
    assert '203.0.113.9' not in interface.bad_access_count


def test_token_checks_are_rate_limited(interface, monkeypatch):
    var.config.set('webinterface', 'auth_method', 'token')
    var.config.set('webinterface', 'max_attempts', '1000')
    monkeypatch.setitem(web_security.RULES, 'token', (('ip', 2, 60),))
    monkeypatch.setattr(interface, 'render_template', lambda *a, **k: 'need token')
    monkeypatch.setattr(interface.web_auth_discord, 'session_user', lambda: None)
    protected = _protected(interface)
    for _ in range(2):
        with interface.web.test_request_context('/?token=x'):
            assert protected() == 'need token'
    with interface.web.test_request_context('/?token=x'):
        assert protected().status_code == 429


def test_password_failures_are_counted(interface, monkeypatch):
    var.config.set('webinterface', 'auth_method', 'password')
    var.config.set('webinterface', 'max_attempts', '1')
    protected = _protected(interface)
    import base64
    bad = {'Authorization': 'Basic ' + base64.b64encode(b'x:y').decode()}
    for _ in range(2):
        with interface.web.test_request_context('/', headers=bad):
            assert protected().status_code == 401
    with interface.web.test_request_context('/', headers=bad):
        with pytest.raises(Exception) as e:
            protected()
        assert getattr(e.value, 'code', None) == 403


def test_new_tokens_are_long():
    import inspect
    from commands import web
    assert 'token_urlsafe(16)' in inspect.getsource(web.cmd_web_access)


# =====================================================================
#  3. SSRF
# =====================================================================

@pytest.mark.parametrize('ip, public', [
    ('8.8.8.8', True), ('2606:4700::1111', True),
    ('10.1.2.3', False), ('172.20.0.1', False), ('192.168.1.1', False), ('127.0.0.1', False),
    ('169.254.169.254', False), ('100.100.1.1', False), ('0.0.0.0', False), ('224.0.0.1', False),
    ('::1', False), ('fe80::1%eth0', False), ('fd00::1', False), ('::ffff:192.168.1.1', False),
    ('::ffff:8.8.8.8', True), ('not-an-ip', False),
])
def test_ip_is_public(ip, public):
    assert util.ip_is_public(ip) is public


def test_is_public_url(monkeypatch):
    table = {'good.example': ['8.8.8.8'], 'lan.example': ['192.168.1.5'],
             'mixed.example': ['8.8.8.8', '10.0.0.1'], 'meta.example': ['169.254.169.254']}
    monkeypatch.setattr(util, 'resolve_host', lambda host: table.get(host, []))
    assert util.is_public_url('https://good.example/watch?v=1')
    assert not util.is_public_url('http://lan.example/')
    assert not util.is_public_url('http://mixed.example/')  # 有一个解析到内网就不行
    assert not util.is_public_url('http://meta.example/latest/meta-data')
    assert not util.is_public_url('http://unresolvable.example/')
    assert not util.is_public_url('file:///etc/passwd')
    assert not util.is_public_url('ftp://good.example/')
    assert not util.is_public_url('http://good.example:99999/')
    assert not util.is_public_url('http://[::1]:8181/api/status')


def test_private_network_allow(monkeypatch):
    import ipaddress
    monkeypatch.setattr(util, 'private_network_allow', [ipaddress.ip_network('192.168.1.10/32')])
    assert util.is_public_url('http://192.168.1.10:8000/stream')
    assert not util.is_public_url('http://192.168.1.11:8000/stream')


def test_search_add_rejects_private_urls(config, monkeypatch):
    from flask import Flask
    import web_api
    app = Flask(__name__)
    app.register_blueprint(web_api.create_blueprint(lambda f: f))
    with mock.patch.object(web_api, 'get_cached_wrapper_from_scrap') as scrap:
        for url in ('http://192.168.1.1/', 'http://127.0.0.1:8181/api/status', 'http://169.254.169.254/'):
            rv = app.test_client().post('/api/search/add', json={'source': 'youtube', 'url': url})
            assert rv.status_code == 400, url
            assert rv.get_json() == {'error': 'bad_url'}
        scrap.assert_not_called()


def test_playlist_url_entries_reject_private_urls(config, monkeypatch):
    import web_users
    from flask import Flask
    app = Flask(__name__)
    with app.test_request_context('/'):
        with pytest.raises(Exception) as e:
            web_users._entries_from_source({'source': 'url', 'url': 'http://10.0.0.1/admin'})
        assert getattr(e.value, 'code', None) == 400


def test_import_source_detection_needs_the_real_domain():
    import playlist_import as pi
    assert pi.detect_source('https://www.youtube.com/playlist?list=PL1') == 'youtube'
    assert pi.detect_source('https://youtube.com/playlist?list=PL1') == 'youtube'
    for bad in ('https://evilyoutube.com/playlist?list=PL1', 'https://notmusic.163.com.evil/playlist?id=1',
                'https://fakemusic.163.com/playlist?id=1', 'https://evil-y.qq.com/n/ryqq/playlist/1',
                'javascript://www.youtube.com/?list=1', 'http://www.youtube.com:bad/?list=1'):
        assert pi.detect_source(bad) is None, bad


class _Resp:
    def __init__(self, location=None):
        self.headers = {'Location': location} if location else {}
        self.is_redirect = bool(location)

    def close(self):
        pass


def test_resolve_redirects_checks_each_hop(monkeypatch):
    import requests
    hops = {'https://163cn.tv/abc': 'https://music.163.com/playlist?id=1',
            'https://163cn.tv/evil': 'http://192.168.1.1/',
            'https://163cn.tv/loop': 'https://163cn.tv/loop'}
    seen = []

    def fake_request(method, url, **kwargs):
        assert kwargs['allow_redirects'] is False
        seen.append(url)
        return _Resp(hops.get(url))

    monkeypatch.setattr(requests, 'request', fake_request)
    ok = lambda h: h == '163cn.tv' or h.endswith('.163.com')  # noqa: E731
    assert util.resolve_redirects('https://163cn.tv/abc', ok) == 'https://music.163.com/playlist?id=1'
    seen.clear()
    assert util.resolve_redirects('https://163cn.tv/evil', ok) is None
    assert seen == ['https://163cn.tv/evil']  # 内网那一跳没有被请求
    assert util.resolve_redirects('https://163cn.tv/loop', ok, max_hops=3) is None
    # 第一跳也要过检查:不在白名单 / 解析到内网的链接一次都不请求
    seen.clear()
    assert util.resolve_redirects('https://evil.example/', ok) is None
    monkeypatch.setattr(util, 'resolve_host', lambda host: ['10.0.0.1'])
    assert util.resolve_redirects('https://163cn.tv/abc', ok) is None
    assert seen == []


def test_failure_log_strips_newlines(interface, caplog):
    with caplog.at_level(logging.INFO, logger='bot'):
        interface._record_failure('203.0.113.1\nFAKE', 'failed login attempt, user: a\r\nweb: forged')
    message = caplog.records[-1].getMessage()
    assert '\n' not in message and '\r' not in message


def test_url_item_refuses_private_url(config, monkeypatch, tmp_path):
    from media.item import ValidationFailedError
    from media.url import URLItem
    import constants
    constants.load_lang('en_US')
    monkeypatch.setattr(var, 'tmp_folder', str(tmp_path) + os.sep)
    monkeypatch.setattr(var, 'store', None, raising=False)
    item = URLItem('http://192.168.1.1/video.mp4')
    with mock.patch.object(URLItem, '_get_info_from_url') as fetch:
        with pytest.raises(ValidationFailedError):
            item.validate()
        fetch.assert_not_called()


def test_livestream_refuses_private_url(config):
    from media.item import ValidationFailedError
    from media.livestream import LiveStreamItem
    import constants
    constants.load_lang('en_US')
    item = LiveStreamItem('http://10.0.0.1/live.m3u8')
    with mock.patch.object(LiveStreamItem, '_fetch_info') as fetch:
        with pytest.raises(ValidationFailedError):
            item.validate()
        fetch.assert_not_called()


def test_artwork_does_not_fetch_private_images(monkeypatch):
    import requests
    from media import artwork
    monkeypatch.setattr(requests, 'get', mock.Mock(side_effect=AssertionError('fetched')))
    with pytest.raises(ValueError):
        artwork._fetch_image('http://169.254.169.254/latest/meta-data')


# ---- 出站守卫(跳转、DNS 重绑定在连接时拦) -------------------------------------------

@pytest.fixture
def listener():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(('127.0.0.1', 0))
    srv.listen(5)
    yield srv.getsockname()[1]
    srv.close()


def test_egress_guard_blocks_private_connections(config, listener):
    from bot import egress
    assert egress.install(config)
    with pytest.raises(PermissionError):
        socket.create_connection(('127.0.0.1', listener), timeout=2)
    s = socket.socket()
    try:
        assert s.connect_ex(('127.0.0.1', listener)) != 0
    finally:
        s.close()
    # socketpair(Windows 上用回环模拟,asyncio 要用)不受影响
    a, b = socket.socketpair()
    a.close()
    b.close()
    egress.uninstall()
    socket.create_connection(('127.0.0.1', listener), timeout=2).close()


def test_egress_guard_allow_list(config, listener):
    from bot import egress
    config.set('bot', 'private_network_allow', '127.0.0.0/8, not-a-network')
    egress.install(config)
    socket.create_connection(('127.0.0.1', listener), timeout=2).close()


def test_egress_guard_disabled_by_config(config, listener):
    from bot import egress
    config.set('bot', 'block_private_network', 'False')
    assert not egress.install(config)
    assert not egress.installed()
    socket.create_connection(('127.0.0.1', listener), timeout=2).close()


def test_egress_guard_pins_the_checked_address(config, monkeypatch):
    """主机名在连接时解析:解析结果是内网就拒绝;是公网就只连检查过的那个 IP(不给二次解析留机会)。"""
    from bot import egress
    egress.install(config)
    answers = {'rebind.example': [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('10.0.0.7', 80))],
               'ok.example': [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('8.8.8.8', 80))]}
    monkeypatch.setattr(socket, 'getaddrinfo', lambda host, port, *a, **k: answers[host])
    connected = []
    monkeypatch.setattr(egress, '_orig_connect', lambda sock, address: connected.append(address))
    s = socket.socket()
    try:
        with pytest.raises(PermissionError):
            s.connect(('rebind.example', 80))
        s.connect(('ok.example', 80))
    finally:
        s.close()
    assert connected == [('8.8.8.8', 80)]


def test_egress_allows_configured_proxies(config, monkeypatch):
    from bot import egress
    monkeypatch.setenv('HTTPS_PROXY', 'http://192.168.1.20:7890')
    egress.install(config)
    assert util.ip_is_allowed('192.168.1.20')
    assert not util.ip_is_allowed('192.168.1.21')


def test_startup_installs_egress_guard():
    import inspect
    from bot import startup
    assert 'egress.install(config)' in inspect.getsource(startup.main)


# ---- 容器层 ------------------------------------------------------------------------

def test_compose_enables_container_egress_filter():
    text = open(os.path.join(ROOT, 'docker-compose.yml'), encoding='utf-8').read()
    assert 'NET_ADMIN' in text
    assert 'BAM_EGRESS_FILTER: ${BAM_EGRESS_FILTER:-1}' in text


def test_egress_filter_script_blocks_the_private_ranges():
    text = open(os.path.join(ROOT, 'scripts', 'egress-filter.sh'), encoding='utf-8').read()
    block = next(line for line in text.splitlines() if line.startswith('BLOCK_V4='))
    for net in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '169.254.0.0/16'):
        assert net in block
    entry = open(os.path.join(ROOT, 'entrypoint.sh'), encoding='utf-8').read()
    assert '/botamusique/scripts/egress-filter.sh' in entry
    assert '--bounding-set=-net_admin' in entry
    assert 'iptables' in open(os.path.join(ROOT, 'Dockerfile'), encoding='utf-8').read()


# =====================================================================
#  4. waitress
# =====================================================================

def test_web_interface_uses_waitress(config, monkeypatch):
    from bot import startup
    import interface
    served = {}
    fake = types.SimpleNamespace(serve=lambda app, **kw: served.update(app=app, **kw))
    monkeypatch.setitem(sys.modules, 'waitress', fake)
    monkeypatch.setattr(interface.web, 'run', mock.Mock(side_effect=AssertionError('dev server')))
    monkeypatch.setattr(util, 'resolve_flask_secret', lambda: 'secret')
    monkeypatch.setattr(var, 'is_proxified', True)
    saved_wsgi = interface.web.wsgi_app
    try:
        startup.start_web_interface('0.0.0.0', 8181)
        assert served['host'] == '0.0.0.0' and served['port'] == 8181
        assert served['max_request_body_size'] >= 4 * 1024 ** 3
        assert served['trusted_proxy'] is None
        # is_web_proxified 照旧装上 ReverseProxied
        assert isinstance(interface.web.wsgi_app, interface.ReverseProxied)
        assert served['app'].app is interface.web
    finally:
        interface.web.wsgi_app = saved_wsgi
        logging.getLogger('werkzeug').handlers.clear()


def test_access_log_has_real_ip_and_no_query(caplog):
    from bot.startup import AccessLog
    from interface import ReverseProxied

    def app(environ, start_response):
        start_response('204 No Content', [])
        return []

    logger = logging.getLogger('test.access')
    wrapped = AccessLog(ReverseProxied(app), logger)
    environ = {'REMOTE_ADDR': '172.18.0.3', 'PATH_INFO': '/api/status', 'QUERY_STRING': 'token=secret',
               'REQUEST_METHOD': 'GET', 'HTTP_CF_CONNECTING_IP': '203.0.113.5'}
    with caplog.at_level(logging.INFO, logger='test.access'):
        wrapped(environ, lambda status, headers, exc_info=None: None)
    line = caplog.records[-1].getMessage()
    assert line == '203.0.113.5 "GET /api/status" 204'
    assert 'secret' not in line


def test_waitress_in_requirements():
    reqs = open(os.path.join(ROOT, 'requirements.txt'), encoding='utf-8').read().splitlines()
    assert any(r.startswith('waitress') for r in reqs)


# =====================================================================
#  5. 文档
# =====================================================================

def test_webui_doc_covers_access_for_admin_paths():
    doc = open(os.path.join(ROOT, 'deploy', 'WEBUI.md'), encoding='utf-8').read()
    for needle in ('/api/logs', '/api/cache', 'api/logs/client', 'Bypass', 'access_email_header ='):
        assert needle in doc


def test_default_config_lists_new_options(config):
    assert config.getboolean('bot', 'block_private_network')
    assert config.get('bot', 'private_network_allow') == ''
    assert config.getboolean('webinterface', 'rate_limit')
    assert config.getint('webinterface', 'ban_minutes') == 15
    assert config.get('webinterface', 'frame_ancestors') == web_security.DEFAULT_FRAME_ANCESTORS


def test_activity_endpoints_are_rate_limited():
    # 合并加固和 Activity 后:换令牌(登录前,按 IP 且放宽)和外部图片代理(按身份)都有限流
    import web_security
    assert web_security.RULES['activity_token'] == (('ip', 120, 60),)
    assert web_security.RULES['image_proxy'][0][0] == 'client'
    import web_activity
    from interface import web
    views = {rule.rule: web.view_functions[rule.endpoint] for rule in web.url_map.iter_rules()}
    for path in ('/api/activity/token', '/api/thumbnail/external'):
        assert hasattr(views[path], '__wrapped__'), path
    assert web_activity  # 模块已加载
