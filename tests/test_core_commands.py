# coding=utf-8
"""DJBot 的命令分发:预检查(封禁 / 管理员 / 频道限制)、点歌时自动进语音、出错回复。"""
import configparser
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import constants  # noqa: E402
import variables as var  # noqa: E402
from bot.core import DJBot  # noqa: E402
from bot.discord_link import CommandContext  # noqa: E402
from commands.slash import Spec, _d  # noqa: E402
from bot.store import GuildStore  # noqa: E402
from database import SettingsDatabase  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class FakeLink:
    def __init__(self):
        self.my_channel_id = None
        self.replies = []
        self.moves = []

    def reply(self, ctx, msg, ephemeral=None):
        self.replies.append(msg)

    def send_announcement(self, msg):
        self.replies.append(('announce', msg))

    def move(self, channel_id):
        self.moves.append(channel_id)
        self.my_channel_id = channel_id
        return True

    channels = {}


class CoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._saved = (var.db, var.config, var.user_db, var.store)
        var.db = SettingsDatabase(os.path.join(self.tmp.name, 's.db'))
        from database import DatabaseMigration, MusicDatabase
        DatabaseMigration(var.db, MusicDatabase(os.path.join(self.tmp.name, 'm.db'))).migrate()
        var.store = GuildStore(var.db.db_path)
        var.user_db = None
        config = configparser.ConfigParser(interpolation=None, allow_no_value=True)
        config.read(os.path.join(ROOT, 'configuration.default.ini'), encoding='utf-8')
        var.config = config
        constants.load_lang('en_US')

        bot = DJBot.__new__(DJBot)
        bot.log = mock.Mock()
        bot.link = FakeLink()
        bot.cmd_handle = {}
        bot.slash_names = {}
        bot._init_follow()
        bot.bots = set()
        self.calls = []

        def handler(b, user, text, command, parameter):
            self.calls.append((user, command, parameter))

        def boom(*a):
            raise RuntimeError('kaboom')

        for spec in (Spec('play', 'play', handler, _d('x', 'x', 'x'), joins_voice=True),
                     Spec('queue', 'queue', handler, _d('x', 'x', 'x')),
                     Spec('help', 'help', handler, _d('x', 'x', 'x'), outside_channel=True),
                     Spec('kill', 'kill', handler, _d('x', 'x', 'x'), owner_only=True),
                     Spec('maxvol', 'maxvolume', handler, _d('x', 'x', 'x'), admin=True),
                     Spec('skip', 'skip', boom, _d('x', 'x', 'x'))):
            bot.cmd_handle[spec.key] = {'handle': spec.handler, 'spec': spec, 'name': spec.name}
            bot.slash_names[spec.key] = spec.name
        # 测试里不需要真实的语音频道判定
        bot.move_to_channel = lambda cid, reason='': bot.link.move(cid)
        self.bot = bot

    def tearDown(self):
        var.db, var.config, var.user_db, var.store = self._saved
        self.tmp.cleanup()

    def ctx(self, command, argument='', voice=None, admin=False, actor=42):
        return CommandContext(actor=actor, name='Aiden', username='aiden', command=command,
                              argument=argument, voice_channel_id=voice, is_admin=admin)

    def test_precheck_admin_and_ban(self):
        b = self.bot
        self.assertEqual(b.precheck(self.ctx('maxvol')), constants.tr_cli('not_admin'))
        self.assertIsNone(b.precheck(self.ctx('maxvol', admin=True)))
        var.store.add_rule('', 'user_ban', '42', note='Aiden')
        self.assertEqual(b.precheck(self.ctx('queue')), constants.tr_cli('user_ban'))
        # 全局封禁是 bot 主人定的:服务器管理员也管
        self.assertEqual(b.precheck(self.ctx('queue', admin=True)), constants.tr_cli('user_ban'))
        self.assertIsNone(b.precheck(self.ctx('queue', actor=43)))
        var.config.set('bot', 'admin', '42')                             # 只有 bot 主人自己不受影响
        self.assertIsNone(b.precheck(self.ctx('queue')))

    def test_guild_ban_does_not_apply_to_that_guilds_admins(self):
        b = self.bot
        b.bind_guild(777)
        var.store.add_rule('777', 'user_ban', '42')
        var.store.add_rule('777', 'url_ban', 'https://bad.example/g')
        self.assertEqual(b.precheck(self.ctx('queue')), constants.tr_cli('user_ban'))
        self.assertIsNone(b.precheck(self.ctx('queue', admin=True)))
        self.assertIsNone(b.precheck(self.ctx('play', 'https://bad.example/g', voice=1, admin=True)))
        var.store.add_rule('', 'url_ban', 'https://bad.example/g')      # 全局也封了:管理员也不行
        self.assertIn('https://bad.example/g',
                      b.precheck(self.ctx('play', 'https://bad.example/g', voice=1, admin=True)))

    def test_owner_only_commands_refuse_guild_admins(self):
        b = self.bot
        var.config.set('bot', 'admin', '111;222')
        # 服务器管理员(管理服务器权限)不是 bot 主人
        self.assertEqual(b.precheck(self.ctx('kill', admin=True)), constants.tr_cli('not_owner'))
        self.assertIsNone(b.precheck(self.ctx('kill', actor=222)))
        # 执行前再查一次:预检查没拦住也跑不起来
        b._handle_command(self.ctx('kill', admin=True))
        self.assertEqual(self.calls, [])
        self.assertEqual(b.link.replies, [constants.tr_cli('not_owner')])
        b._handle_command(self.ctx('kill', actor=111))
        self.assertEqual(len(self.calls), 1)
        # bot 主人在每个服务器都算管理员
        self.assertIsNone(b.precheck(self.ctx('maxvol', actor=111)))
        self.assertTrue(b.is_owner('111'))
        self.assertFalse(b.is_owner(self.ctx('queue', admin=True)))

    def test_queue_full_is_reported(self):
        import media.playlist

        def full(*a):
            raise media.playlist.QueueFullError(3)

        self.bot.cmd_handle['queue']['handle'] = full
        self.bot._handle_command(self.ctx('queue'))
        self.assertEqual(self.bot.link.replies, [constants.tr_cli('queue_full', max=3)])

    def test_precheck_url_ban(self):
        var.store.add_rule('', 'url_ban', 'https://bad.example/x')
        refusal = self.bot.precheck(self.ctx('play', 'https://bad.example/x', voice=1))
        self.assertIn('https://bad.example/x', refusal)

    def test_guild_scoped_bans_only_apply_in_that_guild(self):
        b = self.bot
        var.store.add_rule('777', 'user_ban', '42')
        var.store.add_rule('777', 'url_ban', 'https://bad.example/y')
        self.assertIsNone(b.precheck(self.ctx('queue')))               # 还没绑定服务器:只看全局
        b.bind_guild(888)
        self.assertIsNone(b.precheck(self.ctx('queue')))
        b.bind_guild(777)
        self.assertEqual(b.precheck(self.ctx('queue')), constants.tr_cli('user_ban'))
        self.assertIn('https://bad.example/y', b.precheck(self.ctx('play', 'https://bad.example/y', voice=1, actor=43)))

    def test_precheck_voice_channel_rules(self):
        b = self.bot
        # bot 不在语音里:点歌要求发命令的人在语音里,别的命令无所谓
        self.assertEqual(b.precheck(self.ctx('play')), constants.tr_cli('join_voice_first'))
        self.assertIsNone(b.precheck(self.ctx('play', voice=5)))
        self.assertIsNone(b.precheck(self.ctx('queue')))
        # bot 在频道 5:别的频道的人不能控制(除非 outside_channel / 管理员 / 配置放开)
        b.link.my_channel_id = 5
        self.assertEqual(b.precheck(self.ctx('queue', voice=6)), constants.tr_cli('not_in_my_channel'))
        self.assertEqual(b.precheck(self.ctx('queue')), constants.tr_cli('not_in_my_channel'))
        self.assertIsNone(b.precheck(self.ctx('queue', voice=5)))
        self.assertIsNone(b.precheck(self.ctx('help', voice=6)))
        self.assertIsNone(b.precheck(self.ctx('queue', voice=6, admin=True)))
        var.config.set('bot', 'allow_other_channel_message', 'True')
        self.assertIsNone(b.precheck(self.ctx('queue', voice=6)))

    def test_play_joins_the_invokers_channel(self):
        b = self.bot
        b._handle_command(self.ctx('play', 'lofi', voice=5))
        self.assertEqual(b.link.moves, [5])
        self.assertEqual(self.calls, [('Aiden', 'play', 'lofi')])
        b._handle_command(self.ctx('play', 'more', voice=5))
        self.assertEqual(b.link.moves, [5])  # 已经在了,不再动

    def test_failing_join_stops_the_command(self):
        b = self.bot
        b.move_to_channel = lambda cid, reason='': False
        b._handle_command(self.ctx('play', 'lofi', voice=5))
        self.assertEqual(self.calls, [])
        self.assertEqual(b.link.replies, [constants.tr_cli('cannot_join_voice')])

    def test_handler_error_is_reported(self):
        self.bot._handle_command(self.ctx('skip'))
        self.assertIn('kaboom', self.bot.link.replies[-1])

    def test_send_msg_without_context_goes_to_announcements(self):
        self.bot.send_msg('hi', None)
        self.bot.send_msg('there', self.ctx('queue'))
        self.assertEqual(self.bot.link.replies, [('announce', 'hi'), 'there'])

    def test_admin_is_rechecked_when_the_command_runs(self):
        # 预检查超时 / 出错时也不能让管理员命令跑起来
        self.bot._handle_command(self.ctx('maxvol'))
        self.assertEqual(self.calls, [])
        self.assertEqual(self.bot.link.replies, [constants.tr_cli('not_admin')])
        self.bot._handle_command(self.ctx('maxvol', admin=True))
        self.assertEqual(len(self.calls), 1)

    def test_banned_user_is_rechecked(self):
        var.store.add_rule('', 'user_ban', '42', note='Aiden')
        self.bot._handle_command(self.ctx('queue'))
        self.assertEqual(self.calls, [])

    def test_leave_outside_voice_does_not_suppress_the_kick_pause(self):
        self.bot._leaving_until = 0.0
        self.bot.link.leave_voice = mock.Mock()
        self.bot.leave_voice()                 # 不在语音里:什么都不做
        self.assertEqual(self.bot._leaving_until, 0.0)
        self.bot.link.leave_voice.assert_not_called()

    def test_is_admin_by_id(self):
        var.config.set('bot', 'admin', '111;222')
        self.assertTrue(self.bot.is_admin('222'))
        self.assertFalse(self.bot.is_admin('333'))
        self.assertTrue(self.bot.is_admin(self.ctx('queue', admin=True)))

    def test_commands_run_in_order_on_the_shared_pool(self):
        from bot.executor import KeyedExecutor
        b = self.bot
        b.bind_guild(777)
        b.executor = KeyedExecutor(max_workers=4, name='T')
        finished = []
        b.link.finish = lambda ctx: finished.append(ctx.argument)
        for arg in ('a', 'b', 'c'):
            b.command_received(self.ctx('queue', arg))
        b.command_received(self.ctx('skip'))            # 出错的命令也要 finish,不能卡住后面的
        b.command_received(self.ctx('queue', 'd'))
        deadline = time.time() + 2
        while len(finished) < 5 and time.time() < deadline:
            time.sleep(0.01)
        self.assertEqual([c[2] for c in self.calls], ['a', 'b', 'c', 'd'])
        self.assertEqual(finished, ['a', 'b', 'c', '', 'd'])



def test_play_routes_spotify_by_hostname():
    from commands.playback import _is_spotify_host
    assert _is_spotify_host('https://open.spotify.com/track/abc')
    assert _is_spotify_host('https://spotify.com/x')
    assert not _is_spotify_host('https://evil.example/?u=open.spotify.com')
    assert not _is_spotify_host('https://notspotify.com/track/abc')


if __name__ == '__main__':
    unittest.main()
