# coding=utf-8
"""每个服务器的限额(bot.limits):队列长度、音量;链接校验时按队列所属的服务器查本服务器的封禁。"""
import configparser
import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import constants  # noqa: E402
import media.playlist as mp  # noqa: E402
import variables as var  # noqa: E402
from bot.store import GuildStore  # noqa: E402
from database import DatabaseMigration, MusicDatabase, SettingsDatabase  # noqa: E402
from media.item import BlockedHereError, ValidationFailedError, validating_for  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Wrapper:
    def __init__(self, id):
        self.id = id
        self.version = 0


class Session:
    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.messages = []
        self.dropped = []

    def send_channel_msg(self, msg):
        self.messages.append(msg)

    def drop_from_queue(self, item_id):
        self.dropped.append(item_id)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._saved = (var.config, var.store, var.db, var.playlist, var.cache)
        config = configparser.ConfigParser(interpolation=None, allow_no_value=True)
        config.read(os.path.join(ROOT, 'configuration.default.ini'), encoding='utf-8')
        var.config = config
        var.db = SettingsDatabase(os.path.join(self.tmp.name, 's.db'))
        DatabaseMigration(var.db, MusicDatabase(os.path.join(self.tmp.name, 'm.db'))).migrate()
        var.store = GuildStore(var.db.db_path)
        constants.load_lang('en_US')

    def tearDown(self):
        var.config, var.store, var.db, var.playlist, var.cache = self._saved
        self.tmp.cleanup()


class QueueLimitTest(Base):
    def setUp(self):
        super().setUp()
        patcher = mock.patch.object(mp.BasePlaylist, 'async_validate')
        patcher.start()
        self.addCleanup(patcher.stop)

    def queue(self):
        playlist = mp.OneshotPlaylist()
        playlist.session = Session('777')
        return playlist

    def test_unlimited_by_default(self):
        playlist = self.queue()
        playlist.extend([Wrapper(str(i)) for i in range(500)])
        self.assertEqual(len(playlist), 500)

    def test_full_queue_refuses_everything_at_once(self):
        var.config.set('bot', 'max_queue_length', '3')
        playlist = self.queue()
        playlist.append(Wrapper('a'))
        playlist.insert(0, Wrapper('b'))
        with self.assertRaises(mp.QueueFullError) as cm:
            playlist.extend([Wrapper('c'), Wrapper('d')])
        self.assertEqual(cm.exception.limit, 3)
        self.assertEqual([w.id for w in playlist], ['b', 'a'])       # 一首都没加
        playlist.append(Wrapper('c'))
        with self.assertRaises(mp.QueueFullError):
            playlist.append(Wrapper('d'))
        with self.assertRaises(mp.QueueFullError):
            playlist.insert(0, Wrapper('d'))
        # 换播放模式 / 读存的队列不受限额影响
        moved = mp.get_playlist('repeat', playlist)
        self.assertEqual(len(moved), 3)
        moved.from_list([Wrapper(str(i)) for i in range(10)], -1)
        self.assertEqual(len(moved), 10)


class VolumeLimitTest(Base):
    def test_guild_max_volume(self):
        from bot.limits import guild_max_volume
        self.assertAlmostEqual(guild_max_volume('777'), var.config.getfloat('bot', 'max_volume'))
        var.store.set('777', 'max_volume', '0.4')
        self.assertAlmostEqual(guild_max_volume('777'), 0.4)
        self.assertAlmostEqual(guild_max_volume('888'), var.config.getfloat('bot', 'max_volume'))
        var.store.set('777', 'max_volume', '7')                      # 不超过限额的硬上限
        self.assertAlmostEqual(guild_max_volume('777'), 1.0)

    def test_max_volume_command_is_per_guild(self):
        import util
        from commands import volume
        bot = mock.Mock(guild_id='777', store=var.store)
        bot.volume_helper = util.VolumeHelper()
        bot.volume_helper.set_volume(0.9)
        bot.save_setting = lambda key, value: var.store.set('777', key, value)
        volume.cmd_max_volume(bot, 'Aiden', None, 'maxvolume', '50')
        self.assertEqual(float(var.store.get('777', 'max_volume')), 0.5)
        self.assertIsNone(var.store.get('888', 'max_volume'))
        self.assertAlmostEqual(bot.volume_helper.plain_volume_set, 0.5)   # 当前音量也压下来
        volume.cmd_volume(bot, 'Aiden', None, 'volume', '80')
        self.assertAlmostEqual(bot.volume_helper.plain_volume_set, 0.5)


class GuildUrlBanValidationTest(Base):
    def setUp(self):
        super().setUp()
        import media.url as mu
        self.patch_tmp = mock.patch.object(var, 'tmp_folder', self.tmp.name + os.sep, create=True)
        self.patch_tmp.start()
        self.addCleanup(self.patch_tmp.stop)
        self.item = mu.URLItem('https://example.com/v')
        self.item.ready = 'validated'                              # 别的服务器已经校验过、正在用

    def test_guild_ban_is_checked_for_the_owning_guild_only(self):
        var.store.add_rule('777', 'url_ban', 'https://example.com/v')
        with validating_for('777'), self.assertRaises(BlockedHereError):
            self.item.validate()
        with validating_for('888'):
            self.assertTrue(self.item.validate())
        self.assertTrue(self.item.validate())                       # 不知道是哪个服务器:只看全局

    def test_queue_drops_only_its_own_copy_on_a_guild_ban(self):
        class BlockedWrapper(Wrapper):
            def item(self):
                return self

            def format_debug_string(self):
                return self.id

            def validate(self):
                from media.item import validation_guild
                if validation_guild() == '777':
                    raise BlockedHereError('banned here')
                return True

        cache = mock.Mock()
        var.cache = cache
        banned_here = mp.OneshotPlaylist()
        banned_here.session = Session('777')
        banned_here.pending_items = [BlockedWrapper('x')]
        banned_here._check_valid()
        self.assertEqual(banned_here.session.dropped, ['x'])
        self.assertEqual(banned_here.session.messages, ['banned here'])
        cache.free_and_delete.assert_not_called()                  # 缓存 / 文件 / 别的服务器的队列不动

        elsewhere = mp.OneshotPlaylist()
        elsewhere.session = Session('888')
        elsewhere.pending_items = [BlockedWrapper('x')]
        elsewhere._check_valid()
        self.assertEqual(elsewhere.session.dropped, [])

    def test_global_ban_still_discards_everywhere(self):
        self.assertTrue(issubclass(BlockedHereError, ValidationFailedError))
        var.store.add_rule('', 'url_ban', 'https://example.com/w')
        import media.url as mu
        item = mu.URLItem('https://example.com/w')
        with validating_for('888'), self.assertRaises(ValidationFailedError) as cm:
            item.validate()
        self.assertNotIsInstance(cm.exception, BlockedHereError)


if __name__ == '__main__':
    unittest.main()
