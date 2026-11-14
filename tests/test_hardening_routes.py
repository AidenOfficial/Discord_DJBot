# coding=utf-8
"""公开部署前的路由加固:上传权限 / 配额、曲库网址条目、歌词偏移、频道权限、搜索并发与超时。
web_context 的权限函数直接替换掉,不走真的登录流程。"""
import asyncio
import configparser
import os
import sys
import threading
import time
import types
import unittest
from collections import namedtuple

import pytest
from flask import Flask

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import variables as var  # noqa: E402
import web_context  # noqa: E402
import web_upload  # noqa: E402
from web_users import Identity  # noqa: E402

GUILD = '111'
OWNER = '900'
HUB = types.SimpleNamespace(home_guild_id=GUILD, client=None)


def as_user(monkeypatch, discord_id=None, owner=False, manage=False, hub=HUB, key=None):
    """当前请求的身份:Discord id、是不是 bot 主人 / 能不能管理这个服务器;hub=None 是单服务器旧模式。"""
    monkeypatch.setattr(web_context, 'hub', lambda: hub)
    monkeypatch.setattr(web_context, 'is_owner', lambda: owner)
    monkeypatch.setattr(web_context, 'can_manage', lambda: manage or owner)
    monkeypatch.setattr(web_context, 'guild_id', lambda: GUILD)
    monkeypatch.setattr(web_context, 'linked_discord_id', lambda ident: discord_id)
    ident = Identity(key=key or (f'discord:{discord_id}' if discord_id else None), source='discord')
    import web_channels
    import web_users
    for module in (web_upload, web_channels, web_users):
        monkeypatch.setattr(module, 'current_identity', lambda: ident)


# =====================================================================
#  上传
# =====================================================================

@pytest.fixture
def upload_env(monkeypatch, tmp_path):
    from database import DatabaseMigration, MusicDatabase, SettingsDatabase
    monkeypatch.setattr(var, 'tmp_folder', str(tmp_path / 'cache') + os.sep)
    monkeypatch.setattr(var, 'music_folder', str(tmp_path / 'music') + os.sep)
    os.makedirs(var.tmp_folder)
    os.makedirs(var.music_folder)
    config = configparser.ConfigParser(interpolation=None)
    config.read_dict({'webinterface': {'upload_enabled': 'True', 'max_upload_file_size': '50M',
                                       'upload_extract_audio': 'True', 'uploaders': '77, 78'}})
    monkeypatch.setattr(var, 'config', config)
    db = SettingsDatabase(str(tmp_path / 's.db'))
    music_db = MusicDatabase(str(tmp_path / 'm.db'))
    DatabaseMigration(db, music_db).migrate()
    monkeypatch.setattr(var, 'db', db)
    monkeypatch.setattr(var, 'music_db', music_db)
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024  # 部署时全局只放 1 MiB
    app.register_blueprint(web_upload.create_blueprint(lambda f: f))
    return app.test_client()


def init(client, size=10, name='a.mp3'):
    return client.post('/api/upload/init', json={'filename': name, 'size': size})


def test_upload_forbidden_for_plain_members_in_hub_mode(monkeypatch, upload_env):
    as_user(monkeypatch, discord_id='42')
    rv = init(upload_env)
    assert rv.status_code == 403
    assert rv.get_json() == {'error': 'upload_forbidden'}
    # 别人的 upload_id 也不能续传 / 完成 / 取消
    as_user(monkeypatch, discord_id='77')
    uid = init(upload_env).get_json()['upload_id']
    as_user(monkeypatch, discord_id='42')
    assert upload_env.put(f'/api/upload/{uid}?offset=0', data=b'x').get_json() == {'error': 'upload_forbidden'}
    assert upload_env.post(f'/api/upload/{uid}/finish').status_code == 403
    assert upload_env.delete(f'/api/upload/{uid}').status_code == 403


def test_owner_and_listed_uploaders_may_upload(monkeypatch, upload_env):
    as_user(monkeypatch, discord_id=OWNER, owner=True)
    assert init(upload_env).status_code == 200
    as_user(monkeypatch, discord_id='78')
    assert init(upload_env).status_code == 200
    # 没关联 Discord 的身份不在名单里
    as_user(monkeypatch, discord_id=None, key='user:bob')
    assert init(upload_env).status_code == 403


def test_legacy_single_guild_mode_keeps_uploads_open(monkeypatch, upload_env):
    as_user(monkeypatch, discord_id=None, hub=None)
    assert init(upload_env).status_code == 200


def test_open_uploads_capped_per_identity(monkeypatch, upload_env):
    as_user(monkeypatch, discord_id='77')
    assert init(upload_env).status_code == 200
    assert init(upload_env).status_code == 200
    rv = init(upload_env)
    assert rv.status_code == 429
    assert rv.get_json()['error'] == 'too_many_uploads'
    as_user(monkeypatch, discord_id='78')
    assert init(upload_env).status_code == 200


def test_init_reserves_space_for_uploads_in_flight(monkeypatch, upload_env):
    Usage = namedtuple('Usage', 'total used free')
    monkeypatch.setattr(web_upload.shutil, 'disk_usage',
                        lambda path: Usage(0, 0, web_upload.DISK_RESERVE + 100))
    monkeypatch.setattr(web_upload, 'CHUNK_SIZE', 30)
    as_user(monkeypatch, discord_id='77')
    uid = init(upload_env, size=60).get_json()['upload_id']
    as_user(monkeypatch, discord_id='78')
    # 第一个还有 60 字节没传:60 + 60 > 100
    rv = init(upload_env, size=60)
    assert rv.status_code == 507
    assert rv.get_json()['error'] == 'no_space'
    as_user(monkeypatch, discord_id='77')
    assert upload_env.put(f'/api/upload/{uid}?offset=0', data=b'a' * 30).status_code == 200
    assert upload_env.put(f'/api/upload/{uid}?offset=30', data=b'b' * 25).status_code == 200
    as_user(monkeypatch, discord_id='78')
    assert init(upload_env, size=60).status_code == 200  # 剩 5 字节没传:60 + 5 <= 100
    assert init(upload_env, size=50).status_code == 507  # 50 + 5 + 60 > 100


def test_chunk_put_allows_chunk_size_despite_small_global_limit(monkeypatch, upload_env):
    monkeypatch.setattr(web_upload, 'CHUNK_SIZE', 2 * 1024 * 1024)
    as_user(monkeypatch, discord_id='77')
    size = 3 * 1024 * 1024
    uid = init(upload_env, size=size).get_json()['upload_id']
    chunk = b'x' * (2 * 1024 * 1024)
    rv = upload_env.put(f'/api/upload/{uid}?offset=0', data=chunk,
                        content_type='application/octet-stream')
    assert rv.status_code == 200, rv.get_data(as_text=True)
    assert rv.get_json()['received'] == len(chunk)
    # 超过 CHUNK_SIZE + 64 KiB 的请求体看 Content-Length 就拒掉
    too_big = b'y' * (web_upload.CHUNK_SIZE + web_upload.CHUNK_SLACK + 1)
    assert upload_env.put(f'/api/upload/{uid}?offset={len(chunk)}', data=too_big).status_code == 413


def test_library_info_upload_flag_follows_permission(monkeypatch, upload_env):
    import web_library

    class Lock:
        def locked(self):
            return False

    monkeypatch.setattr(var, 'cache', types.SimpleNamespace(dir_lock=Lock()))
    app = Flask(__name__)
    app.register_blueprint(web_library.create_blueprint(lambda f: f))
    client = app.test_client()
    as_user(monkeypatch, discord_id='42')
    assert client.get('/api/library/info').get_json()['upload_enabled'] is False
    as_user(monkeypatch, discord_id='77')
    assert client.get('/api/library/info').get_json()['upload_enabled'] is True


# =====================================================================
#  曲库:网址条目只有主人能看
# =====================================================================

class LibraryVisibilityTest(unittest.TestCase):
    def setUp(self):
        from tests import test_web_library as lib
        import media.radio  # noqa: F401  注册 radio 类型
        import media.url  # noqa: F401  注册 url 类型
        self.lib = lib
        lib.WebLibraryTestCase.setUp(self)
        var.music_db.insert_music({
            'id': 'u' * 32, 'type': 'url', 'title': 'other guild song', 'url': 'https://e.com/x',
            'path': '', 'duration': 60, 'thumbnail': '', 'ready': 'yes', 'tags': [], 'keywords': 'song'})
        var.music_db.insert_music({
            'id': 'r' * 32, 'type': 'radio', 'title': 'other guild station', 'url': 'https://e.com/radio',
            'path': '', 'duration': 0, 'thumbnail': '', 'ready': 'yes', 'tags': [], 'keywords': 'station'})
        self.mp = pytest.MonkeyPatch()

    def tearDown(self):
        self.mp.undo()
        self.lib.WebLibraryTestCase.tearDown(self)

    def titles(self, **body):
        rv = self.client.post('/api/library/query', json=body)
        self.assertEqual(200, rv.status_code, rv.data)
        return sorted(i['title'] for i in rv.get_json()['items'])

    def test_non_owner_sees_only_local_files(self):
        as_user(self.mp, discord_id='42')
        self.assertEqual(['a.mp3', 'b.mp3', 'c.mp3'], self.titles())
        self.assertEqual(['a.mp3', 'b.mp3', 'c.mp3'], self.titles(type='file,url,radio'))
        self.assertEqual([], self.titles(type='url'))
        self.assertEqual([], self.titles(type='radio'))  # 电台也是别的服务器播过才进库的
        self.assertEqual(['a.mp3', 'b.mp3', 'c.mp3'], self.titles(type='file,url'))
        self.assertEqual(400, self.client.post('/api/library/query', json={'type': 'evil'}).status_code)

    def test_owner_and_legacy_mode_see_everything(self):
        as_user(self.mp, discord_id=OWNER, owner=True)
        self.assertEqual(['other guild song'], self.titles(type='url'))
        self.assertEqual(['other guild station'], self.titles(type='radio'))
        self.assertEqual(5, len(self.titles()))
        as_user(self.mp, discord_id=None, hub=None)
        self.assertEqual(['other guild song'], self.titles(type='url'))


# =====================================================================
#  歌词偏移
# =====================================================================

@pytest.fixture
def lyrics_env(monkeypatch):
    import web_api
    from media import lyrics
    from tests.test_web_api import FakeCache, FakePlaylist, FakeWrapper
    item = types.SimpleNamespace(id='queued')
    other = types.SimpleNamespace(id='elsewhere')
    monkeypatch.setattr(var, 'cache', FakeCache({item.id: item, other.id: other}))
    queue = FakePlaylist([FakeWrapper(item)])
    monkeypatch.setattr(web_context, 'playlist', lambda: queue)
    calls = []
    monkeypatch.setattr(lyrics, 'set_offset', lambda it, off: calls.append((it.id, off)) or {'offset': off})
    monkeypatch.setattr(lyrics, 'to_json', lambda data: data)
    app = Flask(__name__)
    app.register_blueprint(web_api.create_blueprint(lambda f: f))
    return types.SimpleNamespace(client=app.test_client(), calls=calls)


def test_lyrics_offset_needs_manage_or_own_queue(monkeypatch, lyrics_env):
    as_user(monkeypatch, discord_id='42')
    rv = lyrics_env.client.post('/api/lyrics/elsewhere/offset', json={'offset': 3})
    assert rv.status_code == 403
    assert rv.get_json()['error'] == 'not_in_queue'
    assert lyrics_env.client.post('/api/lyrics/queued/offset', json={'offset': 2}).status_code == 200
    as_user(monkeypatch, discord_id='42', manage=True)
    assert lyrics_env.client.post('/api/lyrics/elsewhere/offset', json={'offset': 1}).status_code == 200
    assert lyrics_env.calls == [('queued', 2.0), ('elsewhere', 1.0)]


# =====================================================================
#  频道
# =====================================================================

Perms = namedtuple('Perms', 'view_channel connect')


class FakeGuild:
    """discord.Guild 里 web_channels 用到的部分。成员 42 看不见 Squad(5),能看见但连不上 Lobby(1)。"""

    def __init__(self, cached=True):
        self.cached = cached
        self.fetched = 0
        hidden, no_connect = {5}, {1}
        self.voice_channels = [types.SimpleNamespace(
            id=cid, permissions_for=lambda m, cid=cid: Perms(cid not in hidden, cid not in hidden | no_connect))
            for cid in (1, 3, 4, 5, 6)]
        self.stage_channels = []

    def get_member(self, uid):
        return object() if self.cached else None

    async def fetch_member(self, uid):
        self.fetched += 1
        return object()


class FakeDC:
    def __init__(self, guild):
        self.client = types.SimpleNamespace(get_guild=lambda gid: guild)

    def call(self, coro, timeout=30.0):
        return asyncio.run(coro)


class ChannelPermissionTest(unittest.TestCase):
    def setUp(self):
        from tests import test_channels as chan
        import web_channels
        self.chan = chan
        chan.Base.setUp(self)
        self.web_channels = web_channels
        web_channels._perms_cache.clear()
        var.bot = self.bot
        var.config = configparser.ConfigParser()
        self.bot._guild_id = GUILD
        # bot 在 Music(3);alice(42)也在 Music,bob(43)在看不见的 Squad(5)
        self.bot.link.users.add(42, 'alice', 3)
        self.bot.link.users.add(43, 'bob', 5)
        self.guild = FakeGuild()
        self.hub = types.SimpleNamespace(home_guild_id=GUILD, client=FakeDC(self.guild))
        self.mp = pytest.MonkeyPatch()
        self.mp.setattr(web_context, 'session', lambda: self.bot)
        app = Flask(__name__)
        app.register_blueprint(web_channels.create_blueprint(lambda f: f))
        self.client = app.test_client()

    def tearDown(self):
        self.mp.undo()
        self.web_channels._perms_cache.clear()
        self.chan.Base.tearDown(self)

    def user(self, discord_id='42', manage=False):
        as_user(self.mp, discord_id=discord_id, manage=manage, hub=self.hub)

    def ids(self, node):
        out = [node['id']]
        for child in node['children']:
            out += self.ids(child)
        return out

    def test_overview_hides_channels_the_member_cannot_view(self):
        self.user()
        data = self.client.get('/api/channels').get_json()
        ids = self.ids(data['tree'])
        self.assertNotIn('5', ids)
        self.assertIn('6', ids)  # 同一个分类里看得见的还在
        self.assertEqual(['alice'], data['online_users'])
        self.assertNotIn('bob', str(data['tree']))

    def test_category_left_empty_is_dropped_and_member_fetched_once(self):
        self.guild.cached = False
        self.guild.voice_channels = [c for c in self.guild.voice_channels if c.id != 6]
        self.user()
        ids = self.ids(self.client.get('/api/channels').get_json()['tree'])
        self.assertNotIn('2', ids)  # Games 分类里只剩看不见的 Squad
        self.client.get('/api/channels')
        self.assertEqual(1, self.guild.fetched)

    def test_non_member_is_cached_and_sees_no_voice_channels(self):
        import discord

        class NotFound(discord.NotFound):
            def __init__(self):
                pass

        async def not_a_member(uid):
            self.guild.fetched += 1
            raise NotFound()

        self.guild.cached = False
        self.guild.fetch_member = not_a_member
        self.user()
        for _ in range(3):
            data = self.client.get('/api/channels').get_json()
            self.assertEqual(['0'], self.ids(data['tree']))
        self.assertEqual(1, self.guild.fetched)  # 轮询不会每次都打 REST
        self.assertEqual(403, self.client.post('/api/channels/join', json={'channel_id': '6'}).status_code)

    def test_unknown_member_sees_no_voice_channels(self):
        self.user(discord_id=None)
        data = self.client.get('/api/channels').get_json()
        self.assertEqual(['0'], self.ids(data['tree']))
        self.assertEqual([], data['online_users'])

    def test_managers_see_everything(self):
        self.user(manage=True)
        data = self.client.get('/api/channels').get_json()
        self.assertIn('5', self.ids(data['tree']))
        self.assertEqual(['alice', 'bob'], data['online_users'])

    def test_join_requires_connect(self):
        self.user()
        rv = self.client.post('/api/channels/join', json={'channel_id': '1'})
        self.assertEqual(403, rv.status_code)
        self.assertEqual('channel_forbidden', rv.get_json()['error'])
        self.assertEqual(403, self.client.post('/api/channels/join', json={'channel_id': '5'}).status_code)
        self.assertEqual([], self.bot.link.moves)
        rv = self.client.post('/api/channels/join', json={'channel_id': '6'})
        self.assertEqual(200, rv.status_code)
        self.assertEqual([6], self.bot.link.moves)
        self.user(manage=True)
        self.assertEqual(200, self.client.post('/api/channels/join', json={'channel_id': '5'}).status_code)

    def test_leave_requires_being_in_the_bots_channel(self):
        left = []
        self.bot.pause = lambda: None
        self.bot.leave_voice = lambda: left.append(True)
        self.user(discord_id='43')  # bob 在 Squad,bot 在 Music
        rv = self.client.post('/api/channels/leave')
        self.assertEqual(403, rv.status_code)
        self.assertEqual('not_in_channel', rv.get_json()['error'])
        self.assertEqual([], left)
        self.user(discord_id='42')
        self.assertEqual(200, self.client.post('/api/channels/leave').status_code)
        self.assertEqual([True], left)

    def test_legacy_mode_is_unrestricted(self):
        as_user(self.mp, discord_id=None, hub=None)
        data = self.client.get('/api/channels').get_json()
        self.assertIn('5', self.ids(data['tree']))
        self.assertEqual(200, self.client.post('/api/channels/join', json={'channel_id': '5'}).status_code)


# =====================================================================
#  搜索
# =====================================================================

def test_search_hard_timeout_does_not_wait_for_slow_source(monkeypatch):
    import web_search
    release = threading.Event()
    monkeypatch.setattr(web_search, 'HARD_TIMEOUT', 0.3)
    monkeypatch.setattr(web_search, '_slots', threading.BoundedSemaphore(3))
    monkeypatch.setattr(web_search, 'search_youtube', lambda q, limit: release.wait(10) and [])
    monkeypatch.setattr(web_search, 'search_bilibili', lambda q, limit: [{'source': 'bilibili', 'id': '1'}])
    started = time.monotonic()
    results, failed = web_search.unified_search('query')
    assert time.monotonic() - started < 2
    assert failed == ['youtube']
    assert [r['source'] for r in results] == ['bilibili']
    # 还在跑的那个来源继续占着名额,跑完才还
    assert web_search._slots._value == 2
    release.set()
    deadline = time.monotonic() + 5
    while web_search._slots._value != 3 and time.monotonic() < deadline:
        time.sleep(0.01)
    assert web_search._slots._value == 3


def test_search_busy_returns_503(monkeypatch):
    import web_api
    import web_search
    slots = threading.BoundedSemaphore(1)
    slots.acquire()
    monkeypatch.setattr(web_search, '_slots', slots)
    monkeypatch.setattr(var, 'config', configparser.ConfigParser())
    with pytest.raises(web_search.SearchBusy):
        web_search.unified_search('query')
    app = Flask(__name__)
    app.register_blueprint(web_api.create_blueprint(lambda f: f))
    rv = app.test_client().get('/api/search?q=hello')
    assert rv.status_code == 503
    assert rv.get_json() == {'error': 'busy'}
