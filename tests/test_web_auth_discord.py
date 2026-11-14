# coding=utf-8
"""用 Discord 登录(web_auth_discord):OAuth 流程、身份映射、服务器缓存、门禁。不连真实的 Discord。"""
import configparser
import os
import sys
import time
import types
from urllib.parse import parse_qs, urlparse

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import util  # noqa: E402
import variables as var  # noqa: E402
import web_users  # noqa: E402

PUBLIC_URL = 'https://music.example.test'


class FakeResp:
    def __init__(self, status, payload=None, headers=None):
        self.status_code = status
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        if self._payload is None:
            raise ValueError('no json')
        return self._payload


# Activity 的授权码要过 ^[A-Za-z0-9]{16,64}$;网页登录的回调没有这个检查
GOOD_ACTIVITY_CODE = 'GoodActivityCode1234'
BAD_ACTIVITY_CODE = 'BadActivityCode12345'
GOOD_CODES = ('good', GOOD_ACTIVITY_CODE)


class FakeDiscord:
    """假的 Discord OAuth / REST 端点。"""

    def __init__(self):
        self.user = {'id': '42', 'username': 'alice', 'global_name': 'Alice', 'avatar': 'abc123'}
        self.guilds = [
            {'id': '111', 'name': 'Home', 'icon': 'ic1', 'owner': False, 'permissions': '32'},
            {'id': '222', 'name': 'Mine', 'icon': None, 'owner': True, 'permissions': '0'},
            {'id': '333', 'name': 'Other', 'icon': None, 'owner': False, 'permissions': '1024'},
        ]
        self.calls = []
        self.guilds_status = 200
        self.issued = 0

    def _token(self):
        self.issued += 1
        return FakeResp(200, {'access_token': f'at{self.issued}', 'refresh_token': f'rt{self.issued}',
                              'expires_in': 604800, 'token_type': 'Bearer', 'scope': 'identify guilds'})

    def post(self, url, data=None, **kwargs):
        self.calls.append(('post', url, dict(data or {})))
        assert kwargs.get('timeout')
        if data['grant_type'] == 'authorization_code':
            return self._token() if data['code'] in GOOD_CODES else FakeResp(400, {'error': 'invalid_grant'})
        if data['grant_type'] == 'refresh_token':
            return self._token()
        return FakeResp(400, {})

    def get(self, url, headers=None, **kwargs):
        self.calls.append(('get', url, headers.get('Authorization')))
        assert kwargs.get('timeout')
        if url.endswith('/users/@me'):
            return FakeResp(200, self.user)
        if url.endswith('/users/@me/guilds'):
            if self.guilds_status == 429:
                return FakeResp(429, {'retry_after': 30})
            return FakeResp(self.guilds_status, self.guilds)
        return FakeResp(404, {})

    def count(self, suffix):
        return sum(1 for c in self.calls if c[1].endswith(suffix))


@pytest.fixture
def env(monkeypatch, tmp_path):
    config = configparser.ConfigParser(interpolation=None, allow_no_value=True)
    config.read(util.solve_filepath('configuration.default.ini'), encoding='utf-8')
    config.set('webinterface', 'auth_method', 'discord')
    config.set('webinterface', 'discord_client_id', '123456')
    config.set('webinterface', 'discord_client_secret', 'test-client-secret')
    config.set('webinterface', 'public_url', PUBLIC_URL + '/')
    monkeypatch.setattr(var, 'config', config)
    monkeypatch.setattr(var, 'db', None)
    monkeypatch.setattr(var, 'language', 'en_US')
    monkeypatch.setattr(var, 'user_db', web_users.UserDatabase(str(tmp_path / 'settings.db')))
    monkeypatch.setattr(var, 'bot', types.SimpleNamespace(
        link=types.SimpleNamespace(guild_id=111, bot_name='dj'), command_name=lambda key: key))
    monkeypatch.delenv('DISCORD_CLIENT_SECRET', raising=False)
    import constants
    constants.load_lang('en_US')
    import interface
    import web_auth_discord
    web_auth_discord._cache.clear()
    interface.web.secret_key = 'test'
    interface.bad_access_count.clear()
    fake = FakeDiscord()
    monkeypatch.setattr(web_auth_discord.requests, 'post', fake.post)
    monkeypatch.setattr(web_auth_discord.requests, 'get', fake.get)
    yield types.SimpleNamespace(client=interface.web.test_client(), discord=fake, mod=web_auth_discord,
                                config=config, interface=interface)
    web_auth_discord._cache.clear()


def start_login(client, next_path=None):
    rv = client.get('/auth/discord/login' + (f'?next={next_path}' if next_path else ''))
    assert rv.status_code == 302
    return rv, parse_qs(urlparse(rv.headers['Location']).query)


def login(client, code='good'):
    _, query = start_login(client)
    return client.get(f"/auth/discord/callback?code={code}&state={query['state'][0]}")


# ---- OAuth 流程 ------------------------------------------------------------------

def test_login_redirects_to_discord_with_state(env):
    rv, query = start_login(env.client)
    assert rv.headers['Location'].startswith('https://discord.com/oauth2/authorize?')
    assert query['response_type'] == ['code']
    assert query['client_id'] == ['123456']
    assert query['scope'] == ['identify guilds']
    assert query['redirect_uri'] == [PUBLIC_URL + '/auth/discord/callback']
    state = query['state'][0]
    assert len(state) >= 16
    with env.client.session_transaction() as s:
        assert s[env.mod.SESSION_STATE] == state
    # 每次登录都是新的 state
    assert start_login(env.client)[1]['state'][0] != state


def test_callback_rejects_bad_state(env):
    start_login(env.client)
    rv = env.client.get('/auth/discord/callback?code=good&state=forged')
    assert rv.status_code == 400
    assert 'Log in with Discord' in rv.get_data(as_text=True)
    assert env.discord.calls == []  # 没去换 token
    assert env.client.get('/api/me').status_code == 401
    with env.client.session_transaction() as s:
        assert env.mod.SESSION_STATE not in s  # state 用过即作废


def test_callback_without_login_started_is_rejected(env):
    rv = env.client.get('/auth/discord/callback?code=good&state=anything')
    assert rv.status_code == 400
    assert env.discord.calls == []


def test_callback_user_cancelled_or_exchange_failed(env):
    _, query = start_login(env.client)
    rv = env.client.get(f"/auth/discord/callback?error=access_denied&state={query['state'][0]}")
    assert rv.status_code == 400
    rv = login(env.client, code='bad')
    assert rv.status_code == 502
    assert env.client.get('/api/me').status_code == 401


def test_prompt_none_falls_back_to_consent(env):
    _, query = start_login(env.client, '/app/x')
    assert query['prompt'] == ['none']
    rv = env.client.get(f"/auth/discord/callback?error=interaction_required&state={query['state'][0]}")
    assert rv.status_code == 302
    location = urlparse(rv.headers['Location'])
    assert location.path == '/auth/discord/login'
    assert parse_qs(location.query) == {'prompt': ['consent'], 'next': ['/app/x']}
    rv = env.client.get(rv.headers['Location'])
    assert parse_qs(urlparse(rv.headers['Location']).query)['prompt'] == ['consent']
    assert env.discord.calls == []


def test_token_exchange_request(env):
    login(env.client)
    post = next(c for c in env.discord.calls if c[0] == 'post')
    assert post[1] == 'https://discord.com/api/v10/oauth2/token'
    assert post[2]['grant_type'] == 'authorization_code'
    assert post[2]['client_id'] == '123456'
    assert post[2]['client_secret'] == 'test-client-secret'
    assert post[2]['redirect_uri'] == PUBLIC_URL + '/auth/discord/callback'
    gets = [c for c in env.discord.calls if c[0] == 'get']
    assert {c[2] for c in gets} == {'Bearer at1'}


def test_secret_from_environment(env, monkeypatch):
    env.config.set('webinterface', 'discord_client_secret', '')
    assert not env.mod.configured()
    monkeypatch.setenv('DISCORD_CLIENT_SECRET', 'from-env')
    assert env.mod.client_secret() == 'from-env'
    login(env.client)
    post = next(c for c in env.discord.calls if c[0] == 'post')
    assert post[2]['client_secret'] == 'from-env'


def test_next_path_and_open_redirect(env):
    _, query = start_login(env.client, '/app/settings')
    rv = env.client.get(f"/auth/discord/callback?code=good&state={query['state'][0]}")
    assert rv.headers['Location'].endswith('/app/settings')
    env.client.get('/auth/logout')
    _, query = start_login(env.client, '//evil.example.com/x')
    rv = env.client.get(f"/auth/discord/callback?code=good&state={query['state'][0]}")
    assert urlparse(rv.headers['Location']).path == '/'
    assert 'evil' not in rv.headers['Location']


# ---- 身份映射 ----------------------------------------------------------------------

def test_new_discord_user_gets_own_identity(env):
    rv = login(env.client)
    assert rv.status_code == 302
    assert urlparse(rv.headers['Location']).path == '/'
    assert var.user_db.identity_for_discord('discord:42') == 'discord:42'
    me = env.client.get('/api/me').get_json()
    assert me['identity'] == 'discord:42'
    assert me['source'] == 'discord'
    assert me['display_name'] == 'Alice'
    assert me['can_have_playlists'] is True
    assert me['discord_id'] == '42'
    assert me['discord_username'] == 'alice'
    assert me['discord_avatar'] == 'https://cdn.discordapp.com/avatars/42/abc123.png?size=128'
    assert me['discord_login_available'] is True
    assert me['discord']['discord_name'] == 'Alice'  # 原有字段:绑定信息
    # 不用 /bind 就能有个人歌单
    assert env.client.post('/api/playlists', json={'name': 'Mix'}).status_code == 200


def test_prebound_user_keeps_their_identity(env):
    owner = 'alice@example.com'
    code, _ = var.user_db.create_bind_code(owner)
    assert var.user_db.consume_bind_code(code, 'discord:42', 'AliceNick') == owner
    var.user_db.set_alias(owner, 'Aiden')
    var.user_db.create_playlist(owner, 'Old favourites')
    login(env.client)
    me = env.client.get('/api/me').get_json()
    assert me['identity'] == owner
    assert me['source'] == 'discord'
    assert me['display_name'] == 'Aiden'
    names = [p['name'] for p in env.client.get('/api/playlists').get_json()['playlists']]
    assert names == ['Old favourites']
    # bot 记的服务器内昵称不被 OAuth 的全局名覆盖
    assert var.user_db.discord_link_for(owner)['discord_name'] == 'AliceNick'


def test_discord_session_beats_cloudflare_header(env):
    env.config.set('webinterface', 'auth_method', 'none')
    header = {'Cf-Access-Authenticated-User-Email': 'bob@example.com'}
    assert env.client.get('/api/me', headers=header).get_json()['identity'] == 'bob@example.com'
    login(env.client)
    me = env.client.get('/api/me', headers=header).get_json()
    assert me['identity'] == 'discord:42'
    assert me['source'] == 'discord'


def test_link_discord_login_when_identity_taken(env):
    # discord:42 这个身份已经被另一个 Discord 账号 /bind 走了
    code, _ = var.user_db.create_bind_code('discord:42')
    var.user_db.consume_bind_code(code, 'discord:7', 'Other')
    assert var.user_db.link_discord_login('discord:42', 'Alice') == ('discord:42', False)
    login(env.client)
    assert env.client.get('/api/me').get_json()['identity'] == 'discord:42'


# ---- 门禁 ----------------------------------------------------------------------------

def test_api_gets_401_and_html_redirects(env):
    rv = env.client.get('/api/status')
    assert rv.status_code == 401
    assert rv.get_json()['error'] == 'login_required'
    rv = env.client.get('/app/settings?tab=1')
    assert rv.status_code == 302
    location = urlparse(rv.headers['Location'])
    assert location.path == '/auth/discord/login'
    assert parse_qs(location.query)['next'] == ['/app/settings?tab=1']


def test_non_member_is_forbidden(env):
    var.bot.link.guild_id = 999
    login(env.client)
    rv = env.client.get('/api/me')
    assert rv.status_code == 403
    assert rv.get_json()['error'] == 'not_a_member'
    rv = env.client.get('/')
    assert rv.status_code == 403
    assert '/auth/logout' in rv.get_data(as_text=True)


def test_logout(env):
    login(env.client)
    assert env.client.get('/api/me').status_code == 200
    # GET 不退出(别的网站能用 <img> / 链接触发),只给一个 POST 按钮
    rv = env.client.get('/auth/logout')
    assert rv.status_code == 200
    assert '<form method="post"' in rv.get_data(as_text=True)
    assert env.client.get('/api/me').status_code == 200
    rv = env.client.post('/auth/logout')
    assert rv.get_json() == {'ok': True}
    assert env.client.get('/api/me').status_code == 401
    rv = env.client.get('/auth/logout')
    assert '/auth/discord/login' in rv.get_data(as_text=True)


def test_session_ignored_when_discord_login_unconfigured(env):
    login(env.client)
    env.config.set('webinterface', 'discord_client_id', '')
    assert env.client.get('/api/me').status_code == 401
    assert env.client.get('/auth/discord/login').status_code == 404


def test_token_mode_offers_discord_login(env):
    env.config.set('webinterface', 'auth_method', 'token')
    body = env.client.get('/').get_data(as_text=True)
    assert 'name="token"' in body
    assert 'Log in with Discord' in body
    assert '/auth/discord/login?next=%2F' in body
    login(env.client)
    assert env.client.get('/api/me').get_json()['source'] == 'discord'
    # 没配置 Discord 登录:令牌页和以前一样
    env.config.set('webinterface', 'discord_client_id', '')
    body = env.client.get('/').get_data(as_text=True)
    assert 'name="token"' in body
    assert 'Discord</a>' not in body


def test_password_mode_unaffected_by_discord_session(env):
    login(env.client)
    env.config.set('webinterface', 'auth_method', 'password')
    assert env.client.get('/api/me').status_code == 401
    assert 'Basic' in env.client.get('/api/me').headers.get('WWW-Authenticate', '')


# ---- 服务器缓存 / 辅助函数 ----------------------------------------------------------

def test_guilds_cached_and_helpers(env):
    login(env.client)
    mod = env.mod
    guilds = mod.discord_guilds('42')
    assert [g['id'] for g in guilds] == ['111', '222', '333']
    assert guilds[0] == {'id': '111', 'name': 'Home', 'icon': 'ic1', 'owner': False, 'permissions': 32}
    assert env.discord.count('/guilds') == 1  # 登录时拉过一次,之后走缓存
    for _ in range(3):
        env.client.get('/api/me')
    assert env.discord.count('/guilds') == 1
    assert mod.can_manage(mod.find_guild('42', 111))      # MANAGE_GUILD
    assert mod.can_manage(mod.find_guild('42', '222'))    # owner
    assert not mod.can_manage(mod.find_guild('42', 333))
    assert mod.can_manage({'owner': False, 'permissions': mod.PERM_ADMINISTRATOR})
    assert not mod.can_manage(None)
    assert mod.find_guild('42', 999) is None
    assert mod.discord_guilds('nobody') == []
    assert mod.discord_user_id(web_users.Identity(key='x@y.z', email='x@y.z')) is None
    assert mod.discord_guilds(web_users.Identity(key='x@y.z', email='x@y.z')) == []
    # 返回的是副本,改了不影响缓存
    guilds[0]['name'] = 'changed'
    assert mod.discord_guilds('42')[0]['name'] == 'Home'


def test_guilds_refresh_when_stale_and_rate_limit(env):
    login(env.client)
    mod = env.mod
    entry = mod._cache['42']
    env.discord.guilds = env.discord.guilds[:1]
    entry['fetched_at'] -= mod.GUILDS_TTL + 1
    assert [g['id'] for g in mod.discord_guilds('42')] == ['111']
    assert env.discord.count('/guilds') == 2
    # 429:保留旧列表,按 retry_after 退避
    env.discord.guilds_status = 429
    entry['fetched_at'] -= mod.GUILDS_TTL + 1
    assert [g['id'] for g in mod.discord_guilds('42')] == ['111']
    assert entry['retry_at'] >= time.time() + 25
    mod.discord_guilds('42')
    assert env.discord.count('/guilds') == 3  # 退避期间不再请求


def test_expired_token_is_refreshed(env):
    login(env.client)
    mod = env.mod
    entry = mod._cache['42']
    entry['token']['expires_at'] = time.time() - 10
    entry['fetched_at'] = 0
    env.client.get('/api/me')
    refresh = [c for c in env.discord.calls if c[0] == 'post' and c[2]['grant_type'] == 'refresh_token']
    assert refresh and refresh[0][2]['refresh_token'] == 'rt1'
    assert entry['token']['access_token'] == 'at2'
    assert env.discord.calls[-1][2] == 'Bearer at2'
    assert entry['token']['refresh_token'] == 'rt2'
    with env.client.session_transaction() as s:
        assert 'refresh_token' not in str(dict(s))  # Discord 的令牌只放服务端,不进 Cookie


def test_restart_requires_a_fresh_login(env):
    # Discord 令牌只在服务端内存里:重启后会话里没有令牌可用,得重新登录(不再从 Cookie 里恢复)
    login(env.client)
    env.mod._cache.clear()  # 模拟重启
    rv = env.client.get('/api/me')
    assert rv.status_code in (401, 403)
    assert env.discord.count('/guilds') == 1


def test_identity_helpers_in_request(env):
    login(env.client)
    with env.client:
        assert env.client.get('/api/me').status_code == 200
        ident = web_users.current_identity()  # 请求上下文在 with 块里保留
        assert ident.discord_id == '42'
        assert env.mod.discord_user_id(ident) == '42'
        assert env.mod.discord_user_id() == '42'
        assert [g['id'] for g in env.mod.discord_guilds(ident)] == ['111', '222', '333']
        assert env.mod.shares_guild_with_bot(ident)
