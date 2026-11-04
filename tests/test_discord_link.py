# coding=utf-8
"""DiscordLink:音频推拉转换、斜杠命令生成、回复流程。不连真实的 Discord。"""
import asyncio
import os
import struct
import sys
import threading
import time
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import discord  # noqa: E402

from bot import discord_link as dl  # noqa: E402
from bot.discord_link import CommandContext, DiscordLink, PCMStream  # noqa: E402


def pcm(value, frames=1):
    """frames 个 20 ms 的立体声帧,每个采样都是 value。"""
    samples = dl.FRAME_BYTES // 2 * frames
    return struct.pack(f'<{samples}h', *([value] * samples))


def samples(data):
    return struct.unpack(f'<{len(data) // 2}h', data)


class PCMStreamTest(unittest.TestCase):
    def test_frames_padding_and_idle_stop(self):
        s = PCMStream(capacity=0.5)
        started = []
        s.set_sink(lambda: started.append(1))
        self.assertTrue(s.write(pcm(100)))
        self.assertEqual(started, [1])          # 有数据就请求开播
        s.write(pcm(100)[:100])                 # 不足一帧的尾巴
        self.assertEqual(samples(s.read())[0], 100)
        tail = s.read()
        self.assertEqual(len(tail), dl.FRAME_BYTES)  # 补零成整帧
        self.assertEqual(samples(tail)[0], 100)
        self.assertEqual(samples(tail)[-1], 0)
        # 空了先送静音,超过 IDLE_SILENCE_FRAMES 帧后停(返回 b'')
        for _ in range(dl.IDLE_SILENCE_FRAMES):
            self.assertEqual(s.read(), dl.SILENCE)
        self.assertEqual(s.read(), b'')
        self.assertFalse(s.playing)
        s.write(pcm(1))
        self.assertEqual(started, [1, 1])       # 再有数据时重新开播

    def test_write_blocks_until_read(self):
        s = PCMStream(capacity=0.04)  # 两帧
        s.set_sink(lambda: None)
        s.write(pcm(1, 2))
        done = threading.Event()
        threading.Thread(target=lambda: (s.write(pcm(2)), done.set()), daemon=True).start()
        self.assertFalse(done.wait(0.1))        # 满了:阻塞
        s.read()
        self.assertTrue(done.wait(1))
        self.assertAlmostEqual(s.buffered, 0.04, places=3)

    def test_no_voice_drops_at_real_time(self):
        s = PCMStream()
        started = time.time()
        for _ in range(5):
            self.assertTrue(s.write(pcm(1)))
        self.assertGreaterEqual(time.time() - started, 0.09)  # 5 帧 ≈ 100 ms
        self.assertEqual(s.buffered, 0)

    def test_disconnect_clears_and_close_unblocks(self):
        s = PCMStream(capacity=0.02)
        s.set_sink(lambda: None)
        s.write(pcm(1))
        s.set_sink(None)
        self.assertEqual(s.buffered, 0)
        s.set_sink(lambda: None)
        s.write(pcm(1))
        result = []
        t = threading.Thread(target=lambda: result.append(s.write(pcm(1))), daemon=True)
        t.start()
        time.sleep(0.05)
        s.close()
        t.join(1)
        self.assertEqual(result, [False])

    def test_gain_ramps_within_a_frame(self):
        s = PCMStream()
        s.set_sink(lambda: None)
        s.write(pcm(10000, 3))
        s.set_gain(0.0)
        ramp = samples(s.read())
        self.assertGreater(ramp[0], 0)          # 这一帧从 1.0 渐变到 0
        self.assertEqual(ramp[-1], 0)
        self.assertTrue(all(a >= b for a, b in zip(ramp[::480], ramp[480::480])))
        self.assertEqual(set(samples(s.read())), {0})
        s.set_gain(0.5)
        s.read()
        self.assertEqual(set(samples(s.read())), {0})  # 缓冲用完了是静音帧
        s.write(pcm(10000))
        self.assertEqual(set(samples(s.read())), {5000})


class OpusTest(unittest.TestCase):
    def test_frames_encode_with_discord_opus(self):
        # read() 的帧大小必须正好是 discord.py 编码器要的 20 ms 立体声
        if not (discord.opus.is_loaded() or discord.opus._load_default()):
            self.skipTest('libopus not installed')
        s = PCMStream()
        s.set_sink(lambda: None)
        s.write(pcm(3000, 2))
        encoder = discord.opus.Encoder()
        packet = encoder.encode(s.read(), encoder.SAMPLES_PER_FRAME)
        self.assertGreater(len(packet), 0)
        self.assertEqual(dl.FRAME_BYTES, encoder.FRAME_SIZE)


class LoopThread:
    """在后台线程跑一个事件循环,模拟 discord.py 的线程。"""

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join(2)


def fake_interaction(user_id=42, guild_id=1, channel_id=500, voice_channel=None, admin=False, roles=()):
    perms = types.SimpleNamespace(administrator=admin, manage_guild=False)
    voice = types.SimpleNamespace(channel=types.SimpleNamespace(id=voice_channel)) if voice_channel else None
    member = types.SimpleNamespace(id=user_id, name='aiden', display_name='Aiden', voice=voice,
                                   roles=[types.SimpleNamespace(id=r) for r in roles], guild_permissions=perms)
    interaction = mock.MagicMock()
    interaction.user = member
    interaction.guild_id = guild_id
    interaction.channel_id = channel_id
    interaction.response.defer = mock.AsyncMock()
    interaction.response.send_message = mock.AsyncMock()
    interaction.edit_original_response = mock.AsyncMock()
    interaction.delete_original_response = mock.AsyncMock()
    interaction.followup.send = mock.AsyncMock()
    return interaction


class LinkTest(unittest.TestCase):
    def setUp(self):
        self.lt = LoopThread()
        self.link = DiscordLink('token', guild_id=1, admin_ids=['7'])
        self.link._loop = self.lt.loop

    def tearDown(self):
        self.lt.stop()

    def run_coro(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.lt.loop).result(2)

    def ctx(self, interaction=None, ephemeral=False):
        return CommandContext(actor=42, name='Aiden', username='aiden', command='play', argument='',
                              interaction=interaction or fake_interaction(), ephemeral=ephemeral,
                              channel_id=500)

    def test_first_reply_edits_thinking_then_followups(self):
        ctx = self.ctx()
        self.link.reply(ctx, '<b>one</b>')
        self.link.reply(ctx, 'two')
        self.link.reply(ctx, 'secret', ephemeral=True)
        ctx.interaction.edit_original_response.assert_awaited_once_with(content='**one**')
        sends = ctx.interaction.followup.send.await_args_list
        self.assertEqual([(c.args[0], c.kwargs['ephemeral']) for c in sends], [('two', False), ('secret', True)])

    def test_long_reply_is_split(self):
        ctx = self.ctx()
        self.link.reply(ctx, '<br>'.join(['x' * 150] * 30))
        self.assertEqual(ctx.interaction.edit_original_response.await_count, 1)
        self.assertGreaterEqual(ctx.interaction.followup.send.await_count, 1)
        for call in ctx.interaction.followup.send.await_args_list:
            self.assertLessEqual(len(call.args[0]), 2000)

    def test_expired_interaction_falls_back_to_channel(self):
        ctx = self.ctx()
        ctx.created_at -= dl.INTERACTION_TTL + 1
        channel = mock.MagicMock()
        channel.send = mock.AsyncMock()
        with mock.patch.object(self.link._client, 'get_channel', return_value=channel):
            self.link.reply(ctx, 'late')
        channel.send.assert_awaited_once()
        ctx.interaction.edit_original_response.assert_not_called()

    def test_finish_deletes_thinking_only_if_nothing_was_sent(self):
        with mock.patch.object(dl, 'FINISH_GRACE', 0.05):
            quiet = self.ctx()
            self.link.finish(quiet)
            answered = self.ctx()
            self.link.reply(answered, 'ok')
            self.link.finish(answered)
            late = self.ctx()
            self.link.finish(late)
            time.sleep(0.01)
            self.link.reply(late, 'background thread reply')  # 宽限期内的回复直接用上
            time.sleep(0.2)
        quiet.interaction.delete_original_response.assert_awaited_once()
        answered.interaction.delete_original_response.assert_not_called()
        late.interaction.delete_original_response.assert_not_called()
        late.interaction.edit_original_response.assert_awaited_once()

    def test_announcement_channel_priority(self):
        sent = []

        class Ch:
            def __init__(self, cid):
                self.cid = cid

            async def send(self, content, **kw):
                sent.append((self.cid, content))

        channels = {500: Ch(500), 900: Ch(900)}
        with mock.patch.object(self.link._client, 'get_channel', side_effect=channels.get):
            self.link.send_announcement('a')            # 没有可发的频道:丢掉
            self.link._last_command_channel = 500
            self.link.send_announcement('b')
            self.link.announce_channel_id = 900
            self.link.send_announcement('c')
        self.assertEqual(sent, [(500, 'b'), (900, 'c')])

    def test_context_admin_and_options(self):
        from commands.slash import Opt, Spec, _d
        spec = Spec('user_ban', 'userban', lambda *a: None, _d('x', 'x', 'x'),
                    options=(Opt('user', _d('u', 'u', 'u'), kind='user'),
                             Opt('flag', _d('f', 'f', 'f'), kind='bool'),
                             Opt('n', _d('n', 'n', 'n'), kind='int')))
        target = types.SimpleNamespace(id=99, name='mallory', display_name='Mal')
        ctx = self.link._context(spec, fake_interaction(voice_channel=3), {'user': target, 'flag': True, 'n': 5})
        self.assertEqual(ctx.argument, '99 flag 5')
        self.assertEqual(ctx.options['user_name'], 'Mal')
        self.assertEqual(ctx.voice_channel_id, 3)
        self.assertFalse(ctx.is_admin)
        self.assertTrue(self.link._context(spec, fake_interaction(user_id=7), {}).is_admin)      # 配置的用户 ID
        self.assertTrue(self.link._context(spec, fake_interaction(roles=(7,)), {}).is_admin)     # 配置的身份组 ID
        self.assertTrue(self.link._context(spec, fake_interaction(admin=True), {}).is_admin)     # 服务器管理员
        self.link.admin_permission = False
        self.assertFalse(self.link._context(spec, fake_interaction(admin=True), {}).is_admin)

    def test_invoke_precheck_defer_and_dispatch(self):
        from commands.slash import Spec, _d
        spec = Spec('play', 'play', lambda *a: None, _d('x', 'x', 'x'))
        got = []
        self.link.on_command = got.append
        self.link._dispatcher = threading.Thread(target=self.link._dispatch, daemon=True)
        self.link._dispatcher.start()

        other_guild = fake_interaction(guild_id=2)
        self.run_coro(self.link._invoke(spec, other_guild, {}))
        other_guild.response.send_message.assert_awaited_once()
        self.assertTrue(other_guild.response.send_message.await_args.kwargs['ephemeral'])

        self.link.on_precheck = lambda ctx: '<b>no</b>'
        refused = fake_interaction()
        self.run_coro(self.link._invoke(spec, refused, {}))
        refused.response.send_message.assert_awaited_once_with('**no**', ephemeral=True)
        refused.response.defer.assert_not_called()

        self.link.on_precheck = lambda ctx: None
        ok = fake_interaction(channel_id=777)
        self.run_coro(self.link._invoke(spec, ok, {}))
        ok.response.defer.assert_awaited_once_with(ephemeral=False, thinking=True)
        time.sleep(0.05)
        self.assertEqual([c.command for c in got], ['play'])
        self.assertEqual(self.link._last_command_channel, 777)
        self.link._events.put(None)


class CommandTreeTest(unittest.TestCase):
    def test_every_spec_builds_with_localizations(self):
        import configparser
        from commands import slash
        link = DiscordLink('token', guild_id=1, language='zh_CN')
        config = configparser.ConfigParser(interpolation=None)
        link.register_commands(slash.configured_specs(config))
        commands = {c.name: c for c in link._tree.get_commands()}
        self.assertEqual(len(commands), len(slash.specs()))

        async def payload(name):
            return await commands[name].get_translated_payload(link._tree, dl._Translator())

        data = asyncio.run(payload('volume'))
        self.assertEqual(data['description'], '查看或设置音量')  # 默认语言跟 bot 的语言
        self.assertEqual(data['description_localizations']['en-US'], 'Show or set the volume')
        self.assertEqual(data['description_localizations']['ja'], '音量を表示・設定')
        option = data['options'][0]
        self.assertEqual((option['type'], option['min_value'], option['max_value']), (4, 0, 100))
        self.assertFalse(data['dm_permission'])

        mode = asyncio.run(payload('mode'))['options'][0]
        self.assertEqual([c['value'] for c in mode['choices']],
                         ['one-shot', 'repeat', 'random', 'autoplay', 'single'])
        play = asyncio.run(payload('play'))['options'][0]
        self.assertTrue(play['autocomplete'])
        ban = asyncio.run(payload('userban'))['options'][0]
        self.assertEqual(ban['type'], discord.AppCommandOptionType.user.value)

    def test_callback_passes_option_values(self):
        from commands.slash import Opt, Spec, _d
        link = DiscordLink('token', guild_id=1)
        seen = {}

        async def fake_invoke(spec, interaction, kwargs):
            seen.update(kwargs)

        link._invoke = fake_invoke
        spec = Spec('play', 'play', lambda *a: None, _d('x', 'x', 'x'),
                    options=(Opt('query', _d('q', 'q', 'q'), required=True), Opt('start', _d('s', 's', 's'))))
        command = link._build_command('play', spec)
        asyncio.run(command.callback(mock.MagicMock(), query='lofi', start=None))
        self.assertEqual(seen, {'query': 'lofi', 'start': None})
        self.assertEqual([p.name for p in command.parameters], ['query', 'start'])
        self.assertTrue(command.parameters[0].required)


if __name__ == '__main__':
    unittest.main()
