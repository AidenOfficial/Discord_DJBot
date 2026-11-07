# coding=utf-8
""""正在播放"面板 + 语音频道状态:纯函数、后台更新的决策、DiscordLink 那一侧的发 / 改 / 重发。"""
import asyncio
import base64
import configparser
import os
import sys
import tempfile
import threading
import time
import types
import unittest
from io import BytesIO
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord  # noqa: E402

import constants  # noqa: E402
import variables as var  # noqa: E402
from bot import discord_link as dl  # noqa: E402
from bot import now_playing as np  # noqa: E402
from bot.discord_link import DiscordLink, User  # noqa: E402
from database import SettingsDatabase  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def tiny_jpeg(color=(10, 20, 30)):
    from PIL import Image
    buf = BytesIO()
    Image.new('RGB', (8, 8), color).save(buf, format='JPEG')
    return buf.getvalue()


# =========================================================================
#   假的播放状态
# =========================================================================

class FakeItem:
    def __init__(self, id_, title='Song', artist='', album='', duration=200, type_='url', thumbnail=None):
        self.id, self._title, self.artist, self.album = id_, title, artist, album
        self.duration, self.type, self.thumbnail = duration, type_, thumbnail
        self.track = ''
        self.url = 'https://www.youtube.com/watch?v=' + id_

    def format_title(self):
        return self._title


class FakeWrapper:
    def __init__(self, item, user=''):
        self._item, self.user, self.id = item, user, item.id

    def item(self):
        return self._item


class FakePlaylist(list):
    def __init__(self, items=()):
        super().__init__(FakeWrapper(i) for i in items)
        self.current_index = 0 if items else -1
        self.mode = 'one-shot'

    def current_item(self):
        return self[self.current_index] if 0 <= self.current_index < len(self) else None


class FakeBot:
    # 测试替身:会话的队列就是全局 var.playlist
    playlist = property(lambda self: var.playlist)

    def __init__(self):
        self.is_pause = False
        self.playhead = 0.0
        self.volume_helper = types.SimpleNamespace(plain_volume_set=0.4)
        self.waiting = set()
        self.thread = object()  # ffmpeg 在跑 = 真的在出声

    def is_waiting_for(self, item_id):
        return item_id in self.waiting


class FakeLink:
    def __init__(self):
        self.my_channel_id = 3
        self.shows, self.ends, self.statuses, self.adopted = [], [], [], []
        self.ok = True
        self.panel_ref = None

    def panel_show(self, panel, new_track=False):
        self.shows.append((panel, new_track))
        if self.ok:
            self.panel_ref = (500, 900)
        return self.ok

    def panel_end(self, panel):
        self.ends.append(panel)
        return self.ok

    def panel_adopt(self, channel_id, message_id):
        self.adopted.append((channel_id, message_id))

    def set_voice_status(self, text):
        self.statuses.append(text)
        return True


class _VarCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._saved = (var.db, var.config, var.playlist, var.user_db)
        var.db = SettingsDatabase(os.path.join(self.tmp.name, 's.db'))
        from database import DatabaseMigration, MusicDatabase
        DatabaseMigration(var.db, MusicDatabase(os.path.join(self.tmp.name, 'm.db'))).migrate()
        var.user_db = None
        config = configparser.ConfigParser(interpolation=None, allow_no_value=True)
        config.read(os.path.join(ROOT, 'configuration.default.ini'), encoding='utf-8')
        var.config = config
        constants.load_lang('en_US')
        patcher = mock.patch('media.artwork.has_hd', return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        var.db, var.config, var.playlist, var.user_db = self._saved
        self.tmp.cleanup()


# =========================================================================
#   纯函数
# =========================================================================

class PureTest(_VarCase):
    def test_fmt_time(self):
        self.assertEqual(np.fmt_time(0), '0:00')
        self.assertEqual(np.fmt_time(83.9), '1:23')
        self.assertEqual(np.fmt_time(3723), '1:02:03')
        self.assertEqual(np.fmt_time(-5), '0:00')

    def test_progress_bar(self):
        self.assertEqual(np.progress_bar(10, 0), '')
        bar = np.progress_bar(0, 100, width=10)
        self.assertEqual(bar, '●' + '─' * 9)
        self.assertEqual(np.progress_bar(50, 100, width=10), '━' * 5 + '●' + '─' * 4)
        self.assertEqual(np.progress_bar(500, 100, width=10), '━' * 9 + '●')  # 超过时长也不越界
        self.assertEqual(len(np.progress_bar(37, 100)), np.BAR_WIDTH)

    def test_mode_cycle(self):
        self.assertEqual(np.next_mode('one-shot'), 'repeat')
        self.assertEqual(np.next_mode('repeat'), 'single')
        self.assertEqual(np.next_mode('single'), 'one-shot')
        self.assertEqual(np.next_mode('random'), 'one-shot')

    def test_voice_status_text(self):
        var.playlist = FakePlaylist([FakeItem('a', 'Cherry Candy', artist='Lunak')])
        bot = FakeBot()
        self.assertEqual(np.voice_status(np.snapshot(bot)), '🎵 Cherry Candy — Lunak')
        bot.is_pause = True
        self.assertEqual(np.voice_status(np.snapshot(bot)), '⏸ Cherry Candy — Lunak')
        self.assertEqual(np.voice_status(None), '')
        var.playlist = FakePlaylist([FakeItem('b', 'x' * 900)])
        self.assertEqual(len(np.voice_status(np.snapshot(FakeBot()))), np.VOICE_STATUS_MAX)

    def test_snapshot_states(self):
        var.playlist = FakePlaylist()
        self.assertIsNone(np.snapshot(FakeBot()))
        item = FakeItem('a', 'Song', duration=180)
        item.track = 'Official Name'
        var.playlist = FakePlaylist([item, FakeItem('b')])
        bot = FakeBot()
        bot.playhead = -1  # 还没开始放时是 -1
        snap = np.snapshot(bot)
        self.assertEqual((snap['status'], snap['title'], snap['position']), ('playing', 'Official Name', 0.0))
        self.assertEqual((snap['index'], snap['total'], snap['volume']), (1, 2, 40))
        bot.waiting.add('a')
        self.assertEqual(np.snapshot(bot)['status'], 'loading')
        bot.is_pause = True
        self.assertEqual(np.snapshot(bot)['status'], 'paused')

    def test_build_panel(self):
        var.playlist = FakePlaylist([FakeItem('a', 'Song', artist='Lunak', album='Candy', duration=200)])
        var.playlist[0].user = 'Mevius'
        bot = FakeBot()
        bot.playhead = 83
        panel = np.build_panel(np.snapshot(bot))
        self.assertIn('Now playing', panel['author'])
        self.assertIn('1:23 / 3:20', panel['description'])
        self.assertIn('●', panel['description'])
        self.assertEqual(panel['fields'], [('Artist', 'Lunak'), ('Album', 'Candy')])
        self.assertIn('Play once', panel['footer'])
        self.assertIn('Volume 40%', panel['footer'])
        self.assertIn('Requested by Mevius', panel['footer'])
        self.assertTrue(panel['buttons'])
        self.assertFalse(panel['has_cover'])

        var.playlist = FakePlaylist([FakeItem('r', 'Radio', duration=0, type_='radio')])
        live = np.build_panel(np.snapshot(bot))
        self.assertIn('Live', live['description'])
        self.assertNotIn('●', live['description'])

    def test_cover_from_thumbnail_and_color(self):
        thumb = base64.b64encode(tiny_jpeg((5, 10, 20))).decode()
        var.playlist = FakePlaylist([FakeItem('a', thumbnail=thumb)])
        snap = np.snapshot(FakeBot())
        self.assertEqual(snap['cover_key'][0], 'small')
        data, color = np.load_cover(snap)
        self.assertTrue(data.startswith(b'\xff\xd8'))
        self.assertGreaterEqual(max((color >> 16) & 255, (color >> 8) & 255, color & 255), 90)  # 暗色被提亮

    def test_every_language_has_the_panel_strings(self):
        for lang in ('en_US', 'zh_CN', 'ja_JP'):
            constants.load_lang(lang)
            var.playlist = FakePlaylist([FakeItem('a', artist='A', album='B')])
            for status in ('playing', 'paused', 'loading'):
                bot = FakeBot()
                bot.is_pause = status == 'paused'
                if status == 'loading':
                    bot.waiting.add('a')
                np.build_panel(np.snapshot(bot))
            np.build_ended(None)
            for mode in ('one-shot', 'repeat', 'single', 'random', 'autoplay'):
                self.assertNotEqual(np.mode_label(mode), mode)


# =========================================================================
#   后台更新的决策
# =========================================================================

class ControllerTest(_VarCase):
    def setUp(self):
        super().setUp()
        self.bot = FakeBot()
        self.link = FakeLink()
        self.np = np.NowPlaying(self.bot, self.link)
        var.playlist = FakePlaylist([FakeItem('a', 'One', artist='A'), FakeItem('b', 'Two')])

    def test_lifecycle(self):
        n, link = self.np, self.link
        n.tick(now=100)
        self.assertEqual(len(link.shows), 1)
        self.assertTrue(link.shows[0][1])                   # 第一次:新的一首
        self.assertEqual(link.statuses, ['🎵 One — A'])

        self.bot.playhead = 5
        n.tick(now=105)                                     # 状态没变、没到刷新间隔:不动
        self.assertEqual(len(link.shows), 1)
        n.tick(now=111)                                     # 播放中每 10 秒刷新进度
        self.assertEqual(len(link.shows), 2)
        self.assertFalse(link.shows[1][1])
        self.assertNotIn('cover', link.shows[1][0])         # 封面没变就不重传

        self.bot.is_pause = True
        n.tick(now=112)                                     # 暂停:立刻更新
        self.assertEqual(len(link.shows), 3)
        self.assertIn('Paused', link.shows[2][0]['author'])
        self.assertEqual(link.statuses[-1], '⏸ One — A')
        n.tick(now=200)                                     # 暂停中不刷新进度
        self.assertEqual(len(link.shows), 3)

        self.bot.is_pause = False
        var.playlist.current_index = 1
        n.tick(now=201)                                     # 换歌
        self.assertTrue(link.shows[-1][1])
        self.assertEqual(link.statuses[-1], '🎵 Two')

        var.playlist = FakePlaylist()
        n.tick(now=202)                                     # 放完了:定格、去掉按钮、清掉频道状态
        self.assertEqual(len(link.ends), 1)
        self.assertFalse(link.ends[0]['buttons'])
        self.assertEqual(link.ends[0]['title'], 'Two')
        self.assertEqual(link.statuses[-1], '')
        n.tick(now=203)
        self.assertEqual(len(link.ends), 1)

    def test_restored_queue_does_not_post_until_audio_starts(self):
        self.bot.is_pause = True                            # 启动时恢复了上次的队列(暂停着)
        self.np.tick(now=1)
        self.bot.is_pause = False
        self.bot.thread = None                              # 没暂停,但 ffmpeg 没在跑:还没开始放
        self.np.tick(now=2)
        self.assertEqual(self.link.shows, [])
        self.assertEqual(self.link.statuses, ['⏸ One — A', '🎵 One — A'])  # 频道状态照常
        self.bot.thread = object()
        self.np.tick(now=3)
        self.assertEqual(len(self.link.shows), 1)
        self.bot.thread = None                              # 歌与歌之间的空档:面板已经在了,照常更新
        var.playlist.current_index = 1
        self.np.tick(now=4)
        self.assertEqual(len(self.link.shows), 2)

    def test_failure_backs_off(self):
        self.link.ok = False
        self.np.tick(now=10)
        self.np.tick(now=11)
        self.assertEqual(len(self.link.shows), 1)
        self.np.tick(now=10 + np.RETRY_AFTER)
        self.assertEqual(len(self.link.shows), 2)

    def test_voice_status_only_when_in_voice_and_changed(self):
        self.link.my_channel_id = None
        self.np.tick(now=1)
        self.assertEqual(self.link.statuses, [])
        self.link.my_channel_id = 3
        self.np.tick(now=2)
        self.np.tick(now=3)
        self.assertEqual(self.link.statuses, ['🎵 One — A'])
        self.link.my_channel_id = 4                         # 换了频道:新频道要重新设置
        self.np.tick(now=4)
        self.assertEqual(self.link.statuses, ['🎵 One — A', '🎵 One — A'])

    def test_poke_refreshes_without_waiting_for_the_poll(self):
        ticks = threading.Event()
        with mock.patch.object(np, 'TICK', 30), mock.patch.object(np, 'POKE_DELAY', 0), \
                mock.patch.object(self.np, 'tick', side_effect=lambda: ticks.set()):
            self.np.start()
            self.np.poke()
            self.assertTrue(ticks.wait(2))
            self.np.stop()

    def test_switches(self):
        quiet = np.NowPlaying(self.bot, self.link, panel=False, voice=False)
        quiet.tick(now=1)
        self.assertEqual((self.link.shows, self.link.statuses), ([], []))

    def test_buttons(self):
        self.assertEqual(self.np.resolve_button('toggle'), ('pause', {}))
        self.bot.is_pause = True
        self.assertEqual(self.np.resolve_button('toggle'), ('play', {}))
        self.assertEqual(self.np.resolve_button('skip'), ('skip', {}))
        self.assertEqual(self.np.resolve_button('stop'), ('stop', {}))
        self.assertEqual(self.np.resolve_button('mode'), ('mode', {'mode': 'repeat'}))
        self.assertIsNone(self.np.resolve_button('nope'))

    def test_panel_survives_restart(self):
        self.np.tick(now=1)
        self.assertEqual(var.db.get('discord', 'panel_message'), '500:900')

        link = FakeLink()
        again = np.NowPlaying(self.bot, link)
        again._adopt_panel()
        self.assertEqual(link.adopted, [(500, 900)])
        var.playlist = FakePlaylist()
        again.tick(now=2)                                   # 没在放:把旧面板上的按钮收掉
        again.tick(now=3)
        self.assertEqual(link.ends, [None])


# =========================================================================
#   DiscordLink:发 / 改 / 重发
# =========================================================================

class LoopThread:
    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(2)


class FakeMessage:
    def __init__(self, channel, mid):
        self.channel, self.id = channel, mid
        self.edits, self.deleted = [], False
        self.missing = False

    async def edit(self, **kw):
        if self.missing:
            raise discord.NotFound(types.SimpleNamespace(status=404, reason='Not Found'), 'gone')
        self.edits.append(kw)
        return self

    async def delete(self):
        self.deleted = True


class FakeChannel:
    def __init__(self, cid, perms=None):
        self.id = cid
        self.sent = []
        self.latest = None
        self.perms = perms or types.SimpleNamespace(view_channel=True, send_messages=True, embed_links=True,
                                                    attach_files=True, set_voice_channel_status=True)

    def permissions_for(self, member):
        return self.perms

    async def send(self, **kw):
        msg = FakeMessage(self, 1000 + len(self.sent))
        self.sent.append(kw)
        self.latest = msg
        return msg

    def history(self, limit=1):
        latest = self.latest

        async def gen():
            if latest is not None:
                yield latest
        return gen()

    def get_partial_message(self, mid):
        return FakeMessage(self, mid)


def panel(**kw):
    base = {'author': '▶ Now playing', 'title': 'Song', 'url': '', 'description': 'bar', 'fields': [('Artist', 'A')],
            'footer': 'f', 'color': 0x123456, 'has_cover': False, 'buttons': True}
    base.update(kw)
    return base


class LinkPanelTest(unittest.TestCase):
    def setUp(self):
        self.lt = LoopThread()
        self.link = DiscordLink('token', guild_id=1)
        self.link._loop = self.lt.loop
        self.link.announce_channel_id = 500
        self.channel = FakeChannel(500)
        self.guild = types.SimpleNamespace(me=object(), voice_client=None)
        self.patches = [mock.patch.object(self.link, '_guild', return_value=self.guild),
                        mock.patch.object(self.link._client, 'get_channel',
                                          side_effect=lambda cid: self.channel if cid == 500 else None)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.lt.stop()

    def test_first_show_sends_with_cover(self):
        self.assertTrue(self.link.panel_show(panel(cover=tiny_jpeg(), has_cover=True), new_track=True))
        sent = self.channel.sent[0]
        self.assertEqual(sent['file'].filename, 'cover.jpg')
        self.assertEqual(sent['embed'].thumbnail.url, 'attachment://cover.jpg')
        self.assertEqual(sent['embed'].title, 'Song')
        self.assertEqual(self.link.panel_ref, (500, 1000))

    def test_progress_edits_in_place_and_keeps_the_cover(self):
        self.link.panel_show(panel(cover=tiny_jpeg(), has_cover=True), new_track=True)
        msg = self.link._panel_msg
        self.link.panel_show(panel(has_cover=True, description='later'))
        self.assertEqual(len(self.channel.sent), 1)
        edit = msg.edits[-1]
        self.assertNotIn('attachments', edit)               # 没换封面:不重传,附件保留
        self.assertEqual(edit['embed'].description, 'later')
        self.assertEqual(edit['embed'].thumbnail.url, 'attachment://cover.jpg')

    def test_new_track_edits_if_latest_else_reposts(self):
        self.link.panel_show(panel(), new_track=True)
        first = self.link._panel_msg
        self.link.panel_show(panel(title='Next', cover=None), new_track=True)
        self.assertEqual(len(self.channel.sent), 1)         # 面板还是最新一条:原地改
        self.assertEqual(first.edits[-1]['attachments'], [])
        self.channel.latest = FakeMessage(self.channel, 5)  # 有人聊天,面板被顶上去了
        self.link.panel_show(panel(title='Third'), new_track=True)
        self.assertTrue(first.deleted)
        self.assertEqual(len(self.channel.sent), 2)
        self.assertEqual(self.channel.sent[1]['embed'].title, 'Third')

    def test_deleted_panel_is_reposted_with_cached_cover(self):
        self.link.panel_show(panel(cover=tiny_jpeg(), has_cover=True), new_track=True)
        self.link._panel_msg.missing = True
        self.assertTrue(self.link.panel_show(panel(has_cover=True)))
        self.assertEqual(len(self.channel.sent), 2)
        self.assertIn('file', self.channel.sent[1])

    def test_no_attach_permission_sends_without_cover(self):
        self.channel.perms.attach_files = False
        self.link.panel_show(panel(cover=tiny_jpeg(), has_cover=True), new_track=True)
        sent = self.channel.sent[0]
        self.assertNotIn('file', sent)
        self.assertIsNone(sent['embed'].thumbnail.url)

    def test_web_playback_uses_panel_channel_then_system_channel(self):
        # 网页点歌:没有配置公告频道、也没有"最近发命令的频道"。语音频道自带的文字区排在最后
        voice_chat = FakeChannel(3)
        self.link.announce_channel_id = None
        self.link._users = {99: User(session=99, name='bot', channel_id=3)}
        self.link._me_id = 99
        self.guild.system_channel = self.channel
        channels = {500: self.channel, 3: voice_chat}
        with mock.patch.object(self.link._client, 'get_channel', side_effect=channels.get):
            self.link.panel_show(panel(), new_track=True)
            self.assertEqual((len(self.channel.sent), voice_chat.sent), (1, []))
            self.guild.system_channel = None                # 系统频道没了:面板留在原来的频道
            self.channel.latest = FakeMessage(self.channel, 5)
            self.link.panel_show(panel(title='Next'), new_track=True)
            self.assertEqual((len(self.channel.sent), voice_chat.sent), (2, []))
            self.link._panel_msg = None                     # 什么都没有了才用语音频道的文字区
            self.link.panel_show(panel(title='Last'), new_track=True)
            self.assertEqual(len(voice_chat.sent), 1)

    def test_no_embed_permission_means_no_panel(self):
        self.channel.perms.embed_links = False
        self.assertFalse(self.link.panel_show(panel(), new_track=True))
        self.assertEqual(self.channel.sent, [])

    def test_end_and_adopt(self):
        self.link.panel_adopt(500, 77)
        self.assertTrue(self.link.panel_end(None))
        msg = self.link._panel_msg
        self.assertEqual((msg.id, msg.edits), (77, [{'view': None}]))
        self.link.panel_end(panel(buttons=False, description='done'))
        self.assertIsNone(msg.edits[-1]['view'])
        self.assertEqual(msg.edits[-1]['embed'].description, 'done')

    def test_button_runs_the_command_silently(self):
        from commands.slash import Opt, Spec, _d
        from tests.test_discord_link import fake_interaction
        spec = Spec('mode', 'mode', lambda *a: None, _d('x', 'x', 'x'),
                    options=(Opt('mode', _d('m', 'm', 'm'), kind='choice',
                                 choices=('one-shot', 'repeat', 'single', 'random', 'autoplay')),))
        self.link._spec_by_key = {'mode': ('mode', spec)}
        self.link.on_panel_button = lambda action: ('mode', {'mode': 'repeat'})
        got, pokes = [], []
        self.link.on_command = got.append
        self.link.on_panel_pressed = lambda: pokes.append(1)
        self.link.on_precheck = lambda ctx: None
        self.link._emit = lambda fn, ctx: fn(ctx)
        click = fake_interaction(guild_id=1)
        asyncio.run_coroutine_threadsafe(self.link._on_panel_button(click, 'mode'), self.lt.loop).result(2)

        click.response.defer.assert_awaited_once_with()    # "稍后更新这条消息":不产生新消息
        ctx = got[0]
        self.assertEqual((ctx.command, ctx.argument, ctx.silent), ('mode', 'repeat', True))
        self.assertEqual(pokes, [1])
        self.assertIsNone(self.link._last_command_channel)  # 按钮不改变公告频道
        with mock.patch.object(dl, 'FINISH_GRACE', 0.01):
            self.link.reply(ctx, 'Mevius changed the mode to repeat')
            self.link.finish(ctx)
            time.sleep(0.1)
        click.edit_original_response.assert_not_called()   # 原始消息就是面板,不能被回复覆盖
        click.followup.send.assert_not_called()
        click.delete_original_response.assert_not_called()  # 更不能把面板删了

    def test_button_refusal_is_still_explained(self):
        from commands.slash import Spec, _d
        from tests.test_discord_link import fake_interaction
        spec = Spec('skip', 'skip', lambda *a: None, _d('x', 'x', 'x'))
        self.link._spec_by_key = {'skip': ('skip', spec)}
        self.link.on_panel_button = lambda action: ('skip', {})
        self.link.on_precheck = lambda ctx: "You're not in my voice channel!"
        click = fake_interaction(guild_id=1)
        asyncio.run_coroutine_threadsafe(self.link._on_panel_button(click, 'skip'), self.lt.loop).result(2)
        click.response.send_message.assert_awaited_once_with("You're not in my voice channel!", ephemeral=True)
        click.response.defer.assert_not_called()

    def test_voice_status_needs_permission_and_is_cleared_on_leave(self):
        voice = FakeChannel(3)
        voice.name = 'Lounge'
        self.guild.voice_client = types.SimpleNamespace(channel=voice, is_connected=lambda: True,
                                                        disconnect=mock.AsyncMock())
        calls = []

        async def edit_status(status, channel_id):
            calls.append((status, channel_id))
        with mock.patch.object(self.link._client.http, 'edit_voice_channel_status', side_effect=edit_status):
            self.assertTrue(self.link.set_voice_status('🎵 Song'))
            self.link.leave_voice()
            self.assertEqual(calls, [('🎵 Song', 3), (None, 3)])

            voice.perms.set_voice_channel_status = False
            self.guild.voice_client = types.SimpleNamespace(channel=voice, is_connected=lambda: True)
            self.assertFalse(self.link.set_voice_status('🎵 Song'))
            self.assertFalse(self.link.set_voice_status('🎵 Other'))
            self.assertEqual(len(calls), 2)
            self.assertTrue(self.link._voice_status_warned)


if __name__ == '__main__':
    unittest.main()
