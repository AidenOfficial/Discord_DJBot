# coding=utf-8
"""DiscordClient / GuildLink:音频推拉转换、斜杠命令生成、回复流程、按服务器路由。不连真实的 Discord。"""
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
from bot.discord_link import CommandContext, DiscordClient, GuildLink, PCMStream  # noqa: E402


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


def make_link(guild_id=1, loop=None, home_guild_id=None, **kw):
    """(DiscordClient, GuildLink):不连 Discord,link 直接登记到 client 上。"""
    client = DiscordClient('token', home_guild_id=home_guild_id or guild_id)
    if loop is not None:
        client._loop = loop
    link = GuildLink(client, guild_id, **kw)
    client._links[link.guild_id] = link
    return client, link


def wait_for(predicate, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


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
        self.client, self.link = make_link(1, self.lt.loop, admin_ids=['7'])

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
        channel.guild = types.SimpleNamespace(id=1)
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
            def __init__(self, cid, guild=1):
                self.cid = cid
                self.guild = types.SimpleNamespace(id=guild)

            async def send(self, content, **kw):
                sent.append((self.cid, content))

        channels = {500: Ch(500), 900: Ch(900), 901: Ch(901, guild=2)}
        with mock.patch.object(self.link._client, 'get_channel', side_effect=channels.get):
            self.link.send_announcement('a')            # 没有可发的频道:丢掉
            self.link._last_command_channel = 500
            self.link.send_announcement('b')
            self.link.announce_channel_id = 900
            self.link.send_announcement('c')
            self.link.announce_channel_id = 901         # 别的服务器的频道:不认,退回最近发命令的频道
            self.link.send_announcement('d')
        self.assertEqual(sent, [(500, 'b'), (900, 'c'), (500, 'd')])

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
        # bot 主人只有配置的用户 ID;服务器管理员、配置的身份组都不是主人
        self.assertTrue(self.link._context(spec, fake_interaction(user_id=7), {}).is_owner)
        self.assertFalse(self.link._context(spec, fake_interaction(roles=(7,)), {}).is_owner)
        self.assertFalse(self.link._context(spec, fake_interaction(admin=True), {}).is_owner)
        self.link.admin_permission = False
        self.assertFalse(self.link._context(spec, fake_interaction(admin=True), {}).is_admin)

    def test_invoke_precheck_defer_and_dispatch(self):
        from commands.slash import Spec, _d
        spec = Spec('play', 'play', lambda *a: None, _d('x', 'x', 'x'))
        got = []
        self.link.on_command = got.append

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
        self.assertTrue(wait_for(lambda: got))          # 回调在共享线程池里执行
        self.assertEqual([c.command for c in got], ['play'])
        self.assertEqual(self.link._last_command_channel, 777)


class CommandTreeTest(unittest.TestCase):
    def test_every_spec_builds_with_localizations(self):
        import configparser
        from commands import slash
        link = DiscordClient('token', home_guild_id=1, language='zh_CN')
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

    def test_default_permissions_and_owner_guild_split(self):
        named = all_specs()
        client = DiscordClient('token', home_guild_id=1)
        client.register_commands(named, owner_guild_id=999)
        owner_guild = discord.Object(id=999)
        global_names = {c.name for c in client._tree.get_commands()}
        owner_names = {c.name for c in client._tree.get_commands(guild=owner_guild)}
        owner_specs = {name for name, spec in named if spec.owner_only}
        self.assertIn('kill', owner_specs)
        self.assertEqual(owner_names, owner_specs)                 # 主人命令只在主人的服务器
        self.assertFalse(global_names & owner_specs)
        self.assertEqual(global_names | owner_names, {name for name, _ in named})

        commands = {c.name: c for c in client._tree.get_commands()}
        manage = discord.Permissions(manage_guild=True)
        for name, spec in named:
            if spec.admin:
                self.assertEqual(commands[name].default_permissions, manage, name)
            elif not spec.owner_only:
                self.assertIsNone(commands[name].default_permissions, name)
        self.assertTrue(client._tree.get_command('kill', guild=owner_guild).default_permissions.administrator)
        data = asyncio.run(commands['userban'].get_translated_payload(client._tree, dl._Translator()))
        self.assertEqual(int(data['default_member_permissions']), manage.value)

    def test_without_owner_guild_owner_commands_are_global_but_hidden(self):
        named = all_specs()
        client = DiscordClient('token', home_guild_id=1)
        client.register_commands(named)
        self.assertEqual(len(client._tree.get_commands()), len(named))
        kill = client._tree.get_command('kill')
        self.assertEqual(kill.default_permissions, discord.Permissions(administrator=True))

    def test_dev_guild_gets_every_command(self):
        named = all_specs()
        client = DiscordClient('token', home_guild_id=1)
        client.register_commands(named, owner_guild_id=999, dev_guild_id=888)
        self.assertEqual({c.name for c in client._tree.get_commands(guild=discord.Object(id=888))},
                         {name for name, spec in named if not spec.owner_only})
        # 全局、主人的服务器、开发服务器,再加以前的主服务器(清掉旧的服务器命令)
        self.assertEqual(client._sync_targets(), [None, 999, 888, 1])

    def test_callback_passes_option_values(self):
        from commands.slash import Opt, Spec, _d
        link = DiscordClient('token', home_guild_id=1)
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


def all_specs(renames=None):
    import configparser
    from commands import slash
    config = configparser.ConfigParser(interpolation=None)
    if renames:
        config.read_dict({'commands': renames})
    return slash.configured_specs(config)


class FakeSyncState:
    """SettingsDatabase 的 get / set。"""

    def __init__(self):
        self.data = {}

    def get(self, section, option, fallback=None):
        return self.data.get((section, option), fallback)

    def set(self, section, option, value):
        self.data[(section, option)] = value


class CommandSyncTest(unittest.TestCase):
    def make(self, state, named=None, home=None, remote=(), **kw):
        """remote:Discord 上现有的全局命令(get_global_commands 的返回)。"""
        client = DiscordClient('token', home_guild_id=home)
        client.register_commands(named or all_specs(), sync_state=state, **kw)
        client.client._connection.application_id = 777
        client._tree.sync = mock.AsyncMock(return_value=[])
        client.client.http.get_global_commands = mock.AsyncMock(return_value=[dict(c) for c in remote])
        client.client.http.bulk_upsert_global_commands = mock.AsyncMock(
            side_effect=lambda app_id, payload: list(payload))
        return client

    @staticmethod
    def synced(client):
        """同步到了哪些地方(None = 全局),按调用顺序。"""
        targets = [None] * client.client.http.bulk_upsert_global_commands.await_count
        return targets + [c.kwargs['guild'].id for c in client._tree.sync.await_args_list]

    @staticmethod
    def global_payload(client):
        call = client.client.http.bulk_upsert_global_commands.await_args
        assert call.args[0] == 777
        return call.kwargs['payload']

    def test_sync_only_when_the_commands_changed(self):
        state = FakeSyncState()
        first = self.make(state, owner_guild_id=999)
        asyncio.run(first._sync_commands())
        self.assertEqual(self.synced(first), [None, 999])

        again = self.make(state, owner_guild_id=999)              # 重启,命令没变:不调用 Discord
        asyncio.run(again._sync_commands())
        again._tree.sync.assert_not_awaited()

        renamed = self.make(state, all_specs({'play': 'p'}), owner_guild_id=999)
        asyncio.run(renamed._sync_commands())
        self.assertEqual(self.synced(renamed), [None])             # 只有全局那份变了

    def test_failed_sync_is_retried_on_next_start(self):
        state = FakeSyncState()
        client = self.make(state)
        client.client.http.bulk_upsert_global_commands = mock.AsyncMock(side_effect=RuntimeError('429'))
        asyncio.run(client._sync_commands())
        self.assertEqual(state.data, {})
        retry = self.make(state)
        asyncio.run(retry._sync_commands())
        self.assertEqual(self.synced(retry), [None])

    def test_old_home_guild_commands_are_cleared_once(self):
        state = FakeSyncState()
        client = self.make(state, home=5)
        asyncio.run(client._sync_commands())
        self.assertEqual(self.synced(client), [None, 5])
        self.assertEqual(client._tree.get_commands(guild=discord.Object(id=5)), [])  # 同步一份空的过去
        again = self.make(state, home=5)
        asyncio.run(again._sync_commands())
        again._tree.sync.assert_not_awaited()

    # ---- Activity 的入口命令(PRIMARY_ENTRY_POINT,type 4)-------------------------

    ENTRY = {'id': '1', 'application_id': '777', 'version': '9', 'name': 'launch', 'type': 4,
             'handler': 2, 'description': 'Launch the panel', 'integration_types': [0, 1],
             'contexts': [0, 1, 2], 'name_localizations': None, 'default_member_permissions': None}

    def test_global_sync_keeps_the_entry_point_command(self):
        # Discord 上已经有入口命令(开 Activity 时 Portal 自动建的):整体覆盖时原样带上,不然会被删 / 被拒
        remote = [{'id': '2', 'name': 'play', 'type': 1, 'description': 'old'}, self.ENTRY]
        client = self.make(FakeSyncState(), remote=remote)
        asyncio.run(client._sync_commands())
        payload = self.global_payload(client)
        entries = [p for p in payload if p.get('type') == dl.ENTRY_POINT_TYPE]
        self.assertEqual(entries, [{'name': 'launch', 'type': 4, 'handler': 2, 'description': 'Launch the panel',
                                    'integration_types': [0, 1], 'contexts': [0, 1, 2]}])
        # 其余是我们自己的斜杠命令,旧的 play 被新的替换,不重复
        self.assertEqual(sum(1 for p in payload if p['name'] == 'play'), 1)
        self.assertGreater(len(payload), 10)

    def test_entry_point_kept_even_with_activity_disabled(self):
        client = self.make(FakeSyncState(), remote=[self.ENTRY], entry_point=False)
        asyncio.run(client._sync_commands())
        self.assertEqual(sum(1 for p in self.global_payload(client) if p.get('type') == 4), 1)

    def test_default_entry_point_registered_when_activity_enabled(self):
        client = self.make(FakeSyncState(), remote=[], entry_point=True)
        asyncio.run(client._sync_commands())
        entries = [p for p in self.global_payload(client) if p.get('type') == 4]
        self.assertEqual(entries, [dl.default_entry_point()])
        self.assertEqual(entries[0]['handler'], dl.ENTRY_POINT_HANDLER_DISCORD)

    def test_no_entry_point_without_activity(self):
        client = self.make(FakeSyncState(), remote=[])
        asyncio.run(client._sync_commands())
        self.assertFalse(any(p.get('type') == 4 for p in self.global_payload(client)))

    def test_turning_activity_on_triggers_a_resync(self):
        state = FakeSyncState()
        asyncio.run(self.make(state)._sync_commands())
        enabled = self.make(state, entry_point=True)
        asyncio.run(enabled._sync_commands())
        self.assertEqual(self.synced(enabled), [None])
        again = self.make(state, entry_point=True)
        asyncio.run(again._sync_commands())
        self.assertEqual(self.synced(again), [])

    def test_guild_sync_never_carries_the_entry_point(self):
        # 入口命令只能是全局的;开发服务器那份照旧走 discord.py 的 sync
        client = self.make(FakeSyncState(), remote=[self.ENTRY], dev_guild_id=888)
        asyncio.run(client._sync_commands())
        self.assertEqual(self.synced(client), [None, 888])
        client._tree.sync.assert_awaited_once()


class FakeVoiceClient:
    def __init__(self, connected=True, playing=False, player_alive=True, source=None, play_error=None):
        self._connected = connected
        self._playing = playing
        self._player = types.SimpleNamespace(is_alive=lambda: player_alive) if playing else None
        self.source = source
        self.channel = types.SimpleNamespace(bitrate=8000)
        self.play_error = play_error
        self.plays = []
        self.stops = 0

    def is_connected(self):
        return self._connected

    def is_playing(self):
        return self._playing

    def stop(self):
        self.stops += 1
        self._playing = False
        self._player = None

    def play(self, source, **kw):
        if self.play_error is not None:
            raise self.play_error
        self.plays.append(kw)
        self._playing = True


class PlayerRecoveryTest(unittest.TestCase):
    """语音重连 / 网关重连 / 编码器出错后,播放不能卡死(播放线程会一直卡在写缓冲上)。"""

    def setUp(self):
        self.lt = LoopThread()
        self.client, self.link = make_link(1, self.lt.loop)
        self.vc = None
        self.link._guild = lambda: types.SimpleNamespace(voice_client=self.vc)
        self.link._pcm.set_sink(lambda: None)
        self.link._pcm.write(pcm(1))
        self.link._pcm._playing = True

    def tearDown(self):
        self.lt.stop()

    def start(self):
        self.lt.loop.call_soon_threadsafe(self.link._start_player, 0)
        time.sleep(0.1)

    def test_dead_player_is_replaced(self):
        # AudioPlayer 等语音重连超时后直接 return,不调 stop():is_playing() 仍是 True
        self.vc = FakeVoiceClient(playing=True, player_alive=False, source=self.link._pcm)
        self.start()
        self.assertEqual(self.vc.stops, 1)
        self.assertEqual(len(self.vc.plays), 1)
        self.assertEqual(self.vc.plays[0]['bitrate'], 16)  # 频道 8 kbps:夹到 Opus 的下限

    def test_play_error_does_not_wedge(self):
        self.vc = FakeVoiceClient(play_error=discord.opus.OpusNotLoaded())
        self.start()
        self.assertFalse(self.link._pcm.playing)

    def test_no_voice_client_disconnects_the_sink(self):
        self.vc = None
        self.start()
        self.assertIsNone(self.link._pcm._sink)
        self.assertEqual(self.link._pcm.buffered, 0)

    def test_after_callback_clears_a_dead_player(self):
        self.vc = FakeVoiceClient(playing=True, player_alive=False, source=self.link._pcm)
        self.link._player_after(None)
        time.sleep(0.1)
        self.assertGreaterEqual(self.vc.stops, 1)


class ReplyEdgeCaseTest(LinkTest):
    def test_late_reply_after_thinking_was_dropped_uses_followup(self):
        ctx = self.ctx()
        with mock.patch.object(dl, 'FINISH_GRACE', 0.01):
            self.link.finish(ctx)
            time.sleep(0.15)
        ctx.interaction.delete_original_response.assert_awaited_once()
        self.link.reply(ctx, 'lyrics, ten seconds later')
        ctx.interaction.edit_original_response.assert_not_called()
        ctx.interaction.followup.send.assert_awaited_once()

    def test_edit_not_found_falls_back_to_followup(self):
        ctx = self.ctx()
        response = types.SimpleNamespace(status=404, reason='Not Found')
        ctx.interaction.edit_original_response.side_effect = discord.NotFound(response, 'Unknown Message')
        self.link.reply(ctx, 'hello')
        ctx.interaction.followup.send.assert_awaited_once()

    def test_expired_private_reply_is_not_posted_publicly(self):
        ctx = self.ctx(ephemeral=True)
        ctx.created_at -= dl.INTERACTION_TTL + 1
        channel = mock.MagicMock()
        channel.send = mock.AsyncMock()
        with mock.patch.object(self.link._client, 'get_channel', return_value=channel):
            self.link.reply(ctx, 'https://web/?token=secret')
        channel.send.assert_not_called()

    def test_announcement_skips_channels_without_permission(self):
        sent = []
        allowed = types.SimpleNamespace(view_channel=True, send_messages=True)
        denied = types.SimpleNamespace(view_channel=True, send_messages=False)

        class Ch:
            def __init__(self, cid, perms, forbidden=False):
                self.cid, self.perms, self.forbidden = cid, perms, forbidden
                self.guild = types.SimpleNamespace(id=1)

            def permissions_for(self, member):
                return self.perms

            async def send(self, content, **kw):
                if self.forbidden:
                    raise discord.Forbidden(types.SimpleNamespace(status=403, reason='Forbidden'), 'no')
                sent.append(self.cid)

        channels = {1: Ch(1, allowed, forbidden=True), 500: Ch(500, denied), 3: Ch(3, allowed)}
        self.link.announce_channel_id = 1
        self.link._last_command_channel = 500
        self.link._users = {99: dl.User(session=99, name='bot', channel_id=3)}
        self.link._me_id = 99
        guild = types.SimpleNamespace(me=object(), voice_client=None)
        with mock.patch.object(self.link, '_guild', return_value=guild), \
                mock.patch.object(self.link._client, 'get_channel', side_effect=channels.get):
            self.link.send_announcement('now playing')
        self.assertEqual(sent, [3])  # 1 发不出去,500 没权限,落到语音频道的文字区

    def test_precheck_failure_refuses(self):
        from commands.slash import Spec, _d
        spec = Spec('kill', 'kill', lambda *a: None, _d('x', 'x', 'x'), admin=True)
        self.link.on_command = mock.Mock()

        def boom(ctx):
            raise RuntimeError('database is locked')

        self.link.on_precheck = boom
        interaction = fake_interaction()
        self.run_coro(self.link._invoke(spec, interaction, {}))
        interaction.response.send_message.assert_awaited_once()
        interaction.response.defer.assert_not_called()
        self.link.on_command.assert_not_called()


class VoiceStateDiffTest(unittest.TestCase):
    def test_changes_of_other_members_are_not_lost(self):
        # 两条语音状态事件挤在一起:第一个处理函数重建的快照里已经有第二个人的变化
        link = make_link(1)[1]
        link._me_id = 99
        events = []
        link.on_user_joined = lambda u: events.append(('joined', u.session))
        link.on_user_left = lambda u: events.append(('left', u.session))
        link.on_self_moved = lambda old, new: events.append(('self', old, new))
        link._emit = lambda fn, *args: fn(*args)
        link._users = {99: dl.User(session=99, name='bot', channel_id=5), 2: dl.User(session=2, name='b', channel_id=5)}
        after = {1: dl.User(session=1, name='a', channel_id=5)}

        def rebuild():
            link._users = after

        link._rebuild_users = rebuild
        link._on_self_voice = lambda cid: None
        member = types.SimpleNamespace(id=1, guild=types.SimpleNamespace(id=1))
        asyncio.run(link.on_voice_state_update(member, None, None))
        self.assertEqual(events[0], ('self', 5, None))  # bot 自己的变化先处理
        self.assertIn(('joined', 1), events)
        self.assertIn(('left', 2), events)


# =========================================================================
#   共享连接 -> 各服务器的 GuildLink
# =========================================================================

class FakeGuildLink:
    """DiscordClient 路由用到的那部分 GuildLink 接口,记下收到了什么。"""

    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.got = []
        self.on_autocomplete = lambda kind, ctx, current: [(f'{kind}@{guild_id}', current)]

    async def _invoke(self, spec, interaction, kwargs, ephemeral=None, silent=False):
        self.got.append(('invoke', spec, silent))

    async def _on_panel_button(self, interaction, action):
        self.got.append(('button', action))

    async def on_voice_state_update(self, member, before, after):
        self.got.append(('voice', member.id))

    def _rebuild(self):
        self.got.append(('rebuild',))

    def _after_ready(self):
        self.got.append(('ready',))

    def _context(self, spec, interaction, kwargs):
        return CommandContext(actor=interaction.user.id, name='x', username='x', command='', argument='',
                              guild_id=self.guild_id)


class RoutingTest(unittest.TestCase):
    def setUp(self):
        self.client = DiscordClient('token', home_guild_id=1)
        self.a, self.b = FakeGuildLink(1), FakeGuildLink(2)
        self.client._links = {1: self.a, 2: self.b}

    def test_interactions_go_to_their_guild(self):
        asyncio.run(self.client._invoke('spec', fake_interaction(guild_id=2), {}))
        asyncio.run(self.client._on_panel_button(fake_interaction(guild_id=1), 'skip'))
        self.assertEqual(self.a.got, [('button', 'skip')])
        self.assertEqual(self.b.got, [('invoke', 'spec', False)])

    def test_unknown_guilds_are_refused_politely(self):
        stranger = fake_interaction(guild_id=3)
        asyncio.run(self.client._invoke('spec', stranger, {}))
        stranger.response.send_message.assert_awaited_once_with(dl.HOME_ONLY_REPLY, ephemeral=True)
        del self.client._links[1]                       # 主服务器的会话还没建好
        early = fake_interaction(guild_id=1)
        asyncio.run(self.client._on_panel_button(early, 'skip'))
        early.response.send_message.assert_awaited_once_with(dl.STARTING_REPLY, ephemeral=True)
        dm = fake_interaction(guild_id=None)
        asyncio.run(self.client._invoke('spec', dm, {}))
        dm.response.send_message.assert_awaited_once_with(dl.HOME_ONLY_REPLY, ephemeral=True)

    def test_gateway_events_go_to_their_guild(self):
        guild = types.SimpleNamespace(id=2)
        asyncio.run(self.client.on_voice_state_update(types.SimpleNamespace(id=5, guild=guild), None, None))
        asyncio.run(self.client.on_guild_channel_update(None, types.SimpleNamespace(guild=guild)))
        asyncio.run(self.client.on_guild_role_delete(types.SimpleNamespace(guild=types.SimpleNamespace(id=9))))
        asyncio.run(self.client.on_guild_update(None, types.SimpleNamespace(id=1)))
        self.assertEqual(self.b.got, [('voice', 5), ('rebuild',)])
        self.assertEqual(self.a.got, [('rebuild',)])

    def test_reconnect_check_runs_for_every_guild(self):
        asyncio.run(self.client.on_shard_ready(0))
        self.assertEqual((self.a.got, self.b.got), ([('ready',)], [('ready',)]))

    def test_autocomplete_uses_the_guilds_handler(self):
        from commands.slash import Opt, _d
        opt = Opt('query', _d('q', 'q', 'q'), autocomplete='library')
        complete = self.client._make_autocomplete(opt)
        choices = asyncio.run(complete(fake_interaction(guild_id=2), 'lo'))
        self.assertEqual([(c.name, c.value) for c in choices], [('library@2', 'lo')])
        self.assertEqual(asyncio.run(complete(fake_interaction(guild_id=3), 'lo')), [])

    def test_unknown_guild_gets_a_session_first(self):
        asked = []

        def need(gid):
            asked.append(gid)
            # Hub 在线程池里建会话,过一会儿 GuildLink 才登记上
            threading.Timer(0.1, lambda: self.client._links.__setitem__(gid, FakeGuildLink(gid))).start()

        self.client.on_session_needed = need
        asyncio.run(self.client._invoke('spec', fake_interaction(guild_id=3), {}))
        self.assertEqual(asked, [3])
        self.assertEqual(self.client._links[3].got, [('invoke', 'spec', False)])
        asyncio.run(self.client._on_panel_button(fake_interaction(guild_id=3), 'stop'))
        self.assertEqual(asked, [3])                    # 已经有了:不再请求
        self.assertEqual(self.client._links[3].got[-1], ('button', 'stop'))

    def test_refused_or_slow_session(self):
        self.client.on_session_needed = lambda gid: 'Not here.'
        refused = fake_interaction(guild_id=3)
        asyncio.run(self.client._invoke('spec', refused, {}))
        refused.response.send_message.assert_awaited_once_with('Not here.', ephemeral=True)

        self.client.on_session_needed = lambda gid: None    # 在建,但等不到
        slow = fake_interaction(guild_id=3)
        with mock.patch.object(dl, 'SESSION_WAIT', 0.1):
            asyncio.run(self.client._invoke('spec', slow, {}))
        slow.response.send_message.assert_awaited_once_with(dl.STARTING_REPLY, ephemeral=True)

    def test_waits_for_a_session_that_is_still_loading(self):
        self.a.ready = False
        threading.Timer(0.1, lambda: setattr(self.a, 'ready', True)).start()
        self.client.on_session_needed = mock.Mock()
        asyncio.run(self.client._invoke('spec', fake_interaction(guild_id=1), {}))
        self.assertEqual(self.a.got, [('invoke', 'spec', False)])
        self.client.on_session_needed.assert_not_called()

    def test_voice_events_create_sessions_only_for_the_bot_itself(self):
        asked = []
        self.client.on_session_needed = asked.append
        guild = types.SimpleNamespace(id=3)
        joined = types.SimpleNamespace(channel=types.SimpleNamespace(id=50))
        with mock.patch.object(type(self.client.client), 'user', new_callable=mock.PropertyMock,
                               return_value=types.SimpleNamespace(id=99)):
            asyncio.run(self.client.on_voice_state_update(types.SimpleNamespace(id=5, guild=guild), None, joined))
            self.assertEqual(asked, [])                 # 别人进出语音:不建会话
            asyncio.run(self.client.on_voice_state_update(
                types.SimpleNamespace(id=99, guild=guild), None, types.SimpleNamespace(channel=None)))
            self.assertEqual(asked, [])
            asyncio.run(self.client.on_voice_state_update(types.SimpleNamespace(id=99, guild=guild), None, joined))
        self.assertEqual(asked, [3])

    def test_autocomplete_warms_up_a_session(self):
        from commands.slash import Opt, _d
        asked = []
        self.client.on_session_needed = asked.append
        complete = self.client._make_autocomplete(Opt('query', _d('q', 'q', 'q'), autocomplete='library'))
        self.assertEqual(asyncio.run(complete(fake_interaction(guild_id=3), 'lo')), [])
        self.assertEqual(asked, [3])

    def test_guild_join_and_remove_hooks(self):
        seen = []
        self.client.on_guild_joined = lambda gid: seen.append(('join', gid))
        self.client.on_guild_removed = lambda gid: seen.append(('remove', gid))
        asyncio.run(self.client.on_guild_join(types.SimpleNamespace(id=3, name='New')))
        asyncio.run(self.client.on_guild_remove(types.SimpleNamespace(id=2, name='Old')))
        self.assertEqual(seen, [('join', 3), ('remove', 2)])

    def test_humans_in(self):
        members = {1: types.SimpleNamespace(bot=False), 2: types.SimpleNamespace(bot=True),
                   3: types.SimpleNamespace(bot=False)}
        channel = types.SimpleNamespace(voice_states={1: object(), 2: object(), 3: object(), 4: object()})
        guild = types.SimpleNamespace(get_channel=lambda cid: channel if cid == 55 else None,
                                      get_member=members.get)
        with mock.patch.object(self.client.client, 'get_guild', side_effect=lambda gid: guild if gid == 2 else None):
            self.assertEqual(self.client.humans_in('2', '55'), 2)  # 不算 bot,也不算查不到的
            self.assertEqual(self.client.humans_in(2, 56), 0)
            self.assertEqual(self.client.humans_in(3, 55), 0)

    def test_presence_goes_through_the_hook(self):
        seen = []
        client, link = make_link(7)
        client.on_activity = lambda gid, text, state: seen.append((gid, text, state))
        link.set_activity('Song', 'Artist')
        link.set_activity(None)
        self.assertEqual(seen, [(7, 'Song', 'Artist'), (7, None, '')])


class GuildLinkIsolationTest(unittest.TestCase):
    """GuildLink 只碰自己服务器的频道 / 消息。"""

    def setUp(self):
        self.lt = LoopThread()
        self.client, self.link = make_link(1, self.lt.loop)

    def tearDown(self):
        self.lt.stop()

    def test_adopted_panel_from_another_guild_is_ignored(self):
        foreign = mock.MagicMock()
        foreign.guild = types.SimpleNamespace(id=2)
        with mock.patch.object(self.link._client, 'get_channel', return_value=foreign):
            self.link.panel_adopt(500, 77)
            self.assertTrue(self.link.panel_end(None))
        foreign.get_partial_message.assert_not_called()
        self.assertIsNone(self.link.panel_ref)

    def test_expired_reply_never_goes_to_another_guild(self):
        foreign = mock.MagicMock()
        foreign.guild = types.SimpleNamespace(id=2)
        foreign.send = mock.AsyncMock()
        ctx = CommandContext(actor=42, name='Aiden', username='aiden', command='play', argument='',
                             interaction=fake_interaction(), channel_id=500)
        ctx.created_at -= dl.INTERACTION_TTL + 1
        with mock.patch.object(self.link._client, 'get_channel', return_value=foreign):
            self.link.reply(ctx, 'late')
        foreign.send.assert_not_called()

    def test_close_detaches_and_goes_quiet(self):
        self.link.on_command = lambda ctx: None
        self.link.on_user_joined = lambda user: None
        self.assertTrue(self.link.ready)
        with mock.patch.object(self.link, '_shutdown_voice', mock.AsyncMock()) as leave:
            self.link.close('hibernated (idle)')
        leave.assert_awaited_once()                     # 离开语音、清掉语音频道状态
        self.assertIsNone(self.client.link(1))          # 交互 / 事件不再交给它
        self.assertFalse(self.link.ready or self.link.alive)
        self.assertTrue(self.link.closed)
        self.assertIsNone(self.link.on_user_joined)
        self.assertEqual(self.link.close_reason, 'hibernated (idle)')
        self.assertFalse(self.link.panel_show({'title': 'x'}))
        self.assertFalse(self.link.panel_end(None))
        self.assertFalse(self.link.set_voice_status('x'))
        self.assertFalse(self.link.write_audio(pcm(1)))

    def test_close_leaves_a_newer_link_alone(self):
        newer = GuildLink(self.client, 1)
        self.client._links[1] = newer
        with mock.patch.object(self.link, '_shutdown_voice', mock.AsyncMock()):
            self.link.close()
        self.assertIs(self.client.link(1), newer)

    def test_text_channels(self):
        ok = types.SimpleNamespace(view_channel=True, send_messages=True)
        mute = types.SimpleNamespace(view_channel=True, send_messages=False)

        def ch(cid, name, position, category=None, perms=ok):
            return types.SimpleNamespace(id=cid, name=name, position=position, category=category,
                                         permissions_for=lambda me: perms)

        music = types.SimpleNamespace(position=1)
        guild = types.SimpleNamespace(me=object(), text_channels=[
            ch(30, 'requests', 0, music), ch(10, 'general', 0), ch(20, 'rules', 1, perms=mute), ch(11, 'chat', 2)])
        with mock.patch.object(self.link, '_guild', return_value=guild):
            self.assertEqual(self.link.text_channels(), [
                {'id': '10', 'name': 'general'}, {'id': '11', 'name': 'chat'}, {'id': '30', 'name': 'requests'}])
        with mock.patch.object(self.link, '_guild', return_value=None):
            self.assertEqual(self.link.text_channels(), [])

    def test_voice_lost_after_reconnect_is_reported(self):
        moved = []
        self.link.on_self_moved = lambda old, new: moved.append((old, new))
        self.link._emit = lambda fn, *args: fn(*args)
        self.link._me_id = 99
        self.link._users = {99: dl.User(session=99, name='bot', channel_id=5)}
        self.link._pcm.set_sink(lambda: None)
        with mock.patch.object(self.link, '_rebuild', side_effect=lambda: setattr(self.link, '_users', {})):
            self.link._after_ready()
        self.assertEqual(moved, [(5, None)])
        self.assertIsNone(self.link._pcm._sink)        # 音频输出断开,播放线程不会卡在写缓冲上
        with mock.patch.object(self.link, '_rebuild'):
            self.link._after_ready()                   # 没变化:不再报告
        self.assertEqual(moved, [(5, None)])


class ClientContractTest(unittest.TestCase):
    """Hub 给 Web 层用的 guild_info / fetch_member 在 DiscordClient 这一侧的实现。"""

    def setUp(self):
        self.lt = LoopThread()
        self.client = DiscordClient('token', home_guild_id=1)
        self.client._loop = self.lt.loop

    def tearDown(self):
        self.lt.stop()

    def test_guild_info(self):
        guild = types.SimpleNamespace(id=1, name='Home', icon=types.SimpleNamespace(url='https://cdn/icon.png'))
        bare = types.SimpleNamespace(id=2, name='Bare', icon=None)
        guilds = {1: guild, 2: bare}
        with mock.patch.object(self.client.client, 'get_guild', side_effect=guilds.get):
            self.assertEqual(self.client.guild_info('1'), {'id': '1', 'name': 'Home', 'icon': 'https://cdn/icon.png'})
            self.assertEqual(self.client.guild_info(2)['icon'], '')
            self.assertIsNone(self.client.guild_info('3'))
            self.assertIsNone(self.client.guild_info('nope'))

    def test_fetch_member(self):
        not_found = discord.NotFound(types.SimpleNamespace(status=404, reason='Not Found'), 'Unknown Member')
        guild = types.SimpleNamespace(fetch_member=mock.AsyncMock())
        with mock.patch.object(self.client.client, 'get_guild', side_effect=lambda gid: guild if gid == 1 else None):
            self.assertIs(self.client.fetch_member('1', '42'), True)
            guild.fetch_member.assert_awaited_once_with(42)
            guild.fetch_member.side_effect = not_found
            self.assertIs(self.client.fetch_member(1, 42), False)
            guild.fetch_member.side_effect = RuntimeError('network down')
            self.assertIsNone(self.client.fetch_member(1, 42))     # 查不了 != 不是成员
            self.assertIs(self.client.fetch_member(5, 42), False)  # bot 不在这个服务器


if __name__ == '__main__':
    unittest.main()
