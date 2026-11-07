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

    def humans_in(self, guild_id, channel_id):
        return self.humans.get((str(guild_id), str(channel_id)), 0)

    humans = {}

    def close(self):
        self.closed = True


class FakeLink:
    """hub._create_session 建的 GuildLink 的替身。"""

    def __init__(self, client, guild_id, announce_channel_id=None, **kw):
        self.client = client
        self.guild_id = int(guild_id) if guild_id else None
        self.announce_channel_id = int(announce_channel_id) if announce_channel_id else None
        self.my_channel_id = None
        self.closed = None

    def close(self, reason='closed'):
        self.closed = reason


#: FakeDJBot 存队列的地方(guild id -> 队列),相当于数据库
SAVED = {}


class FakeDJBot:
    """hub._create_session 建的 DJBot 的替身:start() 从 SAVED 读队列,播放循环退出时存回去。"""
    version = 'git'
    created = []
    start_delay = 0.0

    def __init__(self, args, link, executor=None, ticker=None, timers=None):
        self.link, self.executor, self.ticker, self.timers = link, executor, ticker, timers
        self.guild_id = str(link.guild_id or '')
        self.channel = 'Music'
        self.exit = False
        self.idle = False
        self.released = False
        self.last_loop_at = time.time()
        self.queue = []
        self.startup = None
        FakeDJBot.created.append(self)

    def register_slash_commands(self, named):
        pass

    def start(self, startup=False):
        time.sleep(self.start_delay)
        self.startup = startup
        self.queue = list(SAVED.get(self.guild_id, []))

    def loop(self):
        while not self.exit:
            self.last_loop_at = time.time()
            time.sleep(0.01)
        self.save_queue()

    def stop_session(self):
        self.exit = True

    def save_queue(self):
        SAVED[self.guild_id] = list(self.queue)

    def is_idle(self):
        return self.idle

    def release(self):
        self.released = True


class FakeSession:
    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.exit = False
        self.last_loop_at = time.time()
        self.saved = 0
        self.playlist = object()
        self.idle = False

    def loop(self):
        while not self.exit:
            self.last_loop_at = time.time()
            time.sleep(0.01)

    def stop_session(self):
        self.exit = True

    def save_queue(self):
        self.saved += 1

    def is_idle(self):
        return self.idle


class FakeThread:
    def __init__(self, alive=True):
        self.alive = alive

    def is_alive(self):
        return self.alive


class HubCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._saved = {n: getattr(var, n) for n in ('config', 'tmp_folder', 'hub', 'bot', 'playlist', 'language',
                                                    'store')}
        var.store = None
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
        self.hub.exit = True
        for session in self.hub.sessions():
            session.exit = True
        self.hub.executor.shutdown()
        self.hub.timers.shutdown()
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

            def __init__(self, args, link, executor=None, ticker=None, timers=None):
                self.link, self.executor, self.ticker, self.timers = link, executor, ticker, timers
                self.guild_id = str(link.guild_id)
                events.append(('session', link.guild_id))

            def register_slash_commands(self, named):
                events.append(('commands', len(named)))

            def start(self, startup=False):
                # 建会话的过程中又要这个会话:不会再建一个(也不会等自己)
                events.append(('start', startup, hub_mod_hub().session_for(self.guild_id)))

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
        self.assertEqual(events, [('connect',), ('session', 1), ('commands', 1), ('start', True, None)])
        self.assertIs(var.bot, home)
        self.assertIs(self.hub.session_for('1'), home)
        link = self.client.links[0]
        self.assertEqual((link.guild_id, link.announce_channel_id), (1, 500))
        self.assertIs(home.executor, self.hub.executor)
        self.assertIs(home.ticker, self.hub.ticker)
        self.assertIs(home.timers, self.hub.timers)
        self.assertEqual(self.hub._pinned, {'1'})                            # 主服务器的会话不休眠

    def test_connect_failure_exits_non_zero(self):
        class Broken:
            def __init__(self, *a, **kw):
                self.home_guild_id = None

            def register_commands(self, named, **kw):
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
        self.assertIsNone(self.hub.session_for('2', create=False))           # 不建:没有就是 None
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


def wait_until(predicate, timeout=3.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


class SessionCase(HubCase):
    """会话的建立 / 休眠:DJBot 和 GuildLink 换成替身。"""

    def setUp(self):
        super().setUp()
        SAVED.clear()
        FakeDJBot.created = []
        FakeDJBot.start_delay = 0.0
        patches = [mock.patch.object(hub_mod, 'DJBot', FakeDJBot), mock.patch.object(hub_mod, 'GuildLink', FakeLink)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.hub._home = '1'
        self.hub._pinned = {'1'}
        self.hub._running = True        # 相当于 run() 之后:新会话马上开播放循环

    def hibernated(self, gid):
        return wait_until(lambda: self.hub.session_for(gid, create=False) is None
                          and gid not in self.hub._transitions)


class LazySessionTest(SessionCase):
    def test_concurrent_first_use_creates_one_session(self):
        FakeDJBot.start_delay = 0.2
        got = []
        threads = [threading.Thread(target=lambda: got.append(self.hub.session_for('2'))) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(3)
        self.assertEqual(len(FakeDJBot.created), 1)
        self.assertEqual(len(got), 6)
        self.assertTrue(all(s is FakeDJBot.created[0] for s in got))
        session = got[0]
        self.assertEqual((session.guild_id, session.startup), ('2', False))   # 按需建的:不进默认频道
        self.assertEqual(session.channel, '')                                 # 配置的默认频道是主服务器的
        self.assertIs(session.timers, self.hub.timers)
        self.assertEqual(len(self.client.links), 1)
        self.assertTrue(wait_until(lambda: self.hub._threads['2'].is_alive()))
        self.assertEqual(self.hub._threads['2'].name, 'Player-2')

    def test_failed_start_is_not_registered(self):
        with mock.patch.object(FakeDJBot, 'start', side_effect=RuntimeError('database is locked')):
            self.assertIsNone(self.hub.session_for('2'))
        self.assertEqual(self.client.links[0].closed, 'session failed to start')
        self.assertNotIn('2', self.hub._transitions)
        self.assertIsNotNone(self.hub.session_for('2'))                       # 下次再试

    def test_request_from_the_event_loop_builds_in_the_background(self):
        FakeDJBot.start_delay = 0.1
        self.assertIsNone(self.hub.request_session(2))
        self.assertIsNone(self.hub.session_for('2', create=False))            # 不等:马上返回
        self.assertTrue(wait_until(lambda: self.hub.session_for('2', create=False) is not None))
        self.assertIsNone(self.hub.request_session(2))                        # 已经有了
        self.assertEqual(len(FakeDJBot.created), 1)

    def test_allowed_guilds(self):
        self.hub.allowed_guilds = {'1'}
        self.assertIsNone(self.hub.session_for('2'))
        self.assertEqual(self.hub.request_session(2), constants.tr_cli('server_not_allowed'))
        self.assertEqual(self.hub.guild_ids(), ['1'])
        self.hub.allowed_guilds = set()
        self.assertIsNone(self.hub.session_for('3'))                          # bot 不在这个服务器
        self.assertEqual(self.hub.request_session(3), constants.tr_cli('server_not_allowed'))
        self.assertEqual(FakeDJBot.created, [])

    def test_max_active_sessions(self):
        self.client.guilds = [1, 2, 3]
        self.hub.max_sessions = 2
        self.add_sessions('1')
        self.assertIsNotNone(self.hub.session_for('2'))
        self.assertEqual(self.hub.request_session(3), constants.tr_cli('server_limit_reached'))
        self.assertIsNone(self.hub.session_for('3'))
        self.assertIsNone(self.hub.request_session(2))                        # 已有的照常用

    def test_home_without_explicit_guild_follows_allowed_guilds(self):
        self.hub.allowed_guilds = {'2'}
        self.hub._explicit_home = False
        self.assertEqual(self.hub._pick_home('1'), '2')
        self.hub._explicit_home = True
        self.assertEqual(self.hub._pick_home('1'), '1')                       # 配置写明的主服务器照用
        self.assertTrue(self.hub._allowed('1'))                               # 主服务器总是服务


class HibernateTest(SessionCase):
    def test_idle_session_sleeps_and_comes_back(self):
        session = self.hub.session_for('2')
        session.queue = ['a', 'b']
        self.hub.report_activity('2', 'Song', 'Artist')
        thread = self.hub._threads['2']
        self.assertTrue(wait_until(thread.is_alive))
        self.hub.idle_minutes = 10
        now = time.time()
        self.assertEqual(self.hub.check_idle(now), [])                        # 还在用
        session.idle = True
        self.assertEqual(self.hub.check_idle(now), [])                        # 刚开始闲着
        self.assertEqual(self.hub.check_idle(now + 599), [])
        self.assertEqual(self.hub.check_idle(now + 601), ['2'])
        self.assertTrue(self.hibernated('2'))
        self.assertTrue(wait_until(lambda: not thread.is_alive()))            # 播放循环停了
        self.assertTrue(session.exit and session.released)
        self.assertEqual(session.link.closed, 'hibernated (idle)')
        self.assertEqual(SAVED['2'], ['a', 'b'])                              # 队列存好了
        self.assertNotIn('2', self.hub._activities)                           # 账号状态里没有它了
        self.assertEqual(self.client.presence[-1], (None, ''))
        self.assertFalse(self.hub.exit)                                       # 故意停的:进程不退出
        self.assertEqual(self.hub.exit_code, 0)

        again = self.hub.session_for('2')                                     # 下次用到时恢复
        self.assertIsNot(again, session)
        self.assertEqual(again.queue, ['a', 'b'])
        self.assertEqual(len(self.client.links), 2)
        self.assertTrue(wait_until(lambda: self.hub._threads['2'].is_alive()))

    def test_busy_again_resets_the_clock_and_home_never_sleeps(self):
        home = self.hub.session_for('1')
        other = self.hub.session_for('2')
        home.idle = other.idle = True
        self.hub.idle_minutes = 1
        now = time.time()
        self.hub.check_idle(now)
        other.idle = False
        self.hub.check_idle(now + 30)
        other.idle = True
        self.assertEqual(self.hub.check_idle(now + 70), [])                   # 中间忙过:重新计时
        self.assertEqual(self.hub.check_idle(now + 131), ['2'])               # 主服务器不休眠
        self.assertTrue(self.hibernated('2'))
        self.assertIs(self.hub.session_for('1', create=False), home)
        self.hub.idle_minutes = 0
        self.assertEqual(self.hub.check_idle(now + 9999), [])                 # 0 = 不休眠

    def test_hibernate_rechecks_idle(self):
        session = self.hub.session_for('2')
        self.assertFalse(self.hub.hibernate('2'))                             # 不闲:不停
        self.assertIs(self.hub.session_for('2', create=False), session)
        self.assertFalse(self.hub.hibernate('1', reason='x'))                 # 主服务器:要 force

    def test_watchdog_and_heartbeat_ignore_sleeping_sessions(self):
        session = self.hub.session_for('2')
        self.assertTrue(wait_until(lambda: self.hub._threads['2'].is_alive()))
        session.idle = True
        self.assertTrue(self.hub.hibernate('2'))
        session.last_loop_at = 0                                              # 停了就不再转
        self.hub.watchdog_timeout = 10
        self.hub._exit_process = mock.Mock()
        self.assertIsNone(self.hub.check_watchdog())
        self.assertTrue(self.hub.healthy())
        self.hub._exit_process.assert_not_called()

    def test_command_during_sleep_waits_and_gets_a_fresh_session(self):
        session = self.hub.session_for('2')
        session.queue = ['x']
        session.idle = True
        started = threading.Event()
        release = threading.Event()
        original = session.release

        def slow_release():
            started.set()
            release.wait(2)
            original()

        session.release = slow_release
        self.hub.executor.submit(('2', 'session'), self.hub.hibernate, '2')
        self.assertTrue(started.wait(2))
        self.assertIsNone(self.hub.request_session(2))                        # 正在休眠:排在后面重建
        got = []
        waiter = threading.Thread(target=lambda: got.append(self.hub.session_for('2')))
        waiter.start()
        time.sleep(0.1)
        self.assertEqual(got, [])                                             # 等休眠做完
        release.set()
        waiter.join(3)
        self.assertEqual(len(got), 1)
        self.assertIsNot(got[0], session)
        self.assertEqual(got[0].queue, ['x'])
        self.assertTrue(wait_until(lambda: len(FakeDJBot.created) == 2))
        time.sleep(0.1)
        self.assertEqual(len(FakeDJBot.created), 2)                           # 两个请求只建了一个


class GuildEventsTest(SessionCase):
    def test_removed_from_a_server_stops_its_session(self):
        session = self.hub.session_for('2')
        session.queue = ['keep']
        self.hub._on_guild_removed(2)
        self.assertTrue(self.hibernated('2'))
        self.assertEqual(session.link.closed, 'hibernated (removed from the server)')
        self.assertEqual(SAVED['2'], ['keep'])                                # 数据留着
        self.hub._on_guild_removed(5)                                         # 没有会话的:什么都不做
        self.hub._on_guild_joined(6)                                          # 加入:会话等第一次用到再建
        self.assertEqual(len(FakeDJBot.created), 1)

    def test_rejoin_voice_channels_after_restart(self):
        from bot.store import GuildStore
        from database import DatabaseMigration, MusicDatabase, SettingsDatabase
        db = SettingsDatabase(os.path.join(self.tmp.name, 's.db'))
        DatabaseMigration(db, MusicDatabase(os.path.join(self.tmp.name, 'm.db'))).migrate()
        var.store = GuildStore(db.db_path)
        self.client.guilds = [1, 2, 3, 4]
        var.store.set('2', 'voice_channel', '55')                             # 那里还有人:回去
        var.store.set('3', 'voice_channel', '66')                             # 没人了:忘掉
        var.store.set('9', 'voice_channel', '99')                             # bot 已经不在这个服务器:留着
        var.store.set('1', 'voice_channel', '11')                             # 主服务器自己的 start() 处理
        self.add_sessions('1')
        self.client.humans = {('2', '55'): 2, ('3', '66'): 0, ('1', '11'): 1}
        self.assertEqual(self.hub.rejoin_voice_channels(), ['2'])
        self.assertTrue(wait_until(lambda: self.hub.session_for('2', create=False) is not None))
        self.assertTrue(self.hub.session_for('2', create=False).startup)      # 启动时建的
        self.assertIsNone(var.store.get('3', 'voice_channel'))
        self.assertEqual(var.store.get('9', 'voice_channel'), '99')
        self.assertEqual(var.store.get('1', 'voice_channel'), '11')
        self.assertEqual(len(FakeDJBot.created), 1)


if __name__ == '__main__':
    unittest.main()


def test_stop_playback_is_not_overridden_by_session_exit():
    # 回归:DJBot 上的会话退出方法曾叫 stop(),盖掉了 PlayerMixin.stop(),
    # /stop、/leave、网页停止键会让播放循环退出、整个进程重启
    from bot.core import DJBot
    from bot.player import PlayerMixin
    assert DJBot.stop is PlayerMixin.stop
    assert callable(DJBot.stop_session)
