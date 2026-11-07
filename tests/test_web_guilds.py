# coding=utf-8
"""多服务器 Web:按请求选服务器(X-DJ-Guild)、谁能操作 / 管理哪个服务器、/api/guilds、
按服务器的管理设置和封禁、统计筛选。用假的 Hub,不连 Discord。"""
import configparser
import json
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import util  # noqa: E402
import variables as var  # noqa: E402
import web_users  # noqa: E402
from bot.store import GuildStore  # noqa: E402
from database import DatabaseMigration, MusicDatabase, SettingsDatabase  # noqa: E402
from tests.test_web_api import FakePlaylist, FakeVolume  # noqa: E402
from tests.test_web_auth_discord import FakeDiscord, login  # noqa: E402

OWNER = '900'
EMAIL_HEADER = 'Cf-Access-Authenticated-User-Email'
HOME, SECOND, THIRD = '111', '333', '444'
NAMES = {HOME: 'Home', SECOND: 'Other', THIRD: 'Elsewhere'}


class FakeSession:
    """一个服务器的会话(DJBot 替身):自己的队列(version 不同,方便认出是哪个)。"""

    def __init__(self, guild_id, version):
        self.guild_id = guild_id
        self.playlist = FakePlaylist([])
        self.playlist.version = version
        self.is_pause = False
        self.playhead = 0
        self.volume_helper = FakeVolume()
        self.volume_helper.plain_volume_set = 0.9
        self.saved_channels = []
        self.link = types.SimpleNamespace(guild_name=NAMES[guild_id], bot_name='dj')

    @property
    def store(self):
        return var.store

    def setting(self, key, default=None):
        return var.store.get(self.guild_id, key, default)

    def save_setting(self, key, value):
        var.store.set(self.guild_id, key, value)

    def command_name(self, key):
        return key

    # web_channels 用到的
    def my_channel_id(self):
        return None

    def channel_settings(self):
        return {'default': [], 'follow': 'off', 'follow_user': '', 'return_home': False,
                'idle_pause_minutes': 0, 'idle_resume': False}

    def channel_tree(self):
        return None

    def humans_by_channel(self):
        return {}

    def find_channel_by_path(self, path):
        return None

    def save_channel_settings(self, **changes):
        self.saved_channels.append(changes)


class FakeHub:
    def __init__(self, home=HOME, members=None):
        self.home_guild_id = home
        self._sessions = {gid: FakeSession(gid, version) for gid, version in
                          ((HOME, 101), (SECOND, 303), (THIRD, 404))}
        self.members = members or {}
        self.requested = []

    def sessions(self):
        return list(self._sessions.values())

    def session_for(self, guild_id, create=True):
        self.requested.append(str(guild_id))
        return self._sessions.get(str(guild_id))

    def guild_ids(self):
        return list(self._sessions)

    def guild_info(self, guild_id):
        return {'id': guild_id, 'name': NAMES.get(guild_id, ''), 'icon': 'hash' if guild_id == HOME else None}

    def is_member(self, guild_id, user_id):
        return str(user_id) in self.members.get(str(guild_id), ())


class FakeHistory:
    def __init__(self):
        self.calls = []

    def stats(self, **kwargs):
        self.calls.append(kwargs)
        return {'total_plays': 0, 'top_users': []}


@pytest.fixture
def env(monkeypatch, tmp_path):
    config = configparser.ConfigParser(interpolation=None, allow_no_value=True)
    config.read(util.solve_filepath('configuration.default.ini'), encoding='utf-8')
    config.set('bot', 'admin', f'{OWNER}, 12345678')
    config.set('webinterface', 'auth_method', 'none')
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
    hub = FakeHub()
    monkeypatch.setattr(var, 'hub', hub, raising=False)
    monkeypatch.setattr(var, 'bot', hub._sessions[HOME])
    history = FakeHistory()
    monkeypatch.setattr(var, 'play_history', history)
    monkeypatch.delenv('DISCORD_CLIENT_SECRET', raising=False)
    import constants
    constants.load_lang('en_US')
    import interface
    import web_auth_discord
    web_auth_discord._cache.clear()
    interface.web.secret_key = 'test'
    interface.bad_access_count.clear()
    interface.banned_ip.clear()
    fake = FakeDiscord()
    # Discord 那边:这个用户在 111(管理服务器权限)、222(主人)、333(普通成员)
    monkeypatch.setattr(web_auth_discord.requests, 'post', fake.post)
    monkeypatch.setattr(web_auth_discord.requests, 'get', fake.get)
    yield types.SimpleNamespace(client=interface.web.test_client(), discord=fake, hub=hub,
                                config=config, history=history)
    web_auth_discord._cache.clear()


def guild_ids(client, **kw):
    rv = client.get('/api/guilds', **kw)
    assert rv.status_code == 200, rv.get_data(as_text=True)
    return {g['id']: g['can_manage'] for g in rv.get_json()['guilds']}


def queue_version(client, guild=None, **kw):
    headers = dict(kw.pop('headers', {}))
    if guild:
        headers['X-DJ-Guild'] = guild
    return client.get('/api/queue', headers=headers, **kw)


def bind(email, discord_id):
    code, _ = var.user_db.create_bind_code(email)
    assert var.user_db.consume_bind_code(code, f'discord:{discord_id}', 'bob') == email


def as_email(email):
    return {EMAIL_HEADER: email}


# ---- 授权矩阵 ----------------------------------------------------------------------

def test_owner_sees_every_guild_and_manages(env):
    env.config.set('webinterface', 'auth_method', 'discord')
    env.discord.user = dict(env.discord.user, id=OWNER)
    env.discord.guilds = []  # 主人和 bot 不在同一服务器也能进
    login(env.client)
    assert guild_ids(env.client) == {HOME: True, SECOND: True, THIRD: True}
    data = env.client.get('/api/guilds').get_json()
    assert data['owner'] is True
    assert data['multi'] is True


def test_oauth_member_gets_intersection_and_manage_from_permissions(env):
    env.config.set('webinterface', 'auth_method', 'discord')
    login(env.client)
    # 111:管理服务器权限 → 能管理;333:普通成员;222 bot 不在;444 用户不在
    assert guild_ids(env.client) == {HOME: True, SECOND: False}
    assert queue_version(env.client, THIRD).status_code == 403
    assert queue_version(env.client, THIRD).get_json()['error'] == 'guild_forbidden'
    assert queue_version(env.client, SECOND).get_json()['version'] == 303


def test_oauth_user_sharing_no_guild_is_forbidden(env):
    env.config.set('webinterface', 'auth_method', 'discord')
    env.discord.guilds = [{'id': '999', 'name': 'X', 'icon': None, 'owner': True, 'permissions': '8'}]
    login(env.client)
    assert env.client.get('/api/guilds').status_code == 403


def test_bound_legacy_user_gets_member_guilds_without_manage(env):
    env.hub.members = {SECOND: {'77'}, THIRD: {'78'}}
    bind('bob@example.com', '77')
    h = as_email('bob@example.com')
    assert guild_ids(env.client, headers=h) == {SECOND: False}
    assert queue_version(env.client, headers=h).get_json()['version'] == 303  # 默认:唯一允许的
    assert queue_version(env.client, HOME, headers=h).status_code == 403


def test_bound_owner_via_legacy_login_manages_everything(env):
    bind('boss@example.com', OWNER)
    assert guild_ids(env.client, headers=as_email('boss@example.com')) == {HOME: True, SECOND: True, THIRD: True}


def test_unbound_user_has_no_guild(env):
    h = as_email('nobody@example.com')
    assert guild_ids(env.client, headers=h) == {}
    rv = queue_version(env.client, headers=h)
    assert rv.status_code == 403
    assert rv.get_json()['error'] == 'no_guild_access'
    # 个人的东西(/api/me、生成绑定码)不需要服务器
    assert env.client.get('/api/me', headers=h).status_code == 200
    assert env.client.post('/api/me/bind', headers=h).status_code == 200


def setup_token(token='tok', user='alice', guild=None):
    var.db.set('web_token', token, user)
    var.db.set('user', user, json.dumps({'token': token}))
    if guild:
        var.db.set('web_token_guild', token, guild)


def test_token_user_controls_the_guild_of_the_command(env):
    env.config.set('webinterface', 'auth_method', 'token')
    setup_token(guild=SECOND)
    assert guild_ids(env.client, query_string={'token': 'tok'}) == {SECOND: False}
    # 之后靠会话
    assert queue_version(env.client).get_json()['version'] == 303
    assert queue_version(env.client, HOME).status_code == 403


def test_token_from_before_the_change_maps_to_home(env):
    env.config.set('webinterface', 'auth_method', 'token')
    setup_token()
    assert guild_ids(env.client, query_string={'token': 'tok'}) == {HOME: False}


def test_revoked_token_session_follows_the_users_current_token(env):
    env.config.set('webinterface', 'auth_method', 'token')
    setup_token('old', guild=HOME)
    guild_ids(env.client, query_string={'token': 'old'})
    # 用户在另一个服务器重新发了 /web:旧令牌没了
    var.db.remove_option('web_token', 'old')
    var.db.remove_option('web_token_guild', 'old')
    setup_token('new', guild=SECOND)
    assert guild_ids(env.client) == {SECOND: False}


def test_web_command_records_the_guild(env):
    from commands import web
    env.config.set('webinterface', 'auth_method', 'token')
    sent = []
    bot = types.SimpleNamespace(guild_id=HOME, send_msg=lambda msg, text: sent.append(msg))
    text = types.SimpleNamespace(username='alice', guild_id=int(SECOND))
    web.cmd_web_access(bot, 'Alice', text, 'web', '')
    token = json.loads(var.db.get('user', 'alice'))['token']
    assert var.db.get('web_token_guild', token) == SECOND
    # 再发一次:旧令牌和它的服务器一起作废
    web.cmd_web_access(bot, 'Alice', text, 'web', '')
    assert var.db.get('web_token_guild', token, fallback=None) is None
    assert sent


# ---- 选服务器 ------------------------------------------------------------------------

def test_header_routes_to_the_right_session(env):
    bind('boss@example.com', OWNER)
    h = as_email('boss@example.com')
    assert queue_version(env.client, headers=h).get_json()['version'] == 101  # 默认主服务器
    assert queue_version(env.client, THIRD, headers=h).get_json()['version'] == 404
    assert env.client.get('/api/queue?guild=333', headers=h).get_json()['version'] == 303
    # 请求头优先于 ?guild=
    assert queue_version(env.client, THIRD, headers=h, query_string={'guild': SECOND}).get_json()['version'] == 404
    assert env.hub.requested[-1] == THIRD
    data = env.client.get('/api/guilds', headers=dict(h, **{'X-DJ-Guild': SECOND})).get_json()['guilds']
    assert [g['id'] for g in data if g['selected']] == [SECOND]
    home = next(g for g in data if g['id'] == HOME)
    assert home['name'] == 'Home'
    assert home['icon'] == 'https://cdn.discordapp.com/icons/111/hash.png?size=64'


def test_default_prefers_home_then_first_allowed(env):
    env.hub.members = {SECOND: {'77'}, HOME: {'77'}}
    bind('bob@example.com', '77')
    assert queue_version(env.client, headers=as_email('bob@example.com')).get_json()['version'] == 101


def test_session_unavailable_is_503(env):
    bind('boss@example.com', OWNER)
    env.hub.session_for = lambda gid, create=True: None
    assert queue_version(env.client, headers=as_email('boss@example.com')).status_code == 503


def test_without_hub_everyone_keeps_the_single_session(env, monkeypatch):
    monkeypatch.setattr(var, 'hub', None)
    h = as_email('nobody@example.com')
    # 旧的单服务器部署:请求头不看,谁都能操作
    assert queue_version(env.client, '999', headers=h).get_json()['version'] == 101
    guilds = env.client.get('/api/guilds', headers=h).get_json()
    assert guilds['multi'] is False
    assert [(g['id'], g['can_manage'], g['name']) for g in guilds['guilds']] == [(HOME, False, 'Home')]
    # 频道设置照旧谁都能改,新的管理设置不行
    assert env.client.post('/api/channels/settings', json={'follow': 'auto'}, headers=h).status_code == 200
    assert env.client.get('/api/guild/settings', headers=h).status_code == 403


# ---- 管理设置 ------------------------------------------------------------------------

def oauth_login(env):
    env.config.set('webinterface', 'auth_method', 'discord')
    login(env.client)


def test_guild_settings_require_manage(env):
    oauth_login(env)
    assert env.client.get('/api/guild/settings', headers={'X-DJ-Guild': SECOND}).status_code == 403
    assert env.client.post('/api/guild/settings', json={'max_volume': 10},
                           headers={'X-DJ-Guild': SECOND}).status_code == 403
    assert env.client.get('/api/guild/bans', headers={'X-DJ-Guild': SECOND}).get_json()['error'] == 'manage_required'
    assert var.store.get(SECOND, 'max_volume') is None


def test_guild_settings_roundtrip(env):
    oauth_login(env)
    h = {'X-DJ-Guild': HOME}
    data = env.client.get('/api/guild/settings', headers=h).get_json()
    assert data['announce_channel'] is None
    assert data['max_volume'] == data['default_max_volume']
    data = env.client.post('/api/guild/settings', json={'announce_channel': '5550001', 'max_volume': 40},
                           headers=h).get_json()
    assert data['announce_channel'] == '5550001'
    assert data['max_volume'] == 40
    assert var.store.get(HOME, 'announce_channel') == '5550001'
    assert float(var.store.get(HOME, 'max_volume')) == 0.4
    assert var.store.get(SECOND, 'announce_channel') is None
    # 现在的音量超过了新上限:压下来
    assert env.hub._sessions[HOME].volume_helper.plain_volume_set == 0.4
    # Web 上调音量也不能超过
    env.client.post('/api/controls', json={'action': 'volume', 'volume': 0.9}, headers=h)
    assert env.hub._sessions[HOME].volume_helper.plain_volume_set == 0.4
    data = env.client.post('/api/guild/settings', json={'announce_channel': None}, headers=h).get_json()
    assert data['announce_channel'] is None
    for bad in ({'max_volume': 101}, {'max_volume': 'x'}, {'announce_channel': 'general'}, {}):
        assert env.client.post('/api/guild/settings', json=bad, headers=h).status_code == 400


def test_guild_bans(env):
    oauth_login(env)
    h = {'X-DJ-Guild': HOME}
    data = env.client.post('/api/guild/bans', json={'kind': 'user_ban', 'value': '<@42>', 'note': '<b>x</b>'},
                           headers=h).get_json()
    assert [r['value'] for r in data['user_ban']] == ['42']
    assert data['user_ban'][0]['note'] == '&lt;b&gt;x&lt;/b&gt;'
    env.client.post('/api/guild/bans', json={'kind': 'url_ban', 'value': 'https://bad.example/x'}, headers=h)
    assert var.store.has_rule('user_ban', '42', HOME)
    assert not var.store.has_rule('user_ban', '42', SECOND)
    assert var.store.has_rule('url_ban', 'https://bad.example/x', HOME)
    # 全局规则不出现在服务器列表里
    var.store.add_rule('', 'user_ban', '7')
    assert [r['value'] for r in env.client.get('/api/guild/bans', headers=h).get_json()['user_ban']] == ['42']
    rv = env.client.delete('/api/guild/bans', json={'kind': 'user_ban', 'value': '42'}, headers=h)
    assert rv.get_json()['user_ban'] == []
    assert env.client.delete('/api/guild/bans', json={'kind': 'user_ban', 'value': '42'}, headers=h).status_code == 404
    for bad in ({'kind': 'user_ban', 'value': 'bob'}, {'kind': 'url_whitelist', 'value': '1'},
                {'kind': 'url_ban', 'value': ''}):
        assert env.client.post('/api/guild/bans', json=bad, headers=h).status_code == 400


def test_channel_settings_need_manage(env):
    oauth_login(env)
    rv = env.client.post('/api/channels/settings', json={'follow': 'auto'}, headers={'X-DJ-Guild': SECOND})
    assert rv.status_code == 403
    assert env.client.get('/api/channels', headers={'X-DJ-Guild': SECOND}).get_json()['can_edit_settings'] is False
    rv = env.client.post('/api/channels/settings', json={'follow': 'auto'}, headers={'X-DJ-Guild': HOME})
    assert rv.status_code == 200
    assert rv.get_json()['can_edit_settings'] is True
    assert env.hub._sessions[HOME].saved_channels == [{'follow': 'auto'}]


def test_logs_owner_only_with_hub(env):
    import web_logs
    oauth_login(env)
    assert env.client.get('/api/me').get_json()['can_view_logs'] is False
    assert env.client.get('/api/logs').status_code == 403
    assert web_logs  # 模块已导入


# ---- 统计 ----------------------------------------------------------------------------

def test_stats_scope(env):
    oauth_login(env)
    env.client.get('/api/stats', headers={'X-DJ-Guild': HOME})
    assert env.history.calls[-1] == {'guild_id': HOME, 'include_unscoped': True}
    env.client.get('/api/stats', headers={'X-DJ-Guild': HOME}, query_string={'guild': SECOND})
    assert env.history.calls[-1] == {'guild_id': SECOND, 'include_unscoped': False}
    assert env.client.get('/api/stats', query_string={'guild': THIRD}).status_code == 403
    assert env.client.get('/api/stats', query_string={'guild': 'all'}).status_code == 403


def test_stats_all_for_owner(env):
    bind('boss@example.com', OWNER)
    rv = env.client.get('/api/stats', query_string={'guild': 'all'}, headers=as_email('boss@example.com'))
    assert rv.status_code == 200
    assert env.history.calls[-1] == {}
