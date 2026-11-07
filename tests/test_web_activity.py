# coding=utf-8
"""Discord Activity:用 SDK 的 code 换我们自己的 Bearer 令牌、核对 SDK 给的服务器 / 语音频道、
Bearer 鉴权(过期 / 撤销 / 刷新)、iframe 的页面外壳、外部图片代理。假的 Discord 接口和 Hub。"""
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
from tests.test_web_auth_discord import FakeDiscord  # noqa: E402
from tests.test_web_guilds import HOME, OWNER, SECOND, THIRD, FakeHub  # noqa: E402

USER = '42'          # FakeDiscord 的用户:在 111(管理服务器权限)、222、333
VOICE = '5550'       # HOME 里的语音频道
OTHER_VOICE = '5551'


class VoiceHub(FakeHub):
    """FakeHub + 网关语音状态 {(guild, user): channel}。"""

    def __init__(self):
        super().__init__()
        self.voice = {}

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
    hub = VoiceHub()
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
    web_activity._image_cache.clear()
    web_activity._known_images.clear()
    interface.web.secret_key = 'test'
    interface.bad_access_count.clear()
    interface.banned_ip.clear()
    fake = FakeDiscord()
    monkeypatch.setattr(web_auth_discord.requests, 'post', fake.post)
    monkeypatch.setattr(web_auth_discord.requests, 'get', fake.get)
    yield types.SimpleNamespace(client=interface.web.test_client(), discord=fake, hub=hub, config=config,
                                mod=web_activity, db=db)
    web_auth_discord._cache.clear()


def exchange(client, code='good', guild=HOME, channel=VOICE):
    return client.post('/api/activity/token', json={'code': code, 'guild_id': guild, 'channel_id': channel})


def token_for(client, **kw):
    rv = exchange(client, **kw)
    assert rv.status_code == 200, rv.get_data(as_text=True)
    return rv.get_json()['token']


def bearer(token):
    return {'Authorization': f'Bearer {token}'}


def queue(client, token, guild=None):
    headers = bearer(token)
    if guild:
        headers['X-DJ-Guild'] = guild
    return client.get('/api/queue', headers=headers)


# ---- 换令牌 ----------------------------------------------------------------------

def test_config_endpoint(env):
    data = env.client.get('/api/activity/config').get_json()
    assert data['enabled'] is True
    assert data['client_id'] == '123456'
    assert data['scopes'] == ['identify', 'guilds']
    env.config.set('webinterface', 'activity_enabled', 'False')
    assert env.client.get('/api/activity/config').get_json() == {'enabled': False}
    assert exchange(env.client).status_code == 404


def test_disabled_without_discord_credentials(env):
    env.config.set('webinterface', 'discord_client_secret', '')
    assert env.client.get('/api/activity/config').get_json() == {'enabled': False}
    assert exchange(env.client).status_code == 404


def test_exchange_issues_our_token(env):
    rv = exchange(env.client)
    assert rv.status_code == 200, rv.get_data(as_text=True)
    data = rv.get_json()
    # SDK 的 authenticate() 要 Discord 的 access token;我们自己的令牌是另一个
    assert data['access_token'] == 'at1'
    assert data['token'] and data['token'] != 'at1'
    assert data['guild_id'] == HOME and data['channel_id'] == VOICE
    assert data['user']['id'] == USER
    assert 0 < data['expires_in'] <= 900
    # 换令牌:SDK 授权没有 redirect_uri,这里也不能带
    post = next(c for c in env.discord.calls if c[0] == 'post')
    assert post[2]['grant_type'] == 'authorization_code'
    assert post[2]['code'] == 'good'
    assert post[2]['client_secret'] == 'test-client-secret'
    assert 'redirect_uri' not in post[2]
    assert env.discord.count('/users/@me') == 1 and env.discord.count('/users/@me/guilds') == 1
    # 没有 Set-Cookie:iframe 里不用 Cookie
    assert 'Set-Cookie' not in rv.headers


def test_bearer_token_authenticates_api_and_defaults_to_the_activity_guild(env):
    token = token_for(env.client)
    rv = queue(env.client, token)
    assert rv.status_code == 200
    assert rv.get_json()['version'] == 101     # HOME 的会话,没带 X-DJ-Guild
    me = env.client.get('/api/me', headers=bearer(token)).get_json()
    assert me['discord_id'] == USER
    assert me['source'] == 'discord'
    assert me['identity'] == f'discord:{USER}'
    # 身份关联和 Discord 网页登录一样
    assert var.user_db.identity_for_discord(f'discord:{USER}') == f'discord:{USER}'
    # 还是走 web_context 的权限:111 上有管理服务器权限
    guilds = {g['id']: g for g in env.client.get('/api/guilds', headers=bearer(token)).get_json()['guilds']}
    assert guilds[HOME]['can_manage'] is True
    assert guilds[HOME]['selected'] is True


def test_activity_guild_is_default_even_when_not_home(env):
    env.hub.voice[(SECOND, USER)] = OTHER_VOICE
    token = token_for(env.client, guild=SECOND, channel=OTHER_VOICE)
    assert queue(env.client, token).get_json()['version'] == 303
    # 其他服务器仍按规则:THIRD 用户不在 → 403
    assert queue(env.client, token, THIRD).status_code == 403


def test_member_via_gateway_when_oauth_guilds_miss_it(env):
    # OAuth 的服务器列表里没有 THIRD,但 bot 查得到他是成员,并且在语音里
    env.hub.members = {THIRD: {USER}}
    env.hub.voice[(THIRD, USER)] = OTHER_VOICE
    token = token_for(env.client, guild=THIRD, channel=OTHER_VOICE)
    assert queue(env.client, token).get_json()['version'] == 404


@pytest.mark.parametrize('auth_method', ['none', 'token', 'password', 'discord'])
def test_bearer_accepted_whatever_the_auth_method(env, auth_method):
    env.config.set('webinterface', 'auth_method', auth_method)
    token = token_for(env.client)
    assert queue(env.client, token).status_code == 200


def test_bearer_ignored_when_activity_disabled(env):
    token = token_for(env.client)
    env.config.set('webinterface', 'activity_enabled', 'False')
    env.config.set('webinterface', 'auth_method', 'password')
    assert queue(env.client, token).status_code == 401
    assert 'Basic' in queue(env.client, token).headers.get('WWW-Authenticate', '')


def test_bearer_works_with_cloudflare_jwt_verification(env):
    # Activity 经 Discord 代理访问,没有 Cloudflare Access 的 JWT;Bearer 已经验过,不再要求
    env.config.set('webinterface', 'access_team_domain', 'team.cloudflareaccess.com')
    env.config.set('webinterface', 'access_aud', 'aud')
    token = token_for(env.client)
    assert queue(env.client, token).status_code == 200


# ---- 不信客户端给的上下文 ------------------------------------------------------------

def test_forged_guild_not_a_member(env):
    # 用户不在 THIRD(OAuth 列表里没有,bot 也查不到),即使伪造了语音状态也不行
    env.hub.voice[(THIRD, USER)] = OTHER_VOICE
    rv = exchange(env.client, guild=THIRD, channel=OTHER_VOICE)
    assert rv.status_code == 403
    assert rv.get_json()['error'] == 'not_a_member'


def test_forged_guild_not_served_by_bot(env):
    # 222 用户在(是主人),但 bot 不在那里
    rv = exchange(env.client, guild='222', channel=VOICE)
    assert rv.status_code == 403
    assert rv.get_json()['error'] == 'guild_not_served'


def test_forged_channel_rejected(env):
    rv = exchange(env.client, channel=OTHER_VOICE)
    assert rv.status_code == 403
    assert rv.get_json()['error'] == 'not_in_voice_channel'


def test_user_not_in_voice_rejected(env):
    env.hub.voice.clear()
    rv = exchange(env.client)
    assert rv.status_code == 403
    assert rv.get_json()['error'] == 'not_in_voice_channel'


def test_owner_still_needs_the_voice_channel(env):
    env.discord.user = dict(env.discord.user, id=OWNER)
    rv = exchange(env.client)
    assert rv.get_json()['error'] == 'not_in_voice_channel'
    env.hub.voice[(HOME, OWNER)] = VOICE
    assert exchange(env.client).status_code == 200


@pytest.mark.parametrize('body', [
    {'guild_id': HOME, 'channel_id': VOICE},                      # 没有 code
    {'code': 'good', 'channel_id': VOICE},                        # 私信里打开:没有服务器
    {'code': 'good', 'guild_id': HOME},
    {'code': 'good', 'guild_id': '1; drop', 'channel_id': VOICE},
    {'code': ['good'], 'guild_id': HOME, 'channel_id': VOICE},
])
def test_bad_requests(env, body):
    rv = env.client.post('/api/activity/token', json=body)
    assert rv.status_code == 400
    assert env.discord.calls == []


def test_bad_code_and_discord_down(env):
    rv = exchange(env.client, code='bad')
    assert rv.status_code == 401
    assert rv.get_json()['error'] == 'discord_auth_failed'
    env.discord.guilds_status = 500
    rv = exchange(env.client)
    assert rv.status_code == 502


def test_legacy_single_guild_uses_the_link_snapshot(env, monkeypatch):
    # 没有 Hub(旧的单服务器部署):语音状态看 var.bot.link.users
    monkeypatch.setattr(var, 'hub', None)
    users = {int(USER): types.SimpleNamespace(channel_id=int(VOICE))}
    monkeypatch.setattr(var, 'bot', types.SimpleNamespace(
        guild_id=int(HOME), link=types.SimpleNamespace(guild_id=int(HOME), users=users, bot_name='dj'),
        command_name=lambda key: key))
    assert exchange(env.client, channel=OTHER_VOICE).get_json()['error'] == 'not_in_voice_channel'
    assert exchange(env.client).status_code == 200


# ---- 令牌:过期 / 篡改 / 撤销 / 刷新 -----------------------------------------------------

def test_token_expires(env, monkeypatch):
    token = token_for(env.client)
    assert queue(env.client, token).status_code == 200
    real = time.time
    monkeypatch.setattr(time, 'time', lambda: real() + 901)
    rv = queue(env.client, token)
    assert rv.status_code == 401
    assert rv.get_json()['error'] == 'activity_token_invalid'


def test_lowering_the_ttl_applies_to_issued_tokens(env, monkeypatch):
    token = token_for(env.client)
    env.config.set('webinterface', 'activity_token_ttl', '60')
    real = time.time
    monkeypatch.setattr(time, 'time', lambda: real() + 120)
    assert queue(env.client, token).status_code == 401


def test_tampered_or_foreign_token_rejected(env):
    token = token_for(env.client)
    assert queue(env.client, token[:-2] + ('AA' if token[-2:] != 'AA' else 'BB')).status_code == 401
    assert queue(env.client, 'not-a-token').status_code == 401
    # 换了 Flask 密钥,旧令牌全部失效
    import interface
    interface.web.secret_key = 'rotated'
    try:
        assert queue(env.client, token).status_code == 401
    finally:
        interface.web.secret_key = 'test'


def test_bad_bearer_does_not_fall_back_to_session(env):
    # 带了 Bearer 就只看 Bearer:令牌坏了就是 401,不会悄悄用别的登录方式
    env.config.set('webinterface', 'auth_method', 'none')
    rv = env.client.get('/api/me', headers=bearer('garbage'))
    assert rv.status_code == 401
    assert rv.get_json()['error'] == 'activity_token_invalid'
    assert env.client.get('/api/me').status_code == 200


def test_logout_revokes_the_token(env):
    token = token_for(env.client)
    other = token_for(env.client)
    assert env.client.post('/api/activity/logout', headers=bearer(token)).get_json() == {'ok': True}
    assert queue(env.client, token).status_code == 401
    assert queue(env.client, other).status_code == 200      # 只作废这一个
    # 撤销记录在设置库里:重启(内存表清空)后照样作废
    env.mod._revoked['db'] = None
    assert queue(env.client, token).status_code == 401


def test_revoke_all_tokens_of_a_user(env):
    token = token_for(env.client)
    env.mod.revoke_user(USER)
    assert queue(env.client, token).status_code == 401
    # 之后新签发的不受影响
    time.sleep(0.01)
    assert queue(env.client, token_for(env.client)).status_code == 200


def test_expired_revocations_are_pruned(env, monkeypatch):
    env.mod.revoke('old', time.time() - 10)
    env.mod.revoke('new', time.time() + 100)
    assert dict(env.db.items(env.mod.REVOKED_SECTION)).keys() == {'new'}


def test_refresh_rotates_the_token(env):
    token = token_for(env.client)
    rv = env.client.post('/api/activity/refresh', headers=bearer(token))
    assert rv.status_code == 200
    fresh = rv.get_json()['token']
    assert fresh != token
    assert rv.get_json()['guild_id'] == HOME
    assert queue(env.client, fresh).status_code == 200
    assert queue(env.client, token).status_code == 401


def test_refresh_refused_after_leaving_the_voice_channel(env):
    token = token_for(env.client)
    env.hub.voice[(HOME, USER)] = OTHER_VOICE
    rv = env.client.post('/api/activity/refresh', headers=bearer(token))
    assert rv.status_code == 403
    assert rv.get_json()['error'] == 'not_in_voice_channel'
    assert queue(env.client, token).status_code == 401


def test_refresh_and_logout_need_a_bearer(env):
    env.config.set('webinterface', 'auth_method', 'none')
    assert env.client.post('/api/activity/refresh').status_code == 401
    assert env.client.post('/api/activity/logout').status_code == 401


# ---- 页面外壳 ----------------------------------------------------------------------

def test_shell_loads_without_login_inside_discord(env):
    launch = '/?instance_id=i-1&frame_id=f-1&platform=desktop&guild_id=111&channel_id=5550'
    rv = env.client.get(launch)
    assert rv.status_code == 200
    assert b'<div id="app">' in rv.data
    assets = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'webui', 'dist', 'assets')
    asset = next(n for n in os.listdir(assets) if n.endswith('.js'))
    assert env.client.get(f'/assets/{asset}').status_code == 200
    # 不是从 Discord 打开的:照旧跳去登录
    assert env.client.get('/').status_code == 302
    env.config.set('webinterface', 'activity_enabled', 'False')
    assert env.client.get(launch).status_code == 302
    assert env.client.get(f'/assets/{asset}').status_code == 302


# ---- 外部图片代理 ------------------------------------------------------------------

@pytest.mark.parametrize('url,ok', [
    ('https://i.ytimg.com/vi/abc/mqdefault.jpg', True),
    ('https://i0.hdslb.com/bfs/archive/x.jpg', True),
    ('https://cdn.discordapp.com/avatars/42/abc.png?size=128', True),
    ('http://i.ytimg.com/vi/abc/mqdefault.jpg', False),          # 只认 https
    ('https://ytimg.com.evil.example/x.jpg', False),
    ('https://evilytimg.com/x.jpg', False),
    ('https://unknown.ytimg.com/x.jpg', False),                 # 只认列出来的主机名
    ('https://i.ytimg.com:8443/x.jpg', False),
    ('https://user:pw@i.ytimg.com/x.jpg', False),
    ('https://127.0.0.1/x.jpg', False),
    ('https://localhost/x.jpg', False),
    ('file:///etc/passwd', False),
    ('', False),
])
def test_image_url_allowlist(env, url, ok):
    assert env.mod.allowed_image_url(url) is ok


def test_image_url_is_rebuilt_from_the_allowlist(env):
    assert env.mod.safe_image_url('https://I.YTIMG.COM./vi/a/1.jpg?x=1#frag') == 'https://i.ytimg.com/vi/a/1.jpg?x=1'
    assert env.mod.safe_image_url('https://cdn.discordapp.com') == 'https://cdn.discordapp.com/'
    assert env.mod.safe_image_url('https://i.ytimg.com/a\\b') is None


def test_log_values_cannot_forge_lines(env):
    assert env.mod._for_log('1\r\nWARNING fake') == '1  WARNING fake'


class FakeImageResp:
    def __init__(self, status=200, ctype='image/jpeg', data=b'\xff\xd8jpeg'):
        self.status_code = status
        self.headers = {'Content-Type': ctype}
        self._data = data
        self.closed = False

    def iter_content(self, size):
        yield self._data

    def close(self):
        self.closed = True


def test_image_proxy(env, monkeypatch):
    calls = []
    responses = {'https://i.ytimg.com/vi/a/1.jpg': FakeImageResp(),
                 'https://i.ytimg.com/vi/a/page.jpg': FakeImageResp(ctype='text/html'),
                 'https://i.ytimg.com/vi/a/moved.jpg': FakeImageResp(status=302)}

    def fake_get(url, **kw):
        calls.append((url, kw))
        return responses[url]

    token = token_for(env.client)
    # requests 模块和 Discord 登录共用:先拿令牌再换掉 get
    monkeypatch.setattr(env.mod.requests, 'get', fake_get)
    path = '/api/thumbnail/external?url='
    # 没登记过的地址(不是服务端发出去的):白名单图床也不取
    assert env.client.get(path + 'https://i.ytimg.com/vi/a/1.jpg', headers=bearer(token)).status_code == 404
    assert calls == []
    env.mod.remember_images(list(responses) + ['https://example.com/x.jpg', '', None])
    assert env.mod.known_image('https://example.com/x.jpg') is None
    rv = env.client.get(path + 'https://i.ytimg.com/vi/a/1.jpg', headers=bearer(token))
    assert rv.status_code == 200
    assert rv.data == b'\xff\xd8jpeg'
    assert rv.mimetype == 'image/jpeg'
    assert calls[0][1]['allow_redirects'] is False
    # 缓存:第二次不再请求
    env.client.get(path + 'https://i.ytimg.com/vi/a/1.jpg', headers=bearer(token))
    assert len(calls) == 1
    assert env.client.get(path + 'https://i.ytimg.com/vi/a/page.jpg', headers=bearer(token)).status_code == 404
    assert env.client.get(path + 'https://i.ytimg.com/vi/a/moved.jpg', headers=bearer(token)).status_code == 404
    assert env.client.get(path + 'https://example.com/x.jpg', headers=bearer(token)).status_code == 400
    # 要登录
    assert env.client.get(path + 'https://i.ytimg.com/vi/a/1.jpg').status_code == 401


def test_image_proxy_size_limit(env, monkeypatch):
    big = FakeImageResp(data=b'x' * (env.mod.IMAGE_MAX_BYTES + 1))
    token = token_for(env.client)
    monkeypatch.setattr(env.mod.requests, 'get', lambda url, **kw: big)
    env.mod.remember_images(['https://i.ytimg.com/big.jpg'])
    rv = env.client.get('/api/thumbnail/external?url=https://i.ytimg.com/big.jpg', headers=bearer(token))
    assert rv.status_code == 404
    assert big.closed


def test_search_registers_result_thumbnails(env, monkeypatch):
    import web_search
    results = [{'source': 'youtube', 'id': 'abc', 'url': 'https://www.youtube.com/watch?v=abc', 'title': 't',
                'uploader': '', 'duration': 1, 'thumbnail': 'https://i.ytimg.com/vi/abc/mqdefault.jpg'}]
    monkeypatch.setattr(web_search, 'unified_search', lambda q, limit: ([dict(r) for r in results], []))
    token = token_for(env.client)
    assert env.client.get('/api/search?q=hello', headers=bearer(token)).status_code == 200
    assert env.mod.known_image('https://i.ytimg.com/vi/abc/mqdefault.jpg') == 'https://i.ytimg.com/vi/abc/mqdefault.jpg'
    # Activity 没开就不记
    env.mod._known_images.clear()
    env.config.set('webinterface', 'activity_enabled', 'False')
    env.config.set('webinterface', 'auth_method', 'none')
    env.client.get('/api/search?q=hello')
    assert env.mod.known_image('https://i.ytimg.com/vi/abc/mqdefault.jpg') is None

