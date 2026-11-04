"""Discord 连接适配层:整个 bot 只有这个模块 import discord.py。

bot 其余部分是线程模型,discord.py 是 asyncio:这里把 discord.py 放在自己的线程 + 事件循环里跑,
对外暴露同步接口(和 Mumble 版的 MumbleLink 基本一致,播放 / 频道逻辑几乎不用改):

  - 状态快照:users(user_id -> User)、myself、my_channel_id、channels(channel_id -> dict)
  - 命令:reply / finish(回复斜杠命令)、send_announcement(发到公告频道)、move / leave_voice
  - 音频:write_audio(阻塞到缓冲有空位)、audio_buffered、clear_audio、cut_audio、volume
  - 回调:on_command / on_precheck / on_autocomplete / on_user_joined / on_user_updated / on_user_left

回调在本模块的分发线程里依次调用(不是事件循环线程);on_precheck / on_autocomplete 要在
3 秒内给 Discord 答复,在线程池里同步执行,应当很快返回。

单服务器模式:只服务一个 guild(配置的 guild_id,没配就用 bot 加入的第一个),其他服务器里的
命令直接拒绝。斜杠命令同步到这个 guild(即时生效,不用等全局命令的缓存)。
"""

from __future__ import annotations

import asyncio
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Literal, Mapping, Optional, Tuple

import audioop  # Python 3.13+ 由 audioop-lts 提供

import discord
from discord import app_commands

from .discord_format import html_to_markdown, split_message

log = logging.getLogger("bot")

SAMPLE_RATE = 48000
CHANNELS = 2
SAMPLE_BYTES = 2
BYTES_PER_SECOND = SAMPLE_RATE * CHANNELS * SAMPLE_BYTES
#: discord.py 每次 read() 要 20 ms 的 PCM
FRAME_BYTES = BYTES_PER_SECOND // 50
#: 写给发送端的缓冲上限(秒):播放线程写满后自然被播放速度节流
AUDIO_BUFFER_SECONDS = 0.5
#: 缓冲空了以后再送多少帧静音才停止发送(歌与歌之间的小空档不至于反复开关 "speaking")
IDLE_SILENCE_FRAMES = 50
#: 交互 token 15 分钟后失效;留点余量,之后的回复改发到频道里
INTERACTION_TTL = 14 * 60
#: 命令处理完还没回复过的话,等这么久再删掉 "思考中…"(期间有后台线程回复就直接用上)
FINISH_GRACE = 3.0

SILENCE = b'\x00' * FRAME_BYTES


# =========================================================================
#   快照对象
# =========================================================================

@dataclass(frozen=True)
class User:
    """语音频道里的一个成员。字段名沿用 Mumble 版(session = user id),频道 / 跟随逻辑不用改。"""

    session: int
    name: str
    channel_id: Optional[int]
    user_id: int = 0
    username: str = ''
    bot: bool = False
    self_mute: bool = False
    self_deaf: bool = False
    mute: bool = False
    deaf: bool = False


@dataclass
class CommandContext:
    """一次斜杠命令调用。命令处理函数里的 ``text`` 参数就是它。"""

    actor: int                      # 发命令的人的 user id
    name: str                       # 显示名(服务器昵称 > 全局昵称 > 用户名)
    username: str                   # 唯一用户名(不随昵称变)
    command: str                    # 命令的 key(spec.key)
    argument: str                   # 各参数值拼成的字符串
    options: Dict[str, Any] = field(default_factory=dict)
    channel_id: Optional[int] = None        # 发命令的文字频道
    voice_channel_id: Optional[int] = None  # 发命令的人当时所在的语音频道
    guild_id: Optional[int] = None
    role_ids: Tuple[int, ...] = ()
    is_admin: bool = False
    ephemeral: bool = False
    interaction: Any = None
    created_at: float = field(default_factory=time.time)
    # 内部状态
    responded: bool = False         # 已经用 edit_original_response 回过
    finished: bool = False
    _finish_handle: Any = None

    @property
    def session(self):
        """兼容旧代码(Mumble 里非空表示私聊);斜杠命令总是在服务器里。"""
        return ()

    def expired(self):
        return time.time() - self.created_at > INTERACTION_TTL


# =========================================================================
#   音频:推模式(播放线程 write) -> 拉模式(discord.py 每 20 ms read)
# =========================================================================

class PCMStream(discord.AudioSource):
    """有界 PCM 缓冲。播放主循环 write(),discord.py 的 AudioPlayer 线程 read()。

    缓冲空了先送 IDLE_SILENCE_FRAMES 帧静音,再返回 b'' 让 AudioPlayer 停下(Discord 里头像上的
    绿圈随之熄灭);下次有数据写进来时由 link 重新 play()。没连语音的时候(sink 为 None)
    按实时速度丢弃,播放进度照常走,不会把播放线程卡死。
    """

    def __init__(self, capacity=AUDIO_BUFFER_SECONDS):
        self._cond = threading.Condition()
        self._buf = bytearray()
        self._capacity = max(FRAME_BYTES, int(capacity * BYTES_PER_SECOND) // FRAME_BYTES * FRAME_BYTES)
        self._gain = 1.0          # 上一帧结束时的增益
        self._target_gain = 1.0
        self._idle = 0
        self._playing = False     # 有 AudioPlayer 正在读
        self._closed = False
        self._sink: Optional[Callable[[], None]] = None  # 启动 AudioPlayer 的回调

    # ---- discord.AudioSource ----

    def is_opus(self):
        return False

    def cleanup(self):
        # AudioPlayer 结束时会调用;缓冲是长期复用的,这里什么都不做
        pass

    def read(self):
        with self._cond:
            if len(self._buf) >= FRAME_BYTES:
                chunk = bytes(self._buf[:FRAME_BYTES])
                del self._buf[:FRAME_BYTES]
                self._idle = 0
            elif self._buf:
                # 一首歌最后不足 20 ms 的尾巴:补零凑成一帧
                chunk = bytes(self._buf) + b'\x00' * (FRAME_BYTES - len(self._buf))
                self._buf.clear()
                self._idle = 0
            else:
                self._idle += 1
                if self._idle > IDLE_SILENCE_FRAMES or self._closed:
                    self._playing = False
                    self._cond.notify_all()
                    return b''
                chunk = SILENCE
            self._cond.notify_all()
            target = self._target_gain
            start = self._gain
            self._gain = target
        return _apply_gain(chunk, start, target)

    # ---- 写入端 ----

    def write(self, pcm):
        """写入 PCM,缓冲满时阻塞。连接已关闭返回 False。"""
        if not pcm:
            return True
        with self._cond:
            if self._closed:
                return False
            if self._sink is None:
                sink = None
            else:
                while not self._closed and self._sink is not None \
                        and len(self._buf) + len(pcm) > self._capacity:
                    self._ensure_playing()
                    self._cond.wait(timeout=0.25)
                if self._closed:
                    return False
                sink = self._sink
                if sink is not None:
                    self._buf.extend(pcm)
                    self._ensure_playing()
                    return True
        # 没连语音:按实时速度丢掉,让播放进度照常前进
        time.sleep(len(pcm) / BYTES_PER_SECOND)
        return True

    def _ensure_playing(self):
        # 持锁调用
        if not self._playing and self._sink is not None and self._buf:
            self._playing = True
            try:
                self._sink()
            except Exception:
                self._playing = False
                log.exception("discord: could not start the audio player")

    def player_unavailable(self):
        """暂时没法开播(语音还没连好):标记为没在播,下次 write 时再试(不立刻重试,免得空转)。"""
        with self._cond:
            self._playing = False
            self._cond.notify_all()

    def player_stopped(self):
        """AudioPlayer 意外结束(after 回调):允许下次写入时重新启动。"""
        with self._cond:
            self._playing = False
            restart = bool(self._buf)
            if restart:
                self._ensure_playing()
            self._cond.notify_all()

    def set_sink(self, sink):
        """连上语音时传入启动播放的回调;断开时传 None(并丢掉缓冲)。"""
        with self._cond:
            self._sink = sink
            if sink is None:
                self._buf.clear()
                self._playing = False
            else:
                self._ensure_playing()
            self._cond.notify_all()

    def clear(self):
        with self._cond:
            self._buf.clear()
            self._cond.notify_all()

    def close(self):
        with self._cond:
            self._closed = True
            self._buf.clear()
            self._cond.notify_all()

    @property
    def buffered(self):
        """还没播出去的秒数。"""
        return len(self._buf) / BYTES_PER_SECOND

    @property
    def playing(self):
        return self._playing

    def set_gain(self, value):
        self._target_gain = max(0.0, float(value))


def _apply_gain(chunk, start, target):
    """按帧施加音量;增益变化时在这一帧里分 8 段线性过渡,避免咔哒声。"""
    if start == target:
        if target == 1.0:
            return chunk
        return audioop.mul(chunk, SAMPLE_BYTES, target)
    pieces = 8
    size = len(chunk) // pieces  # 480 字节 = 120 个立体声采样
    out = []
    for i in range(pieces):
        gain = start + (target - start) * (i + 1) / pieces
        out.append(audioop.mul(chunk[i * size:(i + 1) * size], SAMPLE_BYTES, gain))
    return b''.join(out)


# =========================================================================
#   斜杠命令
# =========================================================================

class _Translator(app_commands.Translator):
    """命令 / 参数说明的本地化:locale_str.extras['i18n'] 里放着 {locale: 文本}。"""

    async def translate(self, string, locale, context):
        table = string.extras.get('i18n') if string.extras else None
        if not table:
            return None
        key = {discord.Locale.chinese: 'zh-CN', discord.Locale.japanese: 'ja'}.get(locale)
        if key is None and str(locale).startswith('en'):
            key = 'en'
        return table.get(key) if key else None


def _desc(text_by_locale, default_locale='en'):
    base = text_by_locale.get(default_locale) or text_by_locale['en']
    return app_commands.locale_str(base[:100], i18n={k: v[:100] for k, v in text_by_locale.items()})


# =========================================================================
#   连接
# =========================================================================

class DiscordLink:
    def __init__(self, token, guild_id=None, announce_channel_id=None, admin_ids=(),
                 admin_permission=True, self_deaf=True, bitrate=0, language='en_US', debug=False):
        self.token = token
        self.guild_id = int(guild_id) if guild_id else None
        self.announce_channel_id = int(announce_channel_id) if announce_channel_id else None
        self.admin_ids = {int(x) for x in admin_ids}
        self.admin_permission = admin_permission
        self.self_deaf = self_deaf
        self.bitrate = int(bitrate or 0)
        self.default_locale = {'zh_CN': 'zh-CN', 'ja_JP': 'ja'}.get(language, 'en')
        if debug:
            # discord.py 的调试日志也写进 bot 的日志(根 logger 只显示 WARNING 以上)
            dlog = logging.getLogger("discord")
            dlog.setLevel(logging.DEBUG)
            for handler in log.handlers:
                dlog.addHandler(handler)

        intents = discord.Intents.none()
        intents.guilds = True        # 频道列表、角色
        intents.voice_states = True  # 谁在哪个语音频道;连语音也需要
        self._client = discord.Client(intents=intents, allowed_mentions=discord.AllowedMentions.none())
        self._tree = app_commands.CommandTree(self._client)
        self._tree.on_error = self._on_tree_error
        self._client.event(self.on_ready)
        self._client.event(self.on_voice_state_update)
        self._client.event(self.on_guild_channel_create)
        self._client.event(self.on_guild_channel_delete)
        self._client.event(self.on_guild_channel_update)
        self._client.event(self.on_guild_update)

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._closed = threading.Event()
        self._error: Optional[BaseException] = None
        self._close_reason = ''
        self._synced = False

        self._users: Mapping[int, User] = {}
        self._channels: Dict[int, dict] = {}
        self._me_id: Optional[int] = None
        self._guild_name = ''
        self._last_command_channel: Optional[int] = None

        self._pcm = PCMStream()
        self._volume = 1.0
        self._cutting = False

        self._events: "queue.Queue" = queue.Queue()
        self._dispatcher: Optional[threading.Thread] = None

        self.on_command: Optional[Callable[[CommandContext], None]] = None
        self.on_precheck: Optional[Callable[[CommandContext], Optional[str]]] = None
        self.on_autocomplete: Optional[Callable[[str, CommandContext, str], List[Tuple[str, str]]]] = None
        self.on_user_joined: Optional[Callable[[User], None]] = None
        self.on_user_updated: Optional[Callable[[User, frozenset], None]] = None
        self.on_user_left: Optional[Callable[[User], None]] = None
        self.on_self_moved: Optional[Callable[[Optional[int], Optional[int]], None]] = None
        self._specs: List[Tuple[str, Any]] = []
        self._spec_by_key: Dict[str, Any] = {}

    # ---- 生命周期 ----------------------------------------------------------

    def register_commands(self, named_specs):
        """[(slash 名, Spec)];必须在 connect() 之前调用。"""
        self._specs = list(named_specs)
        self._spec_by_key = {spec.key: (name, spec) for name, spec in self._specs}
        for name, spec in self._specs:
            self._tree.add_command(self._build_command(name, spec))

    def connect(self, timeout=60):
        """登录并等到 guild 数据同步完。失败时抛异常(token 错误、超时……)。"""
        self._dispatcher = threading.Thread(target=self._dispatch, name="DiscordEvents", daemon=True)
        self._dispatcher.start()
        self._thread = threading.Thread(target=self._run, name="DiscordLoop", daemon=True)
        self._thread.start()
        if not self._ready.wait(timeout):
            if self._error is not None:
                raise self._error
            raise TimeoutError("timed out waiting for Discord to become ready")
        if self._error is not None:
            raise self._error

    def _run(self):
        try:
            asyncio.run(self._main())
        except BaseException as e:  # noqa: BLE001 - 记录后让 connect()/alive 感知
            self._error = e
            self._close_reason = repr(e)
            log.error("discord: client stopped: %r", e)
        finally:
            self._closed.set()
            self._ready.set()
            self._pcm.close()
            self._events.put(None)

    async def _main(self):
        self._loop = asyncio.get_running_loop()
        await self._tree.set_translator(_Translator())
        async with self._client:
            await self._client.start(self.token, reconnect=True)

    def close(self):
        loop = self._loop
        if loop is not None and not loop.is_closed():
            try:
                asyncio.run_coroutine_threadsafe(self._shutdown(), loop).result(timeout=10)
            except Exception:
                pass
        self._closed.set()
        self._pcm.close()

    async def _shutdown(self):
        guild = self._guild()
        if guild is not None and guild.voice_client is not None:
            try:
                await guild.voice_client.disconnect(force=True)
            except Exception:
                pass
        await self._client.close()

    @property
    def alive(self):
        """连接还在。discord.py 自己会断线重连;只有彻底退出(token 失效等)才是 False。"""
        return not self._closed.is_set()

    @property
    def close_reason(self):
        return self._close_reason

    # ---- 线程桥 ------------------------------------------------------------

    def _call(self, coro, timeout=30.0):
        """在事件循环里执行协程并等结果(从别的线程调用)。在事件循环线程里调用时只调度不等。"""
        loop = self._loop
        if loop is None or loop.is_closed():
            coro.close()
            return None
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            loop.create_task(coro)
            return None
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=timeout)

    def _emit(self, fn, *args):
        self._events.put((fn, args))

    def _dispatch(self):
        while True:
            item = self._events.get()
            if item is None:
                return
            fn, args = item
            if fn is None:
                continue
            try:
                fn(*args)
            except Exception:
                log.exception("discord: event handler %s failed", getattr(fn, '__name__', fn))

    # ---- discord.py 事件 ----------------------------------------------------

    def _guild(self) -> Optional[discord.Guild]:
        if self.guild_id is not None:
            return self._client.get_guild(self.guild_id)
        return None

    async def on_ready(self):
        if self.guild_id is None:
            guilds = list(self._client.guilds)
            if not guilds:
                log.error("discord: the bot is not in any server yet; invite it first (see README)")
            else:
                self.guild_id = guilds[0].id
                if len(guilds) > 1:
                    log.warning("discord: the bot is in %d servers but runs in single-server mode; "
                                "serving %s (%s). Set [discord] guild_id to choose.",
                                len(guilds), guilds[0].name, guilds[0].id)
        guild = self._guild()
        if guild is None and self.guild_id is not None:
            log.error("discord: server %s not found; is the bot invited to it?", self.guild_id)
        self._me_id = self._client.user.id if self._client.user else None
        self._rebuild()
        if guild is not None and not self._synced:
            try:
                self._tree.copy_global_to(guild=guild)
                synced = await self._tree.sync(guild=guild)
                self._synced = True
                log.info("discord: synced %d slash commands to %s", len(synced), guild.name)
            except Exception:
                log.exception("discord: could not sync slash commands")
        log.info("discord: logged in as %s, serving %s", self._client.user, guild.name if guild else '-')
        self._ready.set()

    async def on_voice_state_update(self, member, before, after):
        if member.guild.id != self.guild_id:
            return
        old = self._users.get(member.id)
        self._rebuild_users()
        new = self._users.get(member.id)
        if member.id == self._me_id:
            old_cid = old.channel_id if old else None
            new_cid = new.channel_id if new else None
            if old_cid != new_cid:
                self._on_self_voice(new_cid)
                if self.on_self_moved:
                    self._emit(self.on_self_moved, old_cid, new_cid)
        if old is None and new is not None:
            if self.on_user_joined:
                self._emit(self.on_user_joined, new)
        elif old is not None and new is None:
            if self.on_user_left:
                self._emit(self.on_user_left, old)
        elif old is not None and new is not None:
            changed = frozenset(k for k in ('channel_id', 'self_mute', 'self_deaf', 'mute', 'deaf', 'name')
                                if getattr(old, k) != getattr(new, k))
            if changed and self.on_user_updated:
                self._emit(self.on_user_updated, new, changed)

    async def on_guild_channel_create(self, channel):
        if channel.guild.id == self.guild_id:
            self._rebuild()

    async def on_guild_channel_delete(self, channel):
        if channel.guild.id == self.guild_id:
            self._rebuild()

    async def on_guild_channel_update(self, before, after):
        if after.guild.id == self.guild_id:
            self._rebuild()

    async def on_guild_update(self, before, after):
        if after.id == self.guild_id:
            self._rebuild()

    # ---- 快照 --------------------------------------------------------------

    def _rebuild(self):
        self._rebuild_channels()
        self._rebuild_users()

    def _rebuild_users(self):
        guild = self._guild()
        users = {}
        if guild is not None:
            connected = guild.voice_client is not None
            for vc in list(guild.voice_channels) + list(guild.stage_channels):
                for uid, state in list(vc.voice_states.items()):
                    if uid == self._me_id and not connected:
                        # 上次进程留下的语音状态(重启后 Discord 还会挂一会儿):其实没连着,不算在频道里
                        continue
                    member = guild.get_member(uid)
                    if member is None:
                        continue
                    users[uid] = User(
                        session=uid, user_id=uid, name=member.display_name, username=member.name,
                        channel_id=vc.id, bot=member.bot,
                        self_mute=bool(state.self_mute), self_deaf=bool(state.self_deaf),
                        mute=bool(state.mute), deaf=bool(state.deaf))
        self._users = users  # 整体替换:其他线程读到的总是一份完整快照

    def _rebuild_channels(self):
        guild = self._guild()
        out = {}
        if guild is not None:
            self._guild_name = guild.name
            out[0] = {'channel_id': 0, 'name': guild.name, 'position': 0, 'kind': 'guild', 'joinable': False}
            me = guild.me
            for cat in guild.categories:
                out[cat.id] = {'channel_id': cat.id, 'name': cat.name, 'parent': 0,
                               'position': cat.position, 'kind': 'category', 'joinable': False}
            afk = guild.afk_channel.id if guild.afk_channel else None
            for vc in list(guild.voice_channels) + list(guild.stage_channels):
                stage = isinstance(vc, discord.StageChannel)
                perms = vc.permissions_for(me) if me is not None else None
                joinable = bool(perms and perms.view_channel and perms.connect and perms.speak) and not stage
                parent = vc.category_id if vc.category_id in out else 0
                out[vc.id] = {
                    'channel_id': vc.id, 'name': vc.name, 'parent': parent,
                    # 不在分类里的语音频道在 Discord 里排在所有分类前面
                    'position': vc.position if parent else vc.position - 10000,
                    'kind': 'stage' if stage else 'voice', 'joinable': joinable, 'afk': vc.id == afk,
                    'user_limit': vc.user_limit or 0,
                }
        self._channels = out

    @property
    def users(self) -> Mapping[int, User]:
        """user_id -> User:只包含在语音频道里的成员(含 bot 自己)。"""
        return self._users

    @property
    def myself(self) -> Optional[User]:
        if self._me_id is None:
            return None
        return self._users.get(self._me_id)

    @property
    def my_channel_id(self):
        me = self.myself
        return me.channel_id if me is not None else None

    @property
    def channels(self):
        """channel_id -> dict(channel_id/name/parent/position/kind/joinable/afk)。0 = 服务器本身(根)。"""
        return dict(self._channels)

    @property
    def guild_name(self):
        return self._guild_name

    @property
    def max_message_length(self):
        # HTML 长度;转成 Markdown 后一般更短,超出的部分 reply 里还会再切
        return 1900

    @property
    def bot_user_id(self):
        return self._me_id

    @property
    def bot_name(self):
        user = self._client.user
        return user.name if user is not None else ''

    # ---- 语音 --------------------------------------------------------------

    def move(self, channel_id):
        """进入 / 切换到语音频道。返回是否成功。"""
        try:
            return bool(self._call(self._move(channel_id), timeout=45))
        except Exception:
            log.exception("discord: could not join voice channel %s", channel_id)
            return False

    async def _move(self, channel_id):
        guild = self._guild()
        if guild is None:
            return False
        channel = guild.get_channel(int(channel_id))
        if not isinstance(channel, discord.VoiceChannel):
            log.warning("discord: %s is not a voice channel", channel_id)
            return False
        vc = guild.voice_client
        if vc is not None and vc.is_connected():
            if vc.channel and vc.channel.id == channel.id:
                return True
            await vc.move_to(channel)
        else:
            if vc is not None:
                await vc.disconnect(force=True)
            await channel.connect(self_deaf=self.self_deaf, reconnect=True, timeout=30)
        self._on_self_voice(channel.id)
        return True

    def leave_voice(self):
        try:
            self._call(self._leave(), timeout=15)
        except Exception:
            log.exception("discord: could not leave the voice channel")

    async def _leave(self):
        guild = self._guild()
        if guild is not None and guild.voice_client is not None:
            await guild.voice_client.disconnect(force=False)
        self._on_self_voice(None)

    def _on_self_voice(self, channel_id):
        """bot 自己进出语音:接上 / 断开音频输出。"""
        if channel_id is None:
            self._pcm.set_sink(None)
        else:
            self._pcm.set_sink(self._request_play)

    def _request_play(self):
        loop = self._loop
        if loop is not None and not loop.is_closed():
            loop.call_soon_threadsafe(self._start_player, 0)

    def _start_player(self, attempt):
        guild = self._guild()
        vc = guild.voice_client if guild is not None else None
        if vc is None or not vc.is_connected():
            if attempt < 100 and vc is not None:
                # 刚 connect / move_to,语音握手还没完成
                self._loop.call_later(0.1, self._start_player, attempt + 1)
            else:
                self._pcm.player_unavailable()
            return
        if vc.is_playing():
            if vc.source is self._pcm and attempt < 20:
                # 上一个 AudioPlayer 正在退出(read 刚返回 b'')
                self._loop.call_later(0.02, self._start_player, attempt + 1)
            return
        bitrate = self.bitrate or min(max(int((vc.channel.bitrate or 64000) / 1000), 64), 384)
        try:
            vc.play(self._pcm, after=self._player_after, application='audio', bitrate=min(bitrate, 512),
                    signal_type='music')
        except discord.ClientException:
            self._loop.call_later(0.05, self._start_player, attempt + 1)

    def _player_after(self, error):
        if error is not None:
            log.warning("discord: audio player stopped with an error: %s", error)
        self._pcm.player_stopped()

    # ---- 音频 --------------------------------------------------------------

    def write_audio(self, pcm):
        """把 PCM(s16le 48 kHz 立体声)交给发送端。缓冲满 0.5 秒时阻塞。连接已关闭返回 False。"""
        return self._pcm.write(pcm)

    @property
    def audio_buffered(self):
        return self._pcm.buffered

    def clear_audio(self):
        self._pcm.clear()

    def cut_audio(self, fade=0.03):
        """切歌 / 暂停:让下一帧淡出到静音,再丢掉缓冲里还没播的部分。"""
        if not self._pcm.playing:
            self._pcm.clear()
            return
        self._cutting = True
        try:
            self._pcm.set_gain(0.0)
            time.sleep(max(fade, 0.045))  # 至少过一帧(20 ms)多一点
            self._pcm.clear()
        finally:
            self._cutting = False
            self._pcm.set_gain(self._volume)

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value):
        self._volume = value
        if not self._cutting:
            self._pcm.set_gain(value)

    # ---- 文字 --------------------------------------------------------------

    def reply(self, ctx: CommandContext, message, ephemeral=None):
        """回复一条斜杠命令。message 是 bot 内部的 HTML,这里转 Markdown 并按长度切分。不抛异常。"""
        text = html_to_markdown(message)
        if not text:
            return
        ephemeral = ctx.ephemeral if ephemeral is None else ephemeral
        for chunk in split_message(text):
            try:
                self._call(self._reply(ctx, chunk, ephemeral), timeout=20)
            except Exception:
                log.warning("discord: could not reply to /%s", ctx.command, exc_info=True)
                return

    async def _reply(self, ctx, content, ephemeral):
        interaction = ctx.interaction
        if interaction is None or ctx.expired():
            channel = self._client.get_channel(ctx.channel_id) if ctx.channel_id else None
            if channel is not None:
                await channel.send(content, suppress_embeds=True)
            return
        if ctx._finish_handle is not None:
            ctx._finish_handle.cancel()
            ctx._finish_handle = None
        if not ctx.responded and ephemeral == ctx.ephemeral:
            ctx.responded = True
            await interaction.edit_original_response(content=content)
        else:
            await interaction.followup.send(content, ephemeral=ephemeral, suppress_embeds=True)

    def finish(self, ctx: CommandContext):
        """命令处理完。还没回复过就过一会儿删掉 "思考中…"(期间有回复就不删)。"""
        ctx.finished = True
        loop = self._loop
        if loop is None or loop.is_closed() or ctx.interaction is None:
            return
        loop.call_soon_threadsafe(self._schedule_finish, ctx)

    def _schedule_finish(self, ctx):
        if ctx.responded or ctx._finish_handle is not None:
            return
        ctx._finish_handle = self._loop.call_later(
            FINISH_GRACE, lambda: self._loop.create_task(self._drop_thinking(ctx)))

    async def _drop_thinking(self, ctx):
        ctx._finish_handle = None
        if ctx.responded or ctx.expired():
            return
        try:
            await ctx.interaction.delete_original_response()
        except discord.HTTPException:
            pass

    def send_announcement(self, message):
        """发到公告频道:配置的 announce_channel → 最近一次发命令的频道 → bot 所在语音频道的文字区。"""
        text = html_to_markdown(message)
        if not text:
            return
        try:
            self._call(self._announce(text), timeout=20)
        except Exception:
            log.warning("discord: could not send an announcement", exc_info=True)

    async def _announce(self, text):
        channel = None
        for cid in (self.announce_channel_id, self._last_command_channel, self.my_channel_id):
            if cid:
                channel = self._client.get_channel(cid)
                if channel is not None and hasattr(channel, 'send'):
                    break
                channel = None
        if channel is None:
            log.debug("discord: no channel to post announcements in")
            return
        for chunk in split_message(text):
            await channel.send(chunk, suppress_embeds=True)

    def set_activity(self, text):
        """bot 的状态:"正在听 {text}";None 清除。"""
        activity = discord.Activity(type=discord.ActivityType.listening, name=text[:128]) if text else None
        try:
            self._call(self._client.change_presence(activity=activity), timeout=10)
        except Exception:
            log.debug("discord: could not change presence", exc_info=True)

    # ---- 斜杠命令 ----------------------------------------------------------

    def _build_command(self, name, spec):
        import inspect

        params = [inspect.Parameter('interaction', inspect.Parameter.POSITIONAL_OR_KEYWORD,
                                    annotation=discord.Interaction)]
        descriptions = {}
        for opt in spec.options:
            annotation = _annotation(opt)
            default = inspect.Parameter.empty if opt.required else None
            if not opt.required:
                annotation = Optional[annotation]
            params.append(inspect.Parameter(opt.name, inspect.Parameter.KEYWORD_ONLY,
                                            annotation=annotation, default=default))
            descriptions[opt.name] = _desc(opt.desc, self.default_locale)

        link = self

        async def callback(interaction: discord.Interaction, **kwargs):
            await link._invoke(spec, interaction, kwargs)

        callback.__signature__ = inspect.Signature(params)
        callback.__name__ = f"slash_{spec.key}"
        callback.__qualname__ = callback.__name__
        callback.__discord_app_commands_param_description__ = descriptions
        command = app_commands.Command(name=name, description=_desc(spec.desc, self.default_locale),
                                       callback=callback)
        command.guild_only = True
        for opt in spec.options:
            if opt.autocomplete:
                command.autocomplete(opt.name)(self._make_autocomplete(opt))
        return command

    def _make_autocomplete(self, opt):
        link = self

        async def autocomplete(interaction: discord.Interaction, current: str):
            handler = link.on_autocomplete
            if handler is None:
                return []
            ctx = link._context(None, interaction, {})
            try:
                results = await asyncio.wait_for(
                    asyncio.get_running_loop().run_in_executor(None, handler, opt.autocomplete, ctx, current or ''),
                    timeout=2.5)
            except Exception:
                log.debug("discord: autocomplete %s failed", opt.autocomplete, exc_info=True)
                return []
            choices = []
            for label, value in (results or [])[:25]:
                if opt.kind == 'int':
                    try:
                        value = int(value)
                    except (TypeError, ValueError):
                        continue
                else:
                    value = str(value)[:100]
                choices.append(app_commands.Choice(name=str(label)[:100] or str(value), value=value))
            return choices

        return autocomplete

    def _context(self, spec, interaction, kwargs):
        member = interaction.user
        voice = getattr(member, 'voice', None)
        role_ids = tuple(r.id for r in getattr(member, 'roles', ()) or ())
        perms = getattr(member, 'guild_permissions', None)
        is_admin = (member.id in self.admin_ids or any(r in self.admin_ids for r in role_ids)
                    or (self.admin_permission and perms is not None
                        and (perms.administrator or perms.manage_guild)))
        options = {}
        parts = []
        if spec is not None:
            for opt in spec.options:
                value = kwargs.get(opt.name)
                if value is None:
                    continue
                if opt.kind == 'user':
                    options[f'{opt.name}_name'] = getattr(value, 'display_name', None) or value.name
                    value = str(value.id)
                elif opt.kind == 'bool':
                    options[opt.name] = bool(value)
                    if value:
                        parts.append(opt.name)
                    continue
                options[opt.name] = value
                parts.append(str(value).strip())
        return CommandContext(
            actor=member.id,
            name=getattr(member, 'display_name', None) or member.name,
            username=member.name,
            command=spec.key if spec is not None else '',
            argument=' '.join(p for p in parts if p),
            options=options,
            channel_id=interaction.channel_id,
            voice_channel_id=voice.channel.id if voice is not None and voice.channel is not None else None,
            guild_id=interaction.guild_id,
            role_ids=role_ids,
            is_admin=bool(is_admin),
            ephemeral=bool(spec.ephemeral) if spec is not None else True,
            interaction=interaction,
        )

    async def _invoke(self, spec, interaction, kwargs):
        if interaction.guild_id is None or interaction.guild_id != self.guild_id:
            await interaction.response.send_message(
                "This bot only works in its home server for now.", ephemeral=True)
            return
        ctx = self._context(spec, interaction, kwargs)
        if self.on_precheck is not None:
            try:
                refusal = await asyncio.wait_for(
                    asyncio.get_running_loop().run_in_executor(None, self.on_precheck, ctx), timeout=2.0)
            except Exception:
                log.exception("discord: precheck for /%s failed", spec.key)
                refusal = None
            if refusal:
                await interaction.response.send_message(html_to_markdown(refusal)[:2000], ephemeral=True)
                return
        await interaction.response.defer(ephemeral=ctx.ephemeral, thinking=True)
        if not ctx.ephemeral:
            self._last_command_channel = interaction.channel_id
        if self.on_command is None:
            await interaction.edit_original_response(content="The bot is still starting, try again in a moment.")
            return
        self._emit(self.on_command, ctx)

    async def _on_tree_error(self, interaction, error):
        log.error("discord: slash command error: %s", error, exc_info=error)
        try:
            if interaction.response.is_done():
                await interaction.followup.send("Something went wrong.", ephemeral=True)
            else:
                await interaction.response.send_message("Something went wrong.", ephemeral=True)
        except Exception:
            pass


def _annotation(opt):
    if opt.kind == 'int':
        if opt.min is not None or opt.max is not None:
            return app_commands.Range[int, opt.min, opt.max]
        return int
    if opt.kind == 'bool':
        return bool
    if opt.kind == 'user':
        return discord.User
    if opt.kind == 'choice':
        return Literal[tuple(opt.choices)]
    return str
