# coding=utf-8
"""Hub:启动顺序、退出流程、看门狗 / 心跳、bot 账号状态汇总、给 Web 层的接口。不连真实的 Discord。"""
import configparser
import os
import sys
import tempfile
import threading
import time
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import constants  # noqa: E402
import variables as var  # noqa: E402
from bot import hub as hub_mod  # noqa: E402
from bot.hub import Hub  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class FakeClient:
    def __init__(self, guilds=(), members=None):
        self.presence = []
        self.guilds = list(guilds)
        self.members = members or {}
        self.fetches = []
        self.links = []
        self.alive = True
        self.close_reason = ''
        self.closed = False
        self.home_guild_id = None

    def set_presence(self, text, state=''):
        self.presence.append((text, state))

    def guild_ids(self):
        return list(self.guilds)

    def guild_info(self, guild_id):
        return {'id': str(guild_id), 'name': f'G{guild_id}', 'icon': ''} if int(guild_id) in self.guilds else None

    def fetch_member(self, guild_id, user_id):
        self.fetches.append((guild_id, user_id))
        return self.members.get((str(guild_id), str(user_id)), False)

    def add_link(self, link):
        self.links.append(link)
        return link

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.exit = False
        self.last_loop_at = time.time()
        self.saved = 0
        self.playlist = object()

    def loop(self):
        while not self.exit:
            self.last_loop_at = time.time()
            time.sleep(0.01)

    def stop(self):
        self.exit = True

    def save_queue(self):
        self.saved += 1


class FakeThread:
    def __init__(self, alive=True):
        self.alive = alive

    def is_alive(self):
        return self.alive


class HubCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._saved = {n: getattr(var, n) for n in ('config', 'tmp_folder', 'hub', 'bot', 'playlist', 'language')}
        config = configparser.ConfigParser(interpolation=None, allow_no_value=True)
        config.read(os.path.join(ROOT, 'configuration.default.ini'), encoding='utf-8')
        var.config = config
        var.tmp_folder = self.tmp.name + os.sep
        var.language = 'en_US'
        constants.load_lang('en_US')
        os.environ.pop('BAM_HEARTBEAT', None)
        self.hub = Hub(types.SimpleNamespace(token=None, guild=None, channel=None), install_signals=False)
        self.client = FakeClient(guilds=[1, 2])
        self.hub.client = self.client

    def tearDown(self):
        self.hub.executor.shutdown()
        self.hub.ticker.stop()
        for n, v in self._saved.items():
            setattr(var, n, v)
        self.tmp.cleanup()

    def add_sessions(self, *gids, alive=True):
        sessions = {}
        for gid in gids:
            sessions[gid] = FakeSession(gid)
            self.hub._sessions[gid] = sessions[gid]
            self.hub._threads[gid] = FakeThread(alive)
        return sessions


class PresenceTest(HubCase):
    def test_zero_one_and_many_servers_playing(self):
        hub, client = self.hub, self.client
        hub.report_activity(1, 'Cherry Candy', 'Lunak')
        self.assertEqual(client.presence, [('Cherry Candy', 'Lunak')])      # 一个:那首歌 + 歌手
        hub.report_activity('2', 'Other Song', '')
        self.assertEqual(client.presence[-1], ('2 servers', ''))           # 多个:正在听 N 个服务器
        hub.report_activity('2', 'Next Song', 'X')
        self.assertEqual(len(client.presence), 2)                           # 显示的没变:不重复发
        hub.report_activity(1, None)
        self.assertEqual(client.presence[-1], ('Next Song', 'X'))
        hub.report_activity('2', None)
        self.assertEqual(client.presence[-1], (None, ''))                   # 没有:清除
        hub.report_activity('2', None)
        self.assertEqual(len(client.presence), 4)

    def test_server_count_is_localised(self):
        constants.load_lang('zh_CN')
        self.hub.report_activity(1, 'A')
        self.hub.report_activity(2, 'B')
        self.hub.report_activity(3, 'C')
        self.assertEqual(self.client.presence[-1], ('3 个服务器', ''))
        for lang in ('en_US', 'zh_CN', 'ja_JP'):
            constants.load_lang(lang)
            self.assertIn('5', constants.tr_cli('presence_servers', count=5))


class WatchdogTest(HubCase):
    def test_one_stalled_session_restarts_the_process(self):
        sessions = self.add_sessions('1', '2')
        self.hub.watchdog_timeout = 120
        self.hub._exit_process = mock.Mock()
        now = time.time()
        self.assertIsNone(self.hub.check_watchdog(now + 60))
        self.hub._exit_process.assert_not_called()
        sessions['1'].last_loop_at = now + 50                                # 1 还在转,2 卡住了
        self.assertEqual(self.hub.check_watchdog(now + 130), '2')
        self.hub._exit_process.assert_called_once_with(1)

    def test_dead_threads_disabled_watchdog_and_exit_are_ignored(self):
        self.add_sessions('1')
        self.hub._threads['1'].alive = False
        self.hub.watchdog_timeout = 10
        self.hub._exit_process = mock.Mock()
        self.assertIsNone(self.hub.check_watchdog(time.time() + 100))
        self.hub._threads['1'].alive = True
        self.hub.watchdog_timeout = 0
        self.assertIsNone(self.hub.check_watchdog(time.time() + 100))
        self.hub.watchdog_timeout = 10
        self.hub.exit = True                                                 # 正在退出:播放循环在收尾
        self.assertIsNone(self.hub.check_watchdog(time.time() + 100))
        self.hub._exit_process.assert_not_called()


class HeartbeatTest(HubCase):
    def test_heartbeat_only_while_every_loop_is_alive(self):
        sessions = self.add_sessions('1', '2')
        path = self.hub.heartbeat_file
        self.assertTrue(path.startswith(self.tmp.name))
        now = time.time()
        self.assertTrue(self.hub.write_heartbeat(now))
        self.assertTrue(os.path.exists(path))
        os.remove(path)
        sessions['2'].last_loop_at = now - hub_mod.HEARTBEAT_STALE - 1      # 一个卡住了
        self.assertFalse(self.hub.write_heartbeat(now))
        self.assertFalse(os.path.exists(path))
        sessions['2'].last_loop_at = now
        self.hub._threads['1'].alive = False                                # 一个循环死了
        self.assertFalse(self.hub.healthy(now))
        self.hub._threads['1'].alive = True
        self.assertTrue(self.hub.healthy(now))


class LifecycleTest(HubCase):
    def test_kill_stops_every_loop_then_disconnects(self):
        sessions = self.add_sessions('1', '2')
        del self.hub._threads['1'], self.hub._threads['2']
        codes = []
        main = threading.Thread(target=lambda: codes.append(self.hub.run()), daemon=True)
        main.start()
        time.sleep(0.1)
        self.assertEqual(sorted(t.name for t in self.hub._threads.values()), ['Player-1', 'Player-2'])
        self.assertTrue(all(t.is_alive() for t in self.hub._threads.values()))

        from commands import admin
        var.hub = self.hub
        bot = mock.Mock()
        admin.cmd_kill(bot, 'admin', None, 'kill', '')
        bot.pause.assert_called_once()
        main.join(3)
        self.assertEqual(codes, [0])
        self.assertTrue(all(s.exit for s in sessions.values()))
        self.assertTrue(self.client.closed)

    def test_unexpected_loop_end_exits_non_zero(self):
        sessions = self.add_sessions('1')
        del self.hub._threads['1']
        sessions['1'].loop = mock.Mock(side_effect=RuntimeError('boom'))
        codes = []
        main = threading.Thread(target=lambda: codes.append(self.hub.run()), daemon=True)
        main.start()
        main.join(3)
        self.assertEqual(codes, [1])
        self.assertTrue(self.client.closed)

    def test_signal_saves_every_queue_and_stops(self):
        sessions = self.add_sessions('1', '2', alive=False)
        self.hub._on_signal(15, None)
        self.assertEqual([s.saved for s in sessions.values()], [1, 1])
        self.assertTrue(self.hub.exit and all(s.exit for s in sessions.values()))
        self.assertTrue(self.hub._done.is_set())                            # 没有在跑的循环:直接可以收尾
        self.hub._on_signal(15, None)
        with self.assertRaises(SystemExit):                                 # 第三次:强制退出
            self.hub._on_signal(15, None)

    def test_startup_order(self):
        events = []

        class Session:
            version = 'git'

            def __init__(self, args, link, executor=None, ticker=None):
                self.link, self.executor, self.ticker = link, executor, ticker
                self.guild_id = str(link.guild_id)
                events.append(('session', link.guild_id))

            def register_slash_commands(self, named):
                events.append(('commands', len(named)))

            def start(self):
                events.append(('start', hub_mod_hub().session_for(self.guild_id)))

        def hub_mod_hub():
            return self.hub

        def connect():
            events.append(('connect',))
            self.hub._home = '1'

        var.config.set('discord', 'announce_channel', '500')
        self.hub.named_specs = [('play', object())]
        self.hub.connect = connect
        with mock.patch.object(hub_mod, 'DJBot', Session):
            home = self.hub.start()
        # 先连上 -> 建会话 -> 注册命令表 -> start(读状态、进频道);start 期间还不对外(Web 拿不到)
        self.assertEqual(events, [('connect',), ('session', 1), ('commands', 1), ('start', None)])
        self.assertIs(var.bot, home)
        self.assertIs(self.hub.session_for('1'), home)
        link = self.client.links[0]
        self.assertEqual((link.guild_id, link.announce_channel_id), (1, 500))
        self.assertIs(home.executor, self.hub.executor)
        self.assertIs(home.ticker, self.hub.ticker)

    def test_connect_failure_exits_non_zero(self):
        class Broken:
            def __init__(self, *a, **kw):
                self.home_guild_id = None

            def register_commands(self, named):
                pass

            def connect(self):
                raise RuntimeError('401 Unauthorized')

        var.config.set('discord', 'token', 'x')
        with mock.patch.object(hub_mod, 'DiscordClient', Broken), self.assertRaises(SystemExit) as cm:
            self.hub.connect()
        self.assertEqual(cm.exception.code, 1)


class ContractTest(HubCase):
    def test_sessions_and_lookup(self):
        sessions = self.add_sessions('1')
        self.hub._home = '1'
        self.assertEqual(self.hub.sessions(), [sessions['1']])
        self.assertIs(self.hub.session_for('1'), sessions['1'])
        self.assertIs(self.hub.session_for(1), sessions['1'])
        self.assertIsNone(self.hub.session_for('2'))                         # 现在只有主服务器有会话
        self.assertIsNone(self.hub.session_for(''))
        self.assertEqual(self.hub.home_guild_id, '1')

    def test_guilds(self):
        self.assertEqual(self.hub.guild_ids(), ['1', '2'])
        self.assertEqual(self.hub.guild_info('2'), {'id': '2', 'name': 'G2', 'icon': ''})
        self.assertIsNone(self.hub.guild_info(3))

    def test_is_member_is_cached(self):
        self.client.members = {('1', '42'): True}
        self.assertTrue(self.hub.is_member('1', '42'))
        self.assertTrue(self.hub.is_member(1, 42))
        self.assertEqual(len(self.client.fetches), 1)                        # 第二次走缓存
        self.assertFalse(self.hub.is_member('1', '43'))                      # NotFound
        self.assertFalse(self.hub.is_member('1', '43'))
        self.assertEqual(len(self.client.fetches), 2)
        self.client.members[('1', '44')] = None                              # 查不了:不缓存
        self.assertFalse(self.hub.is_member('1', '44'))
        self.assertFalse(self.hub.is_member('1', '44'))
        self.assertEqual(len(self.client.fetches), 4)
        self.assertFalse(self.hub.is_member('1', 'abc'))                     # 不合法的 id 不查
        self.assertEqual(len(self.client.fetches), 4)
        with mock.patch.object(hub_mod.time, 'time', return_value=time.time() + hub_mod.MEMBER_TTL + 1):
            self.assertTrue(self.hub.is_member('1', '42'))                   # 过期了重新查
        self.assertEqual(len(self.client.fetches), 5)

    def test_all_playlists_covers_every_session(self):
        sessions = self.add_sessions('1', '2')
        var.hub = self.hub
        var.bot = sessions['1']
        var.playlist = None
        queues = var.all_playlists()
        self.assertEqual(len(queues), 2)
        self.assertTrue(all(any(q is s.playlist for q in queues) for s in sessions.values()))


if __name__ == '__main__':
    unittest.main()
