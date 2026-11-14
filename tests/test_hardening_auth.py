# coding=utf-8
"""登录 / 授权加固:Discord token 失效时收回权限、token 不进 Cookie、退出只认 POST、换 token 的熔断和预算、
Activity 换令牌的校验和限流、撤销表、安全响应头、IPv6 限流键、成员 / 封禁检查。假的 Discord 和 Hub。"""
import configparser
import os
import sys
import time
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import util  # noqa: E402
import variables as var  # noqa: E402
import web_users  # noqa: E402
from bot.store import GuildStore  # noqa: E402
from database import DatabaseMigration, MusicDatabase, SettingsDatabase  # noqa: E402
from tests.test_web_auth_discord import FakeDiscord, FakeResp, login  # noqa: E402
from tests.test_web_guilds import HOME, OWNER, SECOND, THIRD, FakeHub  # noqa: E402

USER = '42'          # FakeDiscord 的用户:OAuth 列表里有 111(管理服务器)、222、333
VOICE = '5550'
OTHER_VOICE = '5551'
CODE = 'GoodActivityCode1234'


class Discord(FakeDiscord):
    """FakeDiscord + 像样的 Activity code,token 端点可以设成 429 / 400。"""

    def __init__(self):
        super().__init__()
        self.token_status = 200

    def post(self, url, data=None, **kwargs):
        if self.token_status == 429:
            self.calls.append(('post', url, dict(data or {})))
            return FakeResp(429, {'retry_after': 30})
        if self.token_status == 400:
            self.calls.append(('post', url, dict(data or {})))
            return FakeResp(400, {'error': 'invalid_grant'})
        if (data or {}).get('code') == CODE:
            data = dict(data, code='good')
        return super().post(url, data=data, **kwargs)


class Hub(FakeHub):
    """FakeHub + 语音状态;client 不是 None 时 is_member 的 False 才算数(像连上了的 Hub)。"""

    def __init__(self):
        super().__init__()
        self.voice = {}
        self.client = None

    def voice_channel_of(self, guild_id, user_id):
        channel = self.voice.get((str(guild_id), str(user_id)))
        return int(channel) if channel else None


@pytest.fixture
def env(monkeypatch, tmp_path):
    config = configparser.ConfigParser(interpolation=None, allow_no_value=True)
    config.read(util.solve_filepath('configuration.default.ini'), encoding='utf-8')
    config.set('bot', 'admin', OWNER)
    config.set('webinterface', 'auth_method', 'discord')
    config.set('webinterface', 'activity_enabled', 'True')
    config.set('webinterface', 'discord_client_id', '123456')
    config.set('webinterface', 'discord_client_secret', 'test-client-secret')
    config.set('webinterface', 'public_url', 'https://music.example.test/')
    monkeypatch.setattr(var, 'config', config)
    monkeypatch.setattr(var, 'language', 'en_US')
    db = SettingsDatabase(str(tmp_path / 'settings.db'))
    DatabaseMigration(db, MusicDatabase(str(tmp_path / 'music.db'))).migrate()
    monkeypatch.setattr(var, 'db', db)
    monkeypatch.setattr(var, 'store', GuildStore(db.db_path))
    monkeypatch.setattr(var, 'user_db', web_users.UserDatabase(str(tmp_path / 'users.db')))
    hub = Hub()
    hub.voice[(HOME, USER)] = VOICE
    monkeypatch.setattr(var, 'hub', hub, raising=False)
    monkeypatch.setattr(var, 'bot', hub._sessions[HOME])
    monkeypatch.delenv('DISCORD_CLIENT_SECRET', raising=False)
    import constants
    constants.load_lang('en_US')
    import interface
    import web_activity
    import web_auth_discord
    web_auth_discord._cache.clear()
    monkeypatch.setattr(web_auth_discord, '_token_backoff_until', 0.0)
    interface.web.secret_key = 'test'
    interface.bad_access_count.clear()
    interface.banned_ip.clear()
    fake = Discord()
    monkeypatch.setattr(web_auth_discord.requests, 'post', fake.post)
    monkeypatch.setattr(web_auth_discord.requests, 'get', fake.get)
    yield types.SimpleNamespace(client=interface.web.test_client(), discord=fake, hub=hub, config=config,
                                auth=web_auth_discord, activity=web_activity, db=db)
    web_auth_discord._cache.clear()


def exchange(client, code=CODE, guild=HOME, channel=VOICE, **kw):
    return client.post('/api/activity/token', json={'code': code, 'guild_id': guild, 'channel_id': channel}, **kw)


def activity_token(client, **kw):
    rv = exchange(client, **kw)
    assert rv.status_code == 200, rv.get_data(as_text=True)
    return rv.get_json()['token']


def bearer(token, guild=None):
    headers = {'Authorization': f'Bearer {token}'}
    if guild:
        headers['X-DJ-Guild'] = guild
    return headers


def guild_ids(client, **kw):
    return [g['id'] for g in client.get('/api/guilds', **kw).get_json()['guilds']]


def token_posts(fake):
    return [c for c in fake.calls if c[0] == 'post']


# ---- 1. Discord 说 token 不能用了:收回权限 ------------------------------------------

@pytest.mark.parametrize('status', [401, 403])
def test_revoked_authorization_drops_guilds(env, status):
    login(env.client)
    assert env.client.get('/api/me').status_code == 200
    entry = env.auth._cache[USER]
    entry['fetched_at'] -= env.auth.GUILDS_TTL + 1
    env.discord.guilds_status = status
    assert env.auth.discord_guilds(USER) == []
    assert entry['token'] is None and entry['guilds'] == []
    rv = env.client.get('/api/me')
    assert rv.status_code == 403 and rv.get_json()['error'] == 'not_a_member'


def test_invalid_grant_on_refresh_fails_closed(env):
    login(env.client)
    entry = env.auth._cache[USER]
    entry['token']['expires_at'] = time.time() - 10
    entry['fetched_at'] = 0
    env.discord.token_status = 400
    assert env.auth.discord_guilds(USER) == []
    assert entry['token'] is None
    assert not env.auth.can_manage(env.auth.find_guild(USER, HOME))


def test_transient_errors_keep_the_list_only_for_a_while(env):
    login(env.client)
    entry = env.auth._cache[USER]
    env.discord.guilds_status = 500
    entry['fetched_at'] -= env.auth.GUILDS_TTL + 1
    assert [g['id'] for g in env.auth.discord_guilds(USER)] == ['111', '222', '333']
    assert entry['token'] is not None          # 5xx 不是 token 的问题
    entry['fetched_at'] -= env.auth.GUILDS_TTL
    entry['retry_at'] = 0
    assert env.auth.discord_guilds(USER) == []


# ---- 2. Cookie 里没有 Discord token ---------------------------------------------------

def test_oauth_token_not_in_cookie(env):
    login(env.client)
    with env.client.session_transaction() as s:
        assert set(s.keys()) <= {env.auth.SESSION_USER, '_permanent'}
        assert 'at1' not in repr(dict(s)) and 'rt1' not in repr(dict(s))
    assert env.auth._cache[USER]['token']['access_token'] == 'at1'


def test_session_needs_the_server_side_token(env):
    login(env.client)
    env.auth._cache.clear()  # 重启
    rv = env.client.get('/api/me')
    assert rv.status_code == 401 and rv.get_json()['error'] == 'login_required'


def test_legacy_cookie_token_is_dropped(env):
    login(env.client)
    with env.client.session_transaction() as s:
        s[env.auth.LEGACY_SESSION_TOKEN] = {'access_token': 'old', 'refresh_token': 'old'}
    assert env.client.get('/api/me').status_code == 200
    with env.client.session_transaction() as s:
        assert env.auth.LEGACY_SESSION_TOKEN not in s


def test_bot_owner_still_shares_guild(env):
    env.discord.user = dict(env.discord.user, id=OWNER)
    env.discord.guilds = []
    login(env.client)
    assert env.client.get('/api/me').status_code == 200


# ---- 3. 退出:GET 不改状态 ----------------------------------------------------------------

def test_logout_get_does_not_log_out(env):
    login(env.client)
    rv = env.client.get('/auth/logout', headers={'Accept': 'text/html'})
    assert rv.status_code == 200
    body = rv.get_data(as_text=True)
    assert 'method="post"' in body and 'action="/auth/logout"' in body
    assert env.client.get('/api/me').status_code == 200
    rv = env.client.get('/auth/logout', headers={'Accept': 'application/json'})
    assert rv.status_code == 405
    assert env.client.get('/api/me').status_code == 200


def test_logout_post_json_and_form(env):
    login(env.client)
    rv = env.client.post('/auth/logout', headers={'Accept': 'application/json'})
    assert rv.get_json() == {'ok': True}
    assert env.client.get('/api/me').status_code == 401
    # 前端 POST 完再跳到 GET /auth/logout:已退出的页面
    rv = env.client.get('/auth/logout', headers={'Accept': 'text/html'})
    assert rv.status_code == 200 and '/auth/discord/login' in rv.get_data(as_text=True)
    # 页面上的按钮(表单 POST)
    login(env.client)
    rv = env.client.post('/auth/logout', headers={'Accept': 'text/html,*/*;q=0.8'})
    assert rv.status_code == 200 and rv.mimetype == 'text/html'
    assert env.client.get('/api/me').status_code == 401


# ---- 4. 换 token 的熔断 / 预算 ---------------------------------------------------------

def test_token_endpoint_429_opens_the_breaker(env):
    env.discord.token_status = 429
    with pytest.raises(env.auth.DiscordError) as e:
        env.auth.exchange_code('x')
    assert e.value.status == 429
    assert len(token_posts(env.discord)) == 1
    env.discord.token_status = 200
    with pytest.raises(env.auth.DiscordError) as e:
        env.auth.exchange_activity_code(CODE)
    assert e.value.status == 429 and e.value.retry_after > 20
    assert len(token_posts(env.discord)) == 1   # 退避期间没去打 Discord


def test_breaker_minimum_backoff(env, monkeypatch):
    env.discord.token_status = 429
    monkeypatch.setattr(env.discord, 'post', lambda *a, **kw: FakeResp(429, {'retry_after': 0.1}))
    monkeypatch.setattr(env.auth.requests, 'post', env.discord.post)
    with pytest.raises(env.auth.DiscordError):
        env.auth.exchange_code('x')
    assert env.auth._token_backoff_until - time.monotonic() > 4


def test_process_wide_exchange_budget(env, monkeypatch):
    monkeypatch.setattr(env.auth, 'TOKEN_BUDGET', (2, 60))
    for _ in range(2):
        env.auth.exchange_activity_code(CODE)
    with pytest.raises(env.auth.DiscordError) as e:
        env.auth.exchange_activity_code(CODE)
    assert e.value.status == 503
    assert len(token_posts(env.discord)) == 2
    rv = exchange(env.client)
    assert rv.status_code == 502 and rv.get_json()['error'] == 'discord_unavailable'


# ---- 5. Activity 换令牌 --------------------------------------------------------------------

@pytest.mark.parametrize('body', [
    {'code': 'short', 'guild_id': HOME, 'channel_id': VOICE},
    {'code': 'a' * 65, 'guild_id': HOME, 'channel_id': VOICE},
    {'code': 'has-dash-not-alnum-1234', 'guild_id': HOME, 'channel_id': VOICE},
    {'code': CODE, 'guild_id': '0123', 'channel_id': VOICE},
    {'code': CODE, 'guild_id': HOME, 'channel_id': True},
    {'code': CODE, 'guild_id': HOME, 'channel_id': '1' * 21},
])
def test_activity_input_validated_before_calling_discord(env, body):
    assert env.client.post('/api/activity/token', json=body).status_code == 400
    assert env.discord.calls == []


def test_activity_guild_not_served_refused_before_exchange(env):
    rv = exchange(env.client, guild='222')
    assert rv.status_code == 403 and rv.get_json()['error'] == 'guild_not_served'
    assert env.discord.calls == []


def test_activity_only_failures_count_per_ip(env, monkeypatch):
    import web_security
    monkeypatch.setitem(web_security.RULES, 'activity_token_fail', (('ip', 3, 60),))
    # 成功的不算:同一个代理 IP 后面的人都能换
    for _ in range(5):
        activity_token(env.client)
    env.discord.token_status = 400
    for _ in range(3):
        assert exchange(env.client).status_code == 401
    before = len(env.discord.calls)
    rv = exchange(env.client)
    assert rv.status_code == 429
    assert len(env.discord.calls) == before     # 被拦下时不再出站
    # 别的 IP 不受影响
    env.discord.token_status = 200
    assert exchange(env.client, environ_base={'REMOTE_ADDR': '10.9.9.9'}).status_code == 200


def test_activity_context_rejections_count_as_failures(env, monkeypatch):
    import web_security
    monkeypatch.setitem(web_security.RULES, 'activity_token_fail', (('ip', 2, 60),))
    for _ in range(2):
        assert exchange(env.client, channel=OTHER_VOICE).status_code == 403
    assert exchange(env.client).status_code == 429


def test_activity_login_limited_per_user(env, monkeypatch):
    import web_security
    monkeypatch.setitem(web_security.RULES, 'activity_login', (('client', 2, 60),))
    activity_token(env.client)
    activity_token(env.client)
    assert exchange(env.client).status_code == 429
    # 别的 Discord 账号(同一个 IP)照常
    env.discord.user = dict(env.discord.user, id='77')
    env.hub.voice[(HOME, '77')] = VOICE
    assert exchange(env.client).status_code == 200


def test_activity_refresh_and_logout_rate_limited(env, monkeypatch):
    import web_security
    monkeypatch.setitem(web_security.RULES, 'activity_refresh', (('client', 1, 60),))
    token = activity_token(env.client)
    rv = env.client.post('/api/activity/refresh', headers=bearer(token))
    assert rv.status_code == 200
    fresh = rv.get_json()['token']
    assert env.client.post('/api/activity/refresh', headers=bearer(fresh)).status_code == 429
    assert env.client.post('/api/activity/logout', headers=bearer(fresh)).status_code == 429


def test_rules_registered():
    import web_security
    rules = web_security.RULES
    assert rules['activity_token_fail'] == (('ip', 30, 60),)
    assert rules['activity_login'] == (('client', 10, 60),)
    assert rules['activity_refresh'] == (('client', 6, 60),)
    assert rules['upload'] == (('client', 20, 60),)
    assert 'activity_token' not in rules


def test_max_ttl_is_an_hour(env):
    env.config.set('webinterface', 'activity_token_ttl', '86400')
    assert env.activity.token_ttl() == 3600


def test_revoke_persists_and_prunes_at_most_every_interval(env):
    mod = env.activity
    mod.revoke('already-expired', time.time() - 10)
    assert 'already-expired' not in dict(env.db.items(mod.REVOKED_SECTION))
    mod.revoke('soon', time.time() + 0.05)
    time.sleep(0.1)
    mod.revoke('later', time.time() + 100)
    # 上一次清理刚做过:过期的 'soon' 要等到下一个间隔
    assert set(dict(env.db.items(mod.REVOKED_SECTION))) == {'soon', 'later'}
    mod._revoked['pruned_at'] -= mod.PRUNE_INTERVAL + 1
    mod.revoke('another', time.time() + 100)
    assert set(dict(env.db.items(mod.REVOKED_SECTION))) == {'later', 'another'}
    assert 'soon' not in mod._revoked['jti']


# ---- 6. 安全响应头 / IPv6 限流键 ------------------------------------------------------------

def test_hsts_only_for_https_public_url(env):
    rv = env.client.get('/api/activity/config')
    assert rv.headers['Strict-Transport-Security'] == 'max-age=31536000'
    env.config.set('webinterface', 'public_url', 'http://192.168.1.2:8181/')
    assert 'Strict-Transport-Security' not in env.client.get('/api/activity/config').headers


def test_error_responses_not_cached(env):
    rv = env.client.get('/api/queue')
    assert rv.status_code == 401 and rv.headers['Cache-Control'] == 'no-store'
    assert 'no-store' not in (env.client.get('/api/activity/config').headers.get('Cache-Control') or '')
    import flask

    import web_security
    resp = flask.Response('x', status=404, headers={'Cache-Control': 'max-age=5'})
    assert web_security.apply_security_headers(resp).headers['Cache-Control'] == 'max-age=5'


def test_ipv6_clients_share_their_64(env, monkeypatch):
    import web_security
    assert web_security.ip_bucket('2001:db8:1:2:aaaa::1') == '2001:db8:1:2::/64'
    assert web_security.ip_bucket('2001:db8:1:2:bbbb::9') == '2001:db8:1:2::/64'
    assert web_security.ip_bucket('::ffff:10.0.0.1') == '10.0.0.1'
    assert web_security.ip_bucket('10.0.0.1') == '10.0.0.1'
    assert web_security.ip_bucket('unknown') == 'unknown'
    monkeypatch.setitem(web_security.RULES, 'activity_token_fail', (('ip', 1, 60),))
    env.discord.token_status = 400
    assert exchange(env.client, environ_base={'REMOTE_ADDR': '2001:db8:1:2::1'}).status_code == 401
    assert exchange(env.client, environ_base={'REMOTE_ADDR': '2001:db8:1:2::ffff'}).status_code == 429
    assert exchange(env.client, environ_base={'REMOTE_ADDR': '2001:db8:1:3::1'}).status_code == 401


# ---- 7. 成员 / 封禁 --------------------------------------------------------------------------

def test_kicked_member_loses_guild_immediately(env):
    login(env.client)
    assert HOME in guild_ids(env.client)
    env.hub.client = object()                  # Hub 连上了:它说不是成员就当真
    env.hub.members = {SECOND: {USER}}         # 被 HOME 踢了,OAuth 缓存里还有
    ids = guild_ids(env.client)
    assert HOME not in ids and SECOND in ids
    rv = env.client.get('/api/queue', headers={'X-DJ-Guild': HOME})
    assert rv.status_code == 403


def test_activity_guild_requires_current_membership(env):
    # OAuth 列表里没有 THIRD,靠 bot 的成员查询进来
    env.hub.members = {THIRD: {USER}}
    env.hub.voice[(THIRD, USER)] = OTHER_VOICE
    token = activity_token(env.client, guild=THIRD, channel=OTHER_VOICE)
    assert env.client.get('/api/queue', headers=bearer(token)).get_json()['version'] == 404
    env.hub.client = object()
    env.hub.members = {}
    rv = env.client.get('/api/queue', headers=bearer(token, THIRD))
    assert rv.status_code == 403


def test_global_ban_blocks_web_and_activity(env):
    login(env.client)
    assert env.client.get('/api/queue').status_code == 200
    var.store.add_rule('', 'user_ban', USER)
    rv = env.client.get('/api/queue')
    assert rv.status_code == 403 and rv.get_json()['error'] == 'user_banned'
    rv = exchange(env.client)
    assert rv.status_code == 403 and rv.get_json()['error'] == 'user_banned'
    # 不分服务器的接口照常
    assert env.client.get('/api/me').status_code == 200


def test_guild_ban_spares_managers(env):
    login(env.client)
    var.store.add_rule(HOME, 'user_ban', USER)
    var.store.add_rule(SECOND, 'user_ban', USER)
    # HOME(111)上有管理服务器权限:本服务器的封禁管不到
    assert env.client.get('/api/queue', headers={'X-DJ-Guild': HOME}).status_code == 200
    rv = env.client.get('/api/queue', headers={'X-DJ-Guild': SECOND})
    assert rv.status_code == 403 and rv.get_json()['error'] == 'user_banned'


def test_owner_exempt_from_global_ban(env):
    env.discord.user = dict(env.discord.user, id=OWNER)
    login(env.client)
    var.store.add_rule('', 'user_ban', OWNER)
    assert env.client.get('/api/queue').status_code == 200


def test_refresh_refused_once_banned(env):
    token = activity_token(env.client)
    var.store.add_rule('', 'user_ban', USER)
    rv = env.client.post('/api/activity/refresh', headers=bearer(token))
    assert rv.status_code == 403 and rv.get_json()['error'] == 'user_banned'
