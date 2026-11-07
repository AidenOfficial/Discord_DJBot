"""频道树 / 默认频道 / 自动跟随。用假的 DiscordLink(频道是 dict,用户有 name/channel_id/session)。"""
import configparser
import os
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import variables as var  # noqa: E402
from bot import channels as chmod  # noqa: E402
from bot.channels import ChannelMixin  # noqa: E402
from bot.store import GuildStore  # noqa: E402
from database import SettingsDatabase  # noqa: E402


class FakeUser:
    def __init__(self, session, name, channel_id):
        self.session, self.name, self.channel_id = session, name, channel_id
        self.self_mute = self.self_deaf = self.mute = self.deaf = False


class FakeUsers(dict):
    """session -> User 的映射,和 DiscordLink.users 一样;多一个 add() 方便造数据。"""

    def __init__(self):
        super().__init__()
        self.myself = None

    @property
    def all(self):
        return self

    def add(self, session, name, channel_id):
        self[session] = FakeUser(session, name, channel_id)
        return self[session]


class FakeLink:
    """bot.discord_link.DiscordLink 里频道逻辑用到的那部分接口。"""

    def __init__(self):
        self.moves = []
        self.users = FakeUsers()
        self.channels = {}
        # 服务器(0) ─┬ Lobby(1)                不在分类里的语音频道
        #            ├ Music(3)
        #            ├ AFK(4)                  服务器的 AFK 频道
        #            ├ Games(2) 分类 ─┬ Squad(5)
        #            │                └ Lobby(6)   同名不同路径
        #            └ Stage(7)                舞台频道,bot 不进
        for cid, name, parent, pos, kind in [
                (0, 'Server', None, 0, 'guild'), (1, 'Lobby', 0, -10000, 'voice'),
                (3, 'Music', 0, -9998, 'voice'), (4, 'AFK', 0, -9997, 'voice'),
                (2, 'Games', 0, 1, 'category'), (5, 'Squad', 2, 0, 'voice'), (6, 'Lobby', 2, 1, 'voice'),
                (7, 'Stage', 0, -9996, 'stage')]:
            ch = {'channel_id': cid, 'name': name, 'position': pos, 'kind': kind,
                  'joinable': kind == 'voice', 'afk': cid == 4}
            if parent is not None:
                ch['parent'] = parent
            self.channels[cid] = ch
        self.users.myself = self.users.add(1, 'DJBot', 3)

    @property
    def myself(self):
        return self.users.myself

    @property
    def my_channel_id(self):
        return self.users.myself.channel_id if self.users.myself else None

    def move(self, channel_id):
        self.moves.append(channel_id)
        self.users.myself.channel_id = channel_id
        return True


class Bot(ChannelMixin):
    def __init__(self):
        self.link = FakeLink()
        self.channel = ''
        self.bots = {'OtherBot'}
        self._init_follow()


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._saved = {n: getattr(var, n, None) for n in ('db', 'config', 'bot', 'store')}
        var.db = SettingsDatabase(os.path.join(self.tmp.name, 's.db'))
        from database import DatabaseMigration, MusicDatabase
        DatabaseMigration(var.db, MusicDatabase(os.path.join(self.tmp.name, 'm.db'))).migrate()
        var.store = GuildStore(var.db.db_path)
        self.bot = Bot()
        # 测试里同步执行跟随检查,不起定时器
        self.bot.schedule_follow_check = lambda delay=0: None

    def tearDown(self):
        for n, v in self._saved.items():
            setattr(var, n, v)
        self.tmp.cleanup()


class TreeTest(Base):
    def test_paths_and_lookup(self):
        b = self.bot
        self.assertEqual(b.channel_path(6), ['Games', 'Lobby'])
        self.assertEqual(b.channel_path(0), [])
        self.assertEqual(b.find_channel_by_path(['Games', 'Lobby']), 6)
        self.assertEqual(b.find_channel_by_path(['Lobby']), 1)
        self.assertEqual(b.find_channel_by_path([]), 0)
        self.assertIsNone(b.find_channel_by_path(['Nope']))

    def test_tree_snapshot(self):
        self.bot.link.users.add(2, 'alice', 5)
        self.bot.link.users.add(3, 'OtherBot', 5)
        tree = self.bot.channel_tree()
        # 和 Discord 一样:不在分类里的语音频道排在分类前面
        self.assertEqual([c['name'] for c in tree['children']], ['Lobby', 'Music', 'AFK', 'Stage', 'Games'])
        games = tree['children'][4]
        self.assertEqual((games['kind'], games['joinable']), ('category', False))
        squad = games['children'][0]
        self.assertEqual(squad['path'], ['Games', 'Squad'])
        self.assertEqual((squad['kind'], squad['joinable']), ('voice', True))
        self.assertEqual([(u['name'], u['is_bot']) for u in squad['users']], [('alice', False), ('OtherBot', True)])
        music = tree['children'][1]
        self.assertTrue(music['users'][0]['is_me'])
        self.assertTrue(tree['children'][2]['afk'])
        self.assertFalse(tree['children'][3]['joinable'])  # 舞台频道

    def test_channel_id_as_default(self):
        self.assertEqual(self.bot.find_channel_by_path(['5']), 5)
        self.bot.channel = '6'
        self.bot.join_channel()
        self.assertEqual(self.bot.link.moves, [6])

    def test_only_voice_channels_are_joinable(self):
        b = self.bot
        self.assertFalse(b.move_to_channel(2))  # 分类
        self.assertFalse(b.move_to_channel(7))  # 舞台
        self.assertFalse(b.move_to_channel(0))  # 服务器本身
        self.assertEqual(b.link.moves, [])
        self.assertTrue(b.move_to_channel(5))
        self.assertEqual(b.link.moves, [5])

    def test_default_channel_falls_back_to_ini_then_db(self):
        self.bot.channel = 'Games/Squad'
        self.assertEqual(self.bot.channel_settings()['default'], ['Games', 'Squad'])
        self.bot.save_channel_settings(default=['Lobby'])
        self.assertEqual(self.bot.channel_settings()['default'], ['Lobby'])
        self.bot.join_channel()
        self.assertEqual(self.bot.link.moves, [1])


class FollowTest(Base):
    def test_off_never_moves(self):
        self.bot.link.users.add(2, 'alice', 5)
        self.assertIsNone(self.bot.follow_target())

    def test_auto_stays_while_someone_is_here(self):
        self.bot.save_channel_settings(follow='auto')
        self.bot.link.users.add(2, 'alice', 3)
        self.bot.link.users.add(3, 'bob', 5)
        self.assertIsNone(self.bot.follow_target())

    def test_auto_follows_last_leaver(self):
        b = self.bot
        b.save_channel_settings(follow='auto')
        alice = b.link.users.add(2, 'alice', 3)
        b.link.users.add(3, 'bob', 1)
        b.link.users.add(4, 'carol', 1)
        b._note_user_event(alice, 'created')
        alice.channel_id = 5           # alice 从 bot 所在频道走到 Squad
        b._note_user_event(alice, 'updated')
        # Lobby 人更多,但应该跟着刚走的 alice 去 Squad
        b.follow_check()
        self.assertEqual(b.link.moves, [5])

    def test_auto_goes_to_busiest_when_leaver_disconnected(self):
        b = self.bot
        b.save_channel_settings(follow='auto')
        alice = b.link.users.add(2, 'alice', 3)
        b._note_user_event(alice, 'created')
        del b.link.users.all[2]
        b._note_user_event(alice, 'removed')
        b.link.users.add(3, 'bob', 1)
        b.link.users.add(4, 'carol', 6)
        b.link.users.add(5, 'dave', 6)
        b.link.users.add(6, 'OtherBot', 1)  # 其他 bot 不算人
        b.follow_check()
        self.assertEqual(b.link.moves, [6])

    def test_auto_never_follows_into_afk(self):
        b = self.bot
        b.save_channel_settings(follow='auto', return_home=False)
        b.link.users.add(2, 'alice', 4)
        b.link.users.add(3, 'bob', 4)
        self.assertIsNone(b.follow_target())

    def test_discord_bots_are_not_people(self):
        b = self.bot
        b.save_channel_settings(follow='auto', return_home=False)
        other = b.link.users.add(2, 'MusicBot2', 5)
        other.bot = True
        self.assertIsNone(b.follow_target())

    def test_not_in_voice_never_auto_joins(self):
        b = self.bot
        b.save_channel_settings(follow='auto', default=['Lobby'])
        b.link.users.myself.channel_id = None  # /leave 之后
        b.link.users.add(2, 'alice', 5)
        self.assertIsNone(b.follow_target())

    def test_stale_leaver_ignored(self):
        b = self.bot
        b.save_channel_settings(follow='auto')
        b._last_leaver = (time.time() - chmod.LAST_LEAVER_TTL - 1, 5)
        b.link.users.add(2, 'alice', 5)
        b.link.users.add(3, 'bob', 6)
        b.link.users.add(4, 'carol', 6)
        self.assertEqual(b.follow_target(), 6)

    def test_return_home_when_server_empty(self):
        b = self.bot
        b.save_channel_settings(follow='auto', default=['Lobby'])
        b.follow_check()
        self.assertEqual(b.link.moves, [1])
        b.link.moves.clear()
        b.follow_check()  # 已经在家,不再动
        self.assertEqual(b.link.moves, [])
        b.link.users.myself.channel_id = 3
        b.save_channel_settings(return_home=False)
        b.follow_check()
        self.assertEqual(b.link.moves, [])

    def test_follow_specific_user(self):
        b = self.bot
        b.save_channel_settings(follow='user', follow_user='aiden')
        b.link.users.add(2, 'someone', 3)  # 本频道有人也照样跟
        aiden = b.link.users.add(3, 'aiden', 5)
        b.follow_check()
        self.assertEqual(b.link.moves, [5])
        aiden.channel_id = 6
        b.follow_check()
        self.assertEqual(b.link.moves, [5, 6])
        aiden.channel_id = 4  # 进了 AFK 频道:不跟进去,退回 auto 逻辑,去还有人的频道
        b.follow_check()
        self.assertEqual(b.link.moves, [5, 6, 3])

    def test_followed_user_offline_falls_back_to_auto(self):
        b = self.bot
        b.save_channel_settings(follow='user', follow_user='aiden', return_home=False)
        b.link.users.add(2, 'bob', 6)
        self.assertEqual(b.follow_target(), 6)

    def test_follow_would_move_guards_pause(self):
        b = self.bot
        self.assertFalse(b.follow_would_move())
        b.save_channel_settings(follow='auto')
        b.link.users.add(2, 'bob', 6)
        self.assertTrue(b.follow_would_move())

    def test_invalid_mode_rejected(self):
        with self.assertRaises(ValueError):
            self.bot.save_channel_settings(follow='teleport')


class DebounceTest(Base):
    def test_rapid_events_collapse_into_one_check(self):
        b = Bot()
        calls = []
        b.follow_check = lambda: calls.append(1)
        with mock.patch.object(chmod, 'DEBOUNCE_SECONDS', 0.05):
            for _ in range(5):
                b.schedule_follow_check(delay=0.05)
            time.sleep(0.3)
        self.assertEqual(len(calls), 1)


class ApiTest(Base):
    def setUp(self):
        super().setUp()
        from flask import Flask
        import web_channels
        var.bot = self.bot
        var.config = configparser.ConfigParser()
        app = Flask(__name__)
        app.register_blueprint(web_channels.create_blueprint(lambda f: f))
        self.client = app.test_client()

    def test_overview_settings_and_join(self):
        self.bot.link.users.add(2, 'alice', 5)
        data = self.client.get('/api/channels').get_json()
        # Discord 的 ID 超过 JS 安全整数,一律用字符串
        self.assertEqual(data['current_channel_id'], '3')
        self.assertEqual(data['online_users'], ['alice'])
        self.assertEqual(data['tree']['name'], 'Server')
        self.assertEqual(data['tree']['children'][4]['children'][0]['users'][0]['session'], '2')

        rv = self.client.post('/api/channels/settings', json={
            'default_channel_id': '6', 'follow': 'user', 'follow_user': 'alice', 'return_home': False})
        s = rv.get_json()['settings']
        self.assertEqual((s['default_path'], s['default_channel_id'], s['follow'], s['follow_user'], s['return_home']),
                         (['Games', 'Lobby'], '6', 'user', 'alice', False))
        s = self.client.post('/api/channels/settings', json={'default_channel_id': None}).get_json()['settings']
        self.assertEqual((s['default_path'], s['default_channel_id']), ([], None))

        self.assertEqual(self.client.post('/api/channels/settings', json={'follow': 'x'}).status_code, 400)
        self.assertEqual(self.client.post('/api/channels/settings', json={'default_channel_id': 99}).status_code, 404)
        self.assertEqual(self.client.post('/api/channels/settings', json={'default_channel_id': '2'}).status_code, 404)
        self.assertEqual(self.client.post('/api/channels/settings', json={}).status_code, 400)

        rv = self.client.post('/api/channels/join', json={'channel_id': '5'})
        self.assertEqual(rv.get_json()['current_channel_id'], '5')
        self.assertEqual(self.client.post('/api/channels/join', json={'channel_id': 'x'}).status_code, 400)
        self.assertEqual(self.client.post('/api/channels/join', json={'channel_id': '2'}).status_code, 404)


if __name__ == '__main__':
    unittest.main()


class IdleBot(Bot):
    def __init__(self):
        super().__init__()
        self.is_pause = False
        self.calls = []

    def pause(self):
        self.calls.append('pause')
        self.is_pause = True

    def resume(self):
        self.calls.append('resume')
        self.is_pause = False


class IdlePauseTest(Base):
    def setUp(self):
        super().setUp()
        self.bot = IdleBot()
        self.bot.schedule_follow_check = lambda delay=0: None
        self._saved_playlist = var.playlist
        var.playlist = ['song']
        self.t = 1000.0

    def tearDown(self):
        var.playlist = self._saved_playlist
        super().tearDown()

    def tick(self, advance):
        self.t += advance
        self.bot.idle_tick(now=self.t)

    def test_pauses_after_five_empty_minutes_and_resumes_when_someone_returns(self):
        b = self.bot
        self.tick(0)
        self.tick(299)
        self.assertEqual(b.calls, [])            # 还不到 5 分钟
        self.tick(2)
        self.assertEqual(b.calls, ['pause'])
        self.tick(60)
        self.assertEqual(b.calls, ['pause'])     # 不会重复暂停
        b.link.users.add(2, 'alice', 3)        # 有人回到 bot 所在频道
        self.tick(3)
        self.assertEqual(b.calls, ['pause', 'resume'])

    def test_someone_present_never_pauses(self):
        self.bot.link.users.add(2, 'alice', 3)
        for _ in range(10):
            self.tick(100)
        self.assertEqual(self.bot.calls, [])

    def test_manual_pause_is_not_auto_resumed(self):
        b = self.bot
        b.is_pause = True                        # 有人手动暂停
        self.tick(0)
        self.tick(400)
        b.link.users.add(2, 'alice', 3)
        self.tick(3)
        self.assertEqual(b.calls, [])

    def test_manual_resume_restarts_the_timer(self):
        b = self.bot
        self.tick(0)
        self.tick(301)
        self.assertEqual(b.calls, ['pause'])
        b.is_pause = False                       # 没人也手动点了继续
        self.tick(3)
        self.tick(200)
        self.assertEqual(b.calls, ['pause'])     # 重新计时,没马上又停
        self.tick(110)
        self.assertEqual(b.calls, ['pause', 'pause'])

    def test_disabled_and_resume_toggle(self):
        b = self.bot
        b.save_channel_settings(idle_pause_minutes=0)
        self.tick(0)
        self.tick(3600)
        self.assertEqual(b.calls, [])
        b.save_channel_settings(idle_pause_minutes=1, idle_resume=False)
        self.tick(61)
        self.assertEqual(b.calls, ['pause'])
        b.link.users.add(2, 'alice', 3)
        self.tick(3)
        self.assertEqual(b.calls, ['pause'])     # 关了自动继续

    def test_follow_takes_priority_over_pausing(self):
        b = self.bot
        b.save_channel_settings(follow='auto')
        b.link.users.add(2, 'alice', 1)        # 别的频道有人:应该跟过去而不是暂停
        self.tick(0)
        self.tick(400)
        self.assertEqual(b.calls, [])
