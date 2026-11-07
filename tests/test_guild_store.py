# coding=utf-8
"""按服务器分开的数据:settings 库 v2 -> v3 迁移、GuildStore、旧设置的接收、会话连上后读自己的状态。"""
import configparser
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import util  # noqa: E402
import variables as var  # noqa: E402
from bot.store import GuildStore  # noqa: E402
from database import DatabaseMigration, MusicDatabase, SettingsDatabase, SETTING_DB_VERSION  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LEGACY = {
    ('bot', 'volume'): '0.3',
    ('bot', 'max_volume'): '0.8',
    ('playlist', 'playback_mode'): 'repeat',
    ('playlist', 'current_index'): '1',
    ('playlist_item', '0'): json.dumps({'id': 'a', 'user': 'alice'}),
    ('playlist_item', '1'): json.dumps({'id': 'b', 'user': 'bob',
                                        'group': {'key': 'g1', 'name': 'Night', 'kind': 'playlist', 'total': 2}}),
    ('playlist_item', '10'): json.dumps({'id': 'c', 'user': 'bob',
                                         'group': {'key': 'g1', 'name': 'Night', 'kind': 'playlist', 'total': 2}}),
    ('channel', 'default'): json.dumps(['Games', 'Squad']),
    ('channel', 'follow'): 'auto',
    ('channel', 'idle_pause_minutes'): '9',
    ('discord', 'panel_message'): '500:900',
    ('user_ban', '42'): 'Troll',
    ('url_ban', 'https://bad.example/x'): None,
    ('url_whitelist', 'https://long.example/y'): None,
    ('web_token', 'tok'): 'alice',
}


def make_v2_db(path, rows=LEGACY):
    """旧版(v2)的 settings 库:只有 botamusique 表。"""
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE botamusique (section TEXT, option TEXT, value TEXT, UNIQUE(section, option))")
    conn.execute("INSERT INTO botamusique VALUES ('bot', 'db_version', '2')")
    conn.executemany("INSERT INTO botamusique VALUES (?, ?, ?)", [(s, o, v) for (s, o), v in rows.items()])
    conn.commit()
    conn.close()


def tables(path):
    conn = sqlite3.connect(path)
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.close()
    return names


class Tmp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, 'settings.db')
        self.music = MusicDatabase(os.path.join(self.tmp.name, 'music.db'))

    def tearDown(self):
        self.tmp.cleanup()

    def migrate(self):
        db = SettingsDatabase(self.path)
        DatabaseMigration(db, self.music).migrate()
        return db


class MigrationTest(Tmp):
    def test_v2_to_v3_creates_tables_and_backs_up(self):
        make_v2_db(self.path)
        db = self.migrate()
        self.assertEqual(SETTING_DB_VERSION, 3)
        self.assertEqual(db.getint('bot', 'db_version'), 3)
        self.assertTrue({'guild_settings', 'guild_queue', 'guild_queue_state', 'access_rule'} <= tables(self.path))
        # 旧数据原样保留
        self.assertEqual(db.get('bot', 'volume'), '0.3')

        backup = self.path + '.bak-v2'
        self.assertTrue(os.path.exists(backup))
        self.assertNotIn('guild_settings', tables(backup))
        self.assertEqual(SettingsDatabase(backup).get('bot', 'db_version'), '2')
        self.assertEqual(SettingsDatabase(backup).get('bot', 'volume'), '0.3')

    def test_migration_is_idempotent(self):
        make_v2_db(self.path)
        self.migrate()
        GuildStore(self.path).set('1', 'volume', '0.5')
        os.remove(self.path + '.bak-v2')
        db = self.migrate()                                  # 已经是 v3:什么都不做
        self.assertEqual(db.getint('bot', 'db_version'), 3)
        self.assertFalse(os.path.exists(self.path + '.bak-v2'))
        self.assertEqual(GuildStore(self.path).get('1', 'volume'), '0.5')

    def test_rerun_after_old_image_reset_the_version(self):
        # 换回旧镜像时它会把 db_version 写回 2;再升级时 v3 这一步要能重跑
        make_v2_db(self.path)
        self.migrate()
        GuildStore(self.path).set('1', 'volume', '0.5')
        SettingsDatabase(self.path).set('bot', 'db_version', 2)
        db = self.migrate()
        self.assertEqual(db.getint('bot', 'db_version'), 3)
        self.assertEqual(GuildStore(self.path).get('1', 'volume'), '0.5')

    def test_fresh_database_starts_at_v3_without_backup(self):
        db = self.migrate()
        self.assertEqual(db.getint('bot', 'db_version'), 3)
        self.assertIn('access_rule', tables(self.path))
        self.assertFalse(os.path.exists(self.path + '.bak-v2'))


class StoreTest(Tmp):
    def setUp(self):
        super().setUp()
        self.migrate()
        self.store = GuildStore(self.path)

    def test_settings_crud(self):
        s = self.store
        self.assertIsNone(s.get('1', 'volume'))
        self.assertEqual(s.get('1', 'volume', '0.1'), '0.1')
        s.set('1', 'volume', 0.5)
        self.assertEqual(s.get('1', 'volume'), '0.5')
        s.set(1, 'volume', '0.6')                            # int / str 的服务器 ID 是同一个
        self.assertEqual(s.get('1', 'volume'), '0.6')
        s.delete('1', 'volume')
        self.assertIsNone(s.get('1', 'volume'))

    def test_queue_roundtrip(self):
        group = {'key': 'g', 'name': 'Night'}
        entries = [{'id': 'a', 'user': 'u'}, {'id': 'b', 'user': 'v', 'group': group}]
        self.assertEqual(self.store.load_queue('1'), (-1, []))
        self.store.save_queue('1', 1, entries)
        self.assertEqual(self.store.load_queue('1'), (1, entries))
        self.store.save_queue('1', 0, entries[:1])           # 整个替换
        self.assertEqual(self.store.load_queue('1'), (0, entries[:1]))
        self.store.save_queue('1', -1, [])
        self.assertEqual(self.store.load_queue('1'), (-1, []))

    def test_guilds_do_not_mix(self):
        s = self.store
        s.set('1', 'playback_mode', 'repeat')
        s.set('2', 'playback_mode', 'random')
        s.save_queue('1', 0, [{'id': 'a', 'user': 'u'}])
        s.save_queue('2', 1, [{'id': 'x', 'user': 'w'}, {'id': 'y', 'user': 'w'}])
        self.assertEqual(s.get('1', 'playback_mode'), 'repeat')
        self.assertEqual(s.get('2', 'playback_mode'), 'random')
        self.assertEqual(s.load_queue('1'), (0, [{'id': 'a', 'user': 'u'}]))
        self.assertEqual([e['id'] for e in s.load_queue('2')[1]], ['x', 'y'])
        s.save_queue('1', -1, [])
        self.assertEqual(len(s.load_queue('2')[1]), 2)

    def test_two_tier_rules(self):
        s = self.store
        s.add_rule('', 'user_ban', '42', created_by='7', note='Troll')
        s.add_rule('100', 'url_ban', 'https://bad.example/x')
        self.assertTrue(s.has_rule('user_ban', '42'))                 # 全局:哪里都算
        self.assertTrue(s.has_rule('user_ban', '42', '100'))
        self.assertTrue(s.has_rule('user_ban', '42', '200'))
        self.assertTrue(s.has_rule('url_ban', 'https://bad.example/x', '100'))
        self.assertFalse(s.has_rule('url_ban', 'https://bad.example/x', '200'))
        self.assertFalse(s.has_rule('url_ban', 'https://bad.example/x'))
        self.assertFalse(s.has_rule('url_whitelist', 'https://bad.example/x', '100'))
        # 只看本服务器
        self.assertFalse(s.has_rule('user_ban', '42', '100', include_global=False))
        self.assertTrue(s.has_rule('url_ban', 'https://bad.example/x', '100', include_global=False))
        self.assertFalse(s.has_rule('url_ban', 'https://bad.example/x', '', include_global=False))

        rules = s.list_rules('user_ban')
        self.assertEqual([(r['value'], r['note'], r['created_by']) for r in rules], [('42', 'Troll', '7')])
        self.assertEqual(s.list_rules('url_ban'), [])
        self.assertEqual([r['value'] for r in s.list_rules('url_ban', '100')], ['https://bad.example/x'])

        self.assertTrue(s.remove_rule('', 'user_ban', '42'))
        self.assertFalse(s.remove_rule('', 'user_ban', '42'))
        self.assertFalse(s.has_rule('user_ban', '42', '100'))
        with self.assertRaises(ValueError):
            s.add_rule('', 'nonsense', 'x')


class AdoptLegacyTest(Tmp):
    def setUp(self):
        super().setUp()
        make_v2_db(self.path)
        self.migrate()
        self.store = GuildStore(self.path)

    def test_copies_everything_once_and_keeps_legacy_rows(self):
        s = self.store
        self.assertIsNone(s.legacy_guild())
        self.assertTrue(s.adopt_legacy('777'))
        self.assertEqual(s.legacy_guild(), '777')

        self.assertEqual(s.get('777', 'volume'), '0.3')
        self.assertEqual(s.get('777', 'max_volume'), '0.8')
        self.assertEqual(s.get('777', 'playback_mode'), 'repeat')
        self.assertEqual(s.get('777', 'panel_message'), '500:900')
        self.assertEqual(json.loads(s.get('777', 'channel.default')), ['Games', 'Squad'])
        self.assertEqual(s.get('777', 'channel.follow'), 'auto')
        self.assertEqual(s.get('777', 'channel.idle_pause_minutes'), '9')
        self.assertIsNone(s.get('777', 'channel.follow_user'))  # 旧库里没有的不凭空造

        index, entries = s.load_queue('777')
        self.assertEqual(index, 1)
        self.assertEqual([e['id'] for e in entries], ['a', 'b', 'c'])  # 按数字排序,不是字符串("10" 在最后)
        self.assertEqual(entries[2]['group']['name'], 'Night')

        # 封禁 / 白名单 -> 全局规则
        self.assertTrue(s.has_rule('user_ban', '42', '999'))
        self.assertEqual(s.list_rules('user_ban')[0]['note'], 'Troll')
        self.assertTrue(s.has_rule('url_ban', 'https://bad.example/x'))
        self.assertTrue(s.has_rule('url_whitelist', 'https://long.example/y'))

        # 旧行不动(能换回旧镜像)
        db = SettingsDatabase(self.path)
        self.assertEqual(db.get('bot', 'volume'), '0.3')
        self.assertEqual(len(db.items('playlist_item')), 3)
        self.assertTrue(db.has_option('user_ban', '42'))

        # 只做一次:第二次(或者别的服务器)什么都不拿
        s.set('777', 'volume', '0.9')
        self.assertFalse(s.adopt_legacy('777'))
        self.assertFalse(s.adopt_legacy('888'))
        self.assertEqual(s.get('777', 'volume'), '0.9')
        self.assertIsNone(s.get('888', 'volume'))
        self.assertEqual(s.load_queue('888'), (-1, []))

    def test_does_not_overwrite_existing_guild_data(self):
        s = self.store
        s.set('777', 'volume', '0.6')
        s.save_queue('777', 0, [{'id': 'z', 'user': 'u'}])
        s.adopt_legacy('777')
        self.assertEqual(s.get('777', 'volume'), '0.6')
        self.assertEqual(s.load_queue('777'), (0, [{'id': 'z', 'user': 'u'}]))
        self.assertEqual(s.get('777', 'playback_mode'), 'repeat')

    def test_empty_install(self):
        path = os.path.join(self.tmp.name, 'fresh.db')
        DatabaseMigration(SettingsDatabase(path), self.music).migrate()
        store = GuildStore(path)
        self.assertTrue(store.adopt_legacy('1'))
        self.assertEqual(store.load_queue('1'), (-1, []))
        self.assertFalse(store.adopt_legacy('1'))


# =========================================================================
#   会话:连上 Discord 之后读自己的状态
# =========================================================================

class FakeLink:
    def __init__(self, guild_id):
        self.guild_id = guild_id  # GuildLink 建出来就知道是哪个服务器;会话 start() 时才绑定
        self.users = {}
        self.my_channel_id = None
        self.channels = {}


class Cache(dict):
    def get_item_by_id(self, _id):
        from tests.test_web_api import FakeItem
        item = FakeItem(_id)
        item.type = 'url'
        return self.setdefault(_id, item)


class SessionBase(Tmp):
    def setUp(self):
        super().setUp()
        make_v2_db(self.path)
        self.migrate()
        self._saved = {n: getattr(var, n, None) for n in ('db', 'config', 'store', 'cache', 'playlist', 'bot')}
        var.db = SettingsDatabase(self.path)
        var.store = GuildStore(self.path)
        var.cache = Cache()
        config = configparser.ConfigParser(interpolation=None, allow_no_value=True)
        config.read(os.path.join(ROOT, 'configuration.default.ini'), encoding='utf-8')
        var.config = config

    def tearDown(self):
        for n, v in self._saved.items():
            setattr(var, n, v)
        super().tearDown()

    def make_bot(self, guild_id):
        from bot.core import DJBot, new_queue
        bot = DJBot.__new__(DJBot)
        bot.log = mock.Mock()
        bot.link = FakeLink(guild_id)
        bot.now_playing = mock.Mock()
        bot._init_follow()
        bot.join_channel = mock.Mock()
        bot.schedule_follow_check = mock.Mock()
        bot.get_user_count_in_channel = lambda: 0
        bot.volume_helper = util.VolumeHelper()
        bot.volume_helper.set_volume(0.1)
        bot._guild_state_loaded = False
        bot.set_playlist(new_queue('one-shot'))
        return bot

    def start(self, bot):
        from media.playlist import BasePlaylist
        with mock.patch.object(BasePlaylist, 'async_validate'):
            bot.start()


class SessionLoadTest(SessionBase):
    def test_start_adopts_legacy_and_loads_state(self):
        bot = self.make_bot(777)
        self.assertEqual(bot.guild_id, '')
        self.start(bot)
        self.assertEqual(bot.guild_id, '777')
        self.assertAlmostEqual(bot.volume_helper.plain_volume_set, 0.3)
        self.assertEqual(bot.playlist.mode, 'repeat')
        self.assertIs(var.playlist, bot.playlist)
        self.assertIs(bot.playlist.session, bot)
        self.assertEqual([w.id for w in bot.playlist], ['a', 'b', 'c'])
        self.assertEqual(bot.playlist.current_index, 1)
        self.assertTrue(bot._guild_state_loaded)
        bot.now_playing.start.assert_called_once()

        # 之后的保存写到这个服务器
        bot.save_setting('volume', '0.4')
        bot.playlist.current_index = 2
        bot.playlist.save()
        self.assertEqual(var.store.get('777', 'volume'), '0.4')
        self.assertEqual(var.store.load_queue('777')[0], 2)
        self.assertEqual(var.db.get('bot', 'volume'), '0.3')    # 旧行不再写

    def test_second_guild_starts_from_defaults(self):
        var.store.adopt_legacy('777')
        bot = self.make_bot(888)
        self.start(bot)
        self.assertEqual(bot.playlist.mode, var.config.get('bot', 'playback_mode'))
        self.assertEqual(len(bot.playlist), 0)
        self.assertAlmostEqual(bot.volume_helper.plain_volume_set,
                               min(var.config.getfloat('bot', 'volume'), var.config.getfloat('bot', 'max_volume')))
        self.assertFalse(bot.has_rule('user_ban', '1'))
        self.assertTrue(bot.has_rule('user_ban', '42'))           # 全局封禁到处有效

    def test_volume_capped_by_saved_max_and_bad_mode_falls_back(self):
        var.store.adopt_legacy('777')
        var.store.set('777', 'volume', '0.95')
        var.store.set('777', 'playback_mode', 'bogus')
        bot = self.make_bot(777)
        self.start(bot)
        self.assertAlmostEqual(bot.volume_helper.plain_volume_set, 0.8)
        self.assertEqual(bot.playlist.mode, var.config.get('bot', 'playback_mode'))

    def test_exit_before_state_loaded_keeps_saved_queue(self):
        bot = self.make_bot(777)
        var.store.adopt_legacy('777')
        bot.bind_guild(777)
        bot.save_queue()                                     # 连接中被 docker stop(Hub 的信号处理)
        self.assertEqual(len(var.store.load_queue('777')[1]), 3)


class AdminCommandsTest(SessionBase):
    """服务器管理员的封禁只写本服务器;bot 主人的 /globalban 等写全局。"""

    def setUp(self):
        super().setUp()
        import constants
        constants.load_lang('en_US')
        var.store.adopt_legacy('777')          # 旧版的封禁成了全局规则:user 42、https://bad.example/x
        self.bot = self.make_bot(777)
        self.bot.bind_guild(777)
        self.bot.send_msg = mock.Mock()
        self.bot.drop_from_queue = mock.Mock()

    def sent(self):
        return [c[0][0] for c in self.bot.send_msg.call_args_list]

    def test_server_ban_commands_only_touch_this_guild(self):
        from commands import admin
        bot = self.bot
        ctx = mock.Mock(actor=5, options={'user_name': 'Mallory'})
        admin.cmd_user_ban(bot, 'admin', ctx, 'userban', '66')
        self.assertTrue(var.store.has_rule('user_ban', '66', '777', include_global=False))
        self.assertFalse(var.store.has_rule('user_ban', '66'))              # 不是全局
        self.assertFalse(var.store.has_rule('user_ban', '66', '888'))       # 别的服务器不受影响
        self.assertEqual(var.store.list_rules('user_ban', '777')[-1]['created_by'], '5')

        admin.cmd_url_ban(bot, 'admin', ctx, 'urlban', 'https://bad.example/z')
        self.assertTrue(var.store.has_rule('url_ban', 'https://bad.example/z', '777', include_global=False))
        self.assertFalse(var.store.has_rule('url_ban', 'https://bad.example/z'))
        bot.drop_from_queue.assert_called_once()                            # 只从本服务器的队列拿掉

        admin.cmd_ban_list(bot, 'admin', ctx, 'banlist', '')
        listing = self.sent()[-1]
        self.assertIn('Mallory', listing)
        self.assertIn('https://bad.example/z', listing)
        self.assertNotIn('https://bad.example/x', listing)                  # 全局的不在本服务器的列表里

        admin.cmd_user_unban(bot, 'admin', ctx, 'userunban', '66')
        self.assertFalse(var.store.has_rule('user_ban', '66', '777'))
        admin.cmd_url_unban(bot, 'admin', ctx, 'urlunban', 'https://bad.example/z')
        self.assertFalse(var.store.has_rule('url_ban', 'https://bad.example/z', '777'))

    def test_server_unban_cannot_lift_a_global_ban(self):
        import constants
        from commands import admin
        ctx = mock.Mock(actor=5, options={'user_name': 'Troll'})
        admin.cmd_user_unban(self.bot, 'admin', ctx, 'userunban', '42')
        self.assertTrue(var.store.has_rule('user_ban', '42'))
        self.assertIn(constants.tr_cli('still_banned_globally', target='Troll'), self.sent())
        admin.cmd_url_unban(self.bot, 'admin', ctx, 'urlunban', 'https://bad.example/x')
        self.assertTrue(var.store.has_rule('url_ban', 'https://bad.example/x'))

    def test_unbound_session_does_not_write_global_rules(self):
        from commands import admin
        bot = self.make_bot(888)                                            # 还没绑定服务器
        bot.send_msg = mock.Mock()
        admin.cmd_user_ban(bot, 'admin', mock.Mock(actor=5, options={}), 'userban', '66')
        self.assertFalse(var.store.has_rule('user_ban', '66'))

    def test_global_ban_commands(self):
        import constants
        from commands import admin
        bot = self.bot
        ctx = mock.Mock(actor=5, options={'user': '66', 'user_name': 'Mallory'})
        with mock.patch('commands.admin.discard_everywhere') as discard:
            admin.cmd_global_ban(bot, 'owner', ctx, 'globalban', '66')
        self.assertTrue(var.store.has_rule('user_ban', '66'))
        discard.assert_not_called()                                         # 只封了人

        ctx = mock.Mock(actor=5, options={'url': 'https://worse.example/q'})
        with mock.patch('commands.admin.discard_everywhere') as discard:
            admin.cmd_global_ban(bot, 'owner', ctx, 'globalban', 'https://worse.example/q')
        self.assertTrue(var.store.has_rule('url_ban', 'https://worse.example/q'))
        discard.assert_called_once()                                        # 所有队列、缓存、曲库都删

        admin.cmd_url_whitelist(bot, 'owner', ctx, 'urlwhitelist', 'https://ok.example/a')
        self.assertTrue(var.store.has_rule('url_whitelist', 'https://ok.example/a'))
        admin.cmd_global_ban_list(bot, 'owner', ctx, 'globalbanlist', '')
        listing = self.sent()[-1]
        for text in ('Mallory', 'Troll', 'https://worse.example/q', 'https://ok.example/a'):
            self.assertIn(text, listing)
        admin.cmd_url_unwhitelist(bot, 'owner', ctx, 'urlunwhitelist', 'https://ok.example/a')
        self.assertFalse(var.store.has_rule('url_whitelist', 'https://ok.example/a'))
        self.assertIn(constants.tr_cli('url_unwhitelist_success', url='https://ok.example/a'), self.sent())

        ctx = mock.Mock(actor=5, options={'user': '66', 'user_name': 'Mallory', 'url': 'https://worse.example/q'})
        admin.cmd_global_unban(bot, 'owner', ctx, 'globalunban', '')
        self.assertFalse(var.store.has_rule('user_ban', '66'))
        self.assertFalse(var.store.has_rule('url_ban', 'https://worse.example/q'))
        admin.cmd_global_unban(bot, 'owner', mock.Mock(actor=5, options={}), 'globalunban', '')
        self.assertEqual(self.sent()[-1], constants.tr_cli('bad_parameter', command='globalunban'))


class DropDatabaseTest(SessionBase):
    def setUp(self):
        super().setUp()
        import constants
        constants.load_lang('en_US')
        self._saved_paths = (var.music_db, var.settings_db_path)
        var.music_db = self.music
        var.settings_db_path = self.path
        var.store.adopt_legacy('777')
        var.store.set('777', 'volume', '0.5')
        var.store.add_rule('777', 'user_ban', '1')
        var.store.save_queue('777', 0, [{'id': 'a', 'user': 'x'}])
        var.config.set('bot', 'admin', '111')
        self.bot = self.make_bot(777)
        self.bot.bind_guild(777)
        self.bot.send_msg = mock.Mock()

    def tearDown(self):
        var.music_db, var.settings_db_path = self._saved_paths
        super().tearDown()

    def rows(self, table):
        conn = sqlite3.connect(self.path)
        try:
            return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        finally:
            conn.close()

    def ctx(self, actor, admin=False):
        from bot.discord_link import CommandContext
        return CommandContext(actor=actor, name='x', username='x', command='drop_database', argument='',
                              is_admin=admin)

    def test_guild_admin_cannot_drop(self):
        from commands import library
        library.cmd_drop_database(self.bot, 'x', self.ctx(5, admin=True), 'dropdatabase', '')
        self.assertEqual(self.rows('guild_settings') > 0, True)
        self.assertEqual(self.rows('access_rule') > 0, True)

    def test_owner_drop_clears_guild_tables_and_keeps_db_paths(self):
        from commands import library
        library.cmd_drop_database(self.bot, 'x', self.ctx(111), 'dropdatabase', '')
        for table in GuildStore.TABLES:
            self.assertEqual(self.rows(table), 0, table)
        # 以前 music_db 被重建成指向 settings 库
        self.assertEqual(var.music_db.db_path, self.music.db_path)
        self.assertNotEqual(var.music_db.db_path, var.settings_db_path)
        self.assertEqual(var.db.db_path, self.path)
        # 表按当前版本重新建好,马上能用
        self.assertIn('music', tables(self.music.db_path))
        self.assertEqual(var.db.get('bot', 'db_version'), str(SETTING_DB_VERSION))
        var.store.set('777', 'volume', '0.2')
        self.assertEqual(var.store.get('777', 'volume'), '0.2')


if __name__ == '__main__':
    unittest.main()
