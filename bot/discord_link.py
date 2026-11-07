"""Discord 连接适配层:整个 bot 只有这个模块 import discord.py。

bot 其余部分是线程模型,discord.py 是 asyncio:这里把 discord.py 放在自己的线程 + 事件循环里跑,
对外暴露同步接口。分两层:

  DiscordClient(每个进程一个):登录、事件循环线程、斜杠命令树、持久面板按钮;交互和网关事件
      按 guild_id 转给对应的 GuildLink。
  GuildLink(每个服务器一个,接口和 Mumble 版的 MumbleLink 基本一致,播放 / 频道逻辑几乎不用改):
    - 状态快照:users(user_id -> User)、myself、my_channel_id、channels(channel_id -> dict)
    - 命令:reply / finish(回复斜杠命令)、send_announcement(发到公告频道)、move / leave_voice
    - "正在播放":panel_show / panel_end(公告频道里的 embed 面板 + 按钮)、set_voice_status(语音频道状态)
    - 音频:write_audio(阻塞到缓冲有空位)、audio_buffered、clear_audio、cut_audio、volume
    - 回调:on_command / on_precheck / on_autocomplete / on_user_joined / on_user_updated / on_user_left

回调在共享线程池(bot.executor.KeyedExecutor)里按 (guild_id, 'evt') 依次调用,不在事件循环线程里;
on_precheck / on_autocomplete 要在 3 秒内给 Discord 答复,在各自的小线程池里同步执行,应当很快返回。

斜杠命令是全局的;bot 主人命令只注册在 [discord] owner_guild_id。
还没有会话的服务器来了交互(或 bot 自己出现在那里的语音频道):DiscordClient 通过 on_session_needed
请 Hub 按需建会话,等它准备好再交给新的 GuildLink;Hub 拒绝(不允许的服务器、会话数到上限)就回理由。
会话休眠时 GuildLink.close() 把自己从 DiscordClient 上摘下。
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import hashlib
import json
import logging
import threading
import time
from dataclasses import dataclass, field
from io import BytesIO
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
#: 面板封面附件的文件名(embed 里用 attachment://<名字> 引用)
PANEL_COVER_NAME = 'cover.jpg'


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
    #: bot 主人([bot] admin 里的用户 ID);服务器管理员只是 is_admin,不是主人
    is_owner: bool = False
    ephemeral: bool = False
    #: 面板按钮触发的:结果就是面板本身的变化,命令的文字回复一律不发(避免刷屏)
    silent: bool = False
    interaction: Any = None
    created_at: float = field(default_factory=time.time)
    # 内部状态
    responded: bool = False         # 已经用 edit_original_response 回过
    dropped: bool = False           # "思考中…" 已经删掉了,之后只能用 followup
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


#: 设置库(botamusique 表)里记"上次同步的命令内容摘要"的 section;键是 "<应用 ID>:<服务器 ID 或 global>"
SYNC_SECTION = 'command_sync'


def _default_permissions(spec):
    """命令默认谁看得到(服务器可以在"服务器设置 → 整合"里改)。执行时 bot 还会再查一次权限。"""
    if getattr(spec, 'owner_only', False):
        return discord.Permissions(administrator=True)
    if getattr(spec, 'admin', False):
        return discord.Permissions(manage_guild=True)
    return None


def _desc(text_by_locale, default_locale='en'):
    base = text_by_locale.get(default_locale) or text_by_locale['en']
    return app_commands.locale_str(base[:100], i18n={k: v[:100] for k, v in text_by_locale.items()})


# =========================================================================
#   共享连接:一个进程一个
# =========================================================================

#: 交互来自还没准备好的服务器时的回复
STARTING_REPLY = "The bot is still starting, try again in a moment."
#: 没有 Hub 帮忙建会话时(测试 / 单独用连接层),没有会话的服务器里的交互;私信里的交互
HOME_ONLY_REPLY = "This bot only works in its home server for now."
#: 交互来自刚要建会话的服务器时,最多等它准备好多久(秒)
SESSION_WAIT = 1.5


class DiscordClient:
    """整个进程共用的 Discord 连接:登录、事件循环线程、斜杠命令树、持久面板按钮。

    交互(斜杠命令、自动补全、预检查、面板按钮)和网关事件(语音状态、频道 / 身份组 / 服务器变化)
    按 guild_id 交给那个服务器的 GuildLink;没有 GuildLink 的服务器先请 Hub 建会话(on_session_needed)。
    斜杠命令全局注册(bot 主人命令只在 [discord] owner_guild_id),每次启动只在内容变了时才同步;
    [discord] dev_guild_id 另外同步一份,改了立刻生效。
    """

    def __init__(self, token, home_guild_id=None, language='en_US', debug=False, executor=None):
        self.token = token
        self.home_guild_id = int(home_guild_id) if home_guild_id else None
        self.default_locale = {'zh_CN': 'zh-CN', 'ja_JP': 'ja'}.get(language, 'en')
        if debug:
            # discord.py 的调试日志也写进 bot 的日志(根 logger 只显示 WARNING 以上)
            dlog = logging.getLogger("discord")
            dlog.setLevel(logging.DEBUG)
            for handler in log.handlers:
                dlog.addHandler(handler)
        if executor is None:
            from .executor import KeyedExecutor
            executor = KeyedExecutor(name='Discord')
        #: 回调(on_command 等)在这里按 (guild_id, 'evt') 串行执行,不在事件循环线程里
        self.executor = executor

        intents = discord.Intents.none()
        intents.guilds = True        # 频道列表、角色
        intents.voice_states = True  # 谁在哪个语音频道;连语音也需要
        self.client = discord.AutoShardedClient(intents=intents, allowed_mentions=discord.AllowedMentions.none())
        self._tree = app_commands.CommandTree(self.client)
        self._tree.on_error = self._on_tree_error
        for handler in (self.on_ready, self.on_shard_ready, self.on_voice_state_update,
                        self.on_guild_channel_create, self.on_guild_channel_delete, self.on_guild_channel_update,
                        self.on_guild_update, self.on_guild_join, self.on_guild_remove,
                        # 身份组权限变了,"能不能进这个频道"也跟着变
                        self.on_guild_role_create, self.on_guild_role_update, self.on_guild_role_delete):
            self.client.event(handler)
        # 预检查要在 Discord 的 3 秒内答复,不和自动补全 / aiohttp 的 DNS 查询抢默认线程池
        self._precheck_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="Precheck")
        self._autocomplete_pool = concurrent.futures.ThreadPoolExecutor(max_workers=4,
                                                                        thread_name_prefix="Autocomplete")

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._closed = threading.Event()
        self._error: Optional[BaseException] = None
        self._close_reason = ''
        self._synced = False
        self._panel_view: Any = None    # 持久按钮(on_ready 里建,View 要在事件循环里创建)

        self._links: Dict[int, 'GuildLink'] = {}
        self._specs: List[Tuple[str, Any]] = []
        self._spec_by_key: Dict[str, Any] = {}
        # 命令注册(register_commands 设置)
        self.owner_guild_id: Optional[int] = None
        self.dev_guild_id: Optional[int] = None
        self._sync_state: Any = None
        #: GuildLink.set_activity 汇总到这里(Hub 决定账号显示什么);没设置就直接改状态
        self.on_activity: Optional[Callable[[Optional[int], Optional[str], str], None]] = None
        #: 交互来自还没有会话的服务器:请 Hub 建一个(在事件循环里调用,必须马上返回)。
        #: 返回 None = 已经在建 / 已经有了;返回文字 = 拒绝理由(不允许的服务器、会话数到上限……)
        self.on_session_needed: Optional[Callable[[int], Optional[str]]] = None
        #: bot 被拉进 / 移出服务器(在事件循环里调用,要马上返回)
        self.on_guild_joined: Optional[Callable[[int], None]] = None
        self.on_guild_removed: Optional[Callable[[int], None]] = None

    # ---- 生命周期 ----------------------------------------------------------

    def register_commands(self, named_specs, owner_guild_id=None, dev_guild_id=None, sync_state=None):
        """[(slash 名, Spec)];必须在 connect() 之前调用。

        命令注册成全局的(每个服务器都有)。bot 主人命令(spec.owner_only)只注册在 owner_guild_id;
        没配就也注册成全局的,但默认只有"管理员"权限的人看得到(执行时 bot 还会核对是不是主人)。
        dev_guild_id:另外同步一份到这个服务器,改了命令立刻生效(全局命令要等 Discord 传播)。
        sync_state:有 get/set 的设置库(database.SettingsDatabase),记着上次同步的内容,没变就不同步。"""
        self._specs = list(named_specs)
        self._spec_by_key = {spec.key: (name, spec) for name, spec in self._specs}
        self.owner_guild_id = int(owner_guild_id) if owner_guild_id else None
        self.dev_guild_id = int(dev_guild_id) if dev_guild_id else None
        self._sync_state = sync_state
        owner_guild = discord.Object(id=self.owner_guild_id) if self.owner_guild_id else None
        for name, spec in self._specs:
            command = self._build_command(name, spec)
            if getattr(spec, 'owner_only', False) and owner_guild is not None:
                self._tree.add_command(command, guild=owner_guild)
            else:
                self._tree.add_command(command)
        if self.dev_guild_id:
            self._tree.copy_global_to(guild=discord.Object(id=self.dev_guild_id))

    def connect(self, timeout=60):
        """登录并等到 guild 数据同步完。失败时抛异常(token 错误、超时……)。"""
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
            for link in list(self._links.values()):
                link._pcm.close()

    async def _main(self):
        self._loop = asyncio.get_running_loop()
        await self._tree.set_translator(_Translator())
        async with self.client:
            await self.client.start(self.token, reconnect=True)

    def close(self):
        """离开所有语音频道、清掉频道状态,然后断开。"""
        loop = self._loop
        if loop is not None and not loop.is_closed():
            try:
                asyncio.run_coroutine_threadsafe(self._shutdown(), loop).result(timeout=10)
            except Exception:
                pass
        self._closed.set()
        for link in list(self._links.values()):
            link._pcm.close()

    async def _shutdown(self):
        for link in list(self._links.values()):
            try:
                await link._shutdown_voice()
            except Exception:
                log.debug("discord: could not leave voice in %s", link.guild_id, exc_info=True)
        await self.client.close()

    @property
    def alive(self):
        """连接还在。discord.py 自己会断线重连;只有彻底退出(token 失效等)才是 False。"""
        return not self._closed.is_set()

    @property
    def close_reason(self):
        return self._close_reason

    @property
    def loop(self):
        return self._loop

    @property
    def user(self):
        return self.client.user

    # ---- 服务器 ------------------------------------------------------------

    def add_link(self, link: 'GuildLink'):
        """登记一个服务器的 GuildLink:之后这个服务器的交互和事件都交给它。"""
        self._links[link.guild_id] = link
        try:
            self.call(self._attach(link), timeout=15)
        except Exception:
            log.warning("discord: could not take the first snapshot of %s", link.guild_id, exc_info=True)
        return link

    async def _attach(self, link):
        link._me_id = self.client.user.id if self.client.user else None
        link._rebuild()

    def remove_link(self, guild_id):
        return self._links.pop(int(guild_id), None)

    def link(self, guild_id) -> Optional['GuildLink']:
        return self._links.get(int(guild_id)) if guild_id else None

    def links(self) -> List['GuildLink']:
        return list(self._links.values())

    def guild_ids(self) -> List[int]:
        return [g.id for g in list(self.client.guilds)]

    def humans_in(self, guild_id, channel_id):
        """语音频道里有几个真人(不算 bot)。还没有会话的服务器也能查(重启后决定要不要回去)。"""
        try:
            guild = self.client.get_guild(int(guild_id))
            channel = guild.get_channel(int(channel_id)) if guild is not None else None
        except (TypeError, ValueError):
            return 0
        if channel is None or not hasattr(channel, 'voice_states'):
            return 0
        count = 0
        for uid in list(channel.voice_states):
            member = guild.get_member(uid)
            if member is not None and not member.bot:
                count += 1
        return count

    def guild_info(self, guild_id):
        """{'id', 'name', 'icon'}(icon 是 CDN 地址,没有图标为 '');bot 不在这个服务器返回 None。"""
        try:
            guild = self.client.get_guild(int(guild_id))
        except (TypeError, ValueError):
            return None
        if guild is None:
            return None
        icon = getattr(guild, 'icon', None)
        return {'id': str(guild.id), 'name': guild.name, 'icon': icon.url if icon is not None else ''}

    def fetch_member(self, guild_id, user_id):
        """REST 查 user 是不是服务器成员(不需要 members intent)。是 True,不是 False,查不了 None。"""
        async def fetch():
            guild = self.client.get_guild(int(guild_id))
            if guild is None:
                return False
            try:
                await guild.fetch_member(int(user_id))
                return True
            except discord.NotFound:
                return False

        try:
            result = self.call(fetch(), timeout=10)
        except Exception:
            log.debug("discord: could not look up member %s of %s", user_id, guild_id, exc_info=True)
            return None
        return result if isinstance(result, bool) else None

    # ---- 线程桥 ------------------------------------------------------------

    def call(self, coro, timeout=30.0):
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

    def emit(self, key, fn, *args):
        """在共享线程池里执行回调;同一个 key 按顺序。"""
        try:
            self.executor.submit(key, fn, *args)
        except RuntimeError:
            log.debug("discord: dropped %s, shutting down", getattr(fn, '__name__', fn))

    # ---- 状态(整个账号一个) -------------------------------------------------

    def report_activity(self, guild_id, text, state=''):
        hook = self.on_activity
        if hook is not None:
            hook(guild_id, text, state)
        else:
            self.set_presence(text, state)

    def set_presence(self, text, state=''):
        """bot 的状态:"正在听 {text}",第二行 state(歌手);text 为 None 清除。
        bot 账号的活动 Discord 只显示 name 和 state 两行:details、时间戳(进度条)、图片都不显示。"""
        activity = None
        if text:
            activity = discord.Activity(type=discord.ActivityType.listening, name=text[:128],
                                        state=(state or '')[:128] or None)
        try:
            self.call(self.client.change_presence(activity=activity), timeout=10)
        except Exception:
            log.debug("discord: could not change presence", exc_info=True)

    # ---- discord.py 事件 ----------------------------------------------------

    async def on_ready(self):
        if self.home_guild_id is None:
            guilds = list(self.client.guilds)
            if not guilds:
                log.error("discord: the bot is not in any server yet; invite it first (see README)")
            else:
                self.home_guild_id = guilds[0].id
                if len(guilds) > 1:
                    log.warning("discord: the bot is in %d servers but runs in single-server mode; "
                                "serving %s (%s). Set [discord] guild_id to choose.",
                                len(guilds), guilds[0].name, guilds[0].id)
        home = self.client.get_guild(self.home_guild_id) if self.home_guild_id else None
        if home is None and self.home_guild_id is not None:
            log.error("discord: server %s not found; is the bot invited to it?", self.home_guild_id)
        self._check_links()
        if not self._synced:
            self._synced = True
            await self._sync_commands()
        if self._panel_view is None:
            # 持久按钮:custom_id 固定,bot 重启后旧面板上的按钮照样能用;所有服务器共用一个 View
            self._panel_view = _PanelView(self)
            self.client.add_view(self._panel_view)
        log.info("discord: logged in as %s, serving %s", self.client.user, home.name if home else '-')
        self._ready.set()

    # ---- 命令同步 ----------------------------------------------------------

    def _sync_targets(self):
        """[(guild id 或 None = 全局)]:全局、bot 主人的服务器、开发服务器;再加上以前(只同步到主服务器时)
        的主服务器,同步一份空的过去把旧的服务器命令清掉,否则那里每条命令会出现两次。"""
        targets = [None]
        for gid in (self.owner_guild_id, self.dev_guild_id, getattr(self, 'home_guild_id', None)):
            if gid and gid not in targets:
                targets.append(gid)
        return targets

    async def _command_digest(self, guild_id):
        """这一份命令(全局或某个服务器)同步给 Discord 的内容的摘要。"""
        guild = discord.Object(id=guild_id) if guild_id else None
        translator = _Translator()
        payload = [await command.get_translated_payload(self._tree, translator)
                   for command in self._tree.get_commands(guild=guild)]
        payload.sort(key=lambda p: p.get('name', ''))
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode('utf-8')).hexdigest()

    def _sync_key(self, guild_id):
        app = self.client.application_id or getattr(self.client.user, 'id', None) or 0
        return f"{app}:{guild_id or 'global'}"

    async def _sync_commands(self):
        """每次启动调用一次:内容和上次同步的一样就跳过(同步有频率限制,全局命令改了要等 Discord 传播)。"""
        state = self._sync_state
        for guild_id in self._sync_targets():
            where = f"server {guild_id}" if guild_id else "all servers"
            try:
                digest = await self._command_digest(guild_id)
                key = self._sync_key(guild_id)
                if state is not None and state.get(SYNC_SECTION, key, fallback=None) == digest:
                    log.info("discord: slash commands for %s unchanged, not syncing", where)
                    continue
                synced = await self._tree.sync(guild=discord.Object(id=guild_id) if guild_id else None)
                if state is not None:
                    state.set(SYNC_SECTION, key, digest)
                log.info("discord: synced %d slash commands to %s", len(synced), where)
            except Exception:
                log.exception("discord: could not sync slash commands to %s", where)

    async def on_shard_ready(self, shard_id):
        # 单个分片重新 IDENTIFY 时不一定再触发 on_ready
        self._check_links()

    def _check_links(self):
        for link in list(self._links.values()):
            try:
                link._after_ready()
            except Exception:
                log.exception("discord: reconnect check for %s failed", link.guild_id)

    async def on_voice_state_update(self, member, before, after):
        link = self._links.get(member.guild.id)
        if link is not None:
            await link.on_voice_state_update(member, before, after)
            return
        # 没有会话的服务器:别人进出语音不建会话;只有 bot 自己出现在语音里(重启前留下的状态等)才建
        me = self.client.user
        if me is not None and member.id == me.id and getattr(after, 'channel', None) is not None:
            self._need_session(member.guild.id)

    def _need_session(self, guild_id):
        hook = self.on_session_needed
        if hook is None:
            return HOME_ONLY_REPLY
        try:
            return hook(guild_id)
        except Exception:
            log.exception("discord: could not start a session for %s", guild_id)
            return STARTING_REPLY

    async def on_guild_join(self, guild):
        log.info("discord: joined server %s (%s)", guild.name, guild.id)
        if self.on_guild_joined is not None:
            self.on_guild_joined(guild.id)

    async def on_guild_remove(self, guild):
        log.info("discord: removed from server %s (%s)", getattr(guild, 'name', '?'), guild.id)
        if self.on_guild_removed is not None:
            self.on_guild_removed(guild.id)

    def _rebuild(self, guild_id):
        link = self._links.get(guild_id)
        if link is not None:
            link._rebuild()

    async def on_guild_channel_create(self, channel):
        self._rebuild(channel.guild.id)

    async def on_guild_channel_delete(self, channel):
        self._rebuild(channel.guild.id)

    async def on_guild_channel_update(self, before, after):
        self._rebuild(after.guild.id)

    async def on_guild_update(self, before, after):
        self._rebuild(after.id)

    async def on_guild_role_create(self, role):
        self._rebuild(role.guild.id)

    async def on_guild_role_update(self, before, after):
        self._rebuild(after.guild.id)

    async def on_guild_role_delete(self, role):
        self._rebuild(role.guild.id)

    # ---- 交互路由 ----------------------------------------------------------

    async def _refuse(self, interaction, text=None):
        if text is None:
            gid = interaction.guild_id
            text = STARTING_REPLY if gid is not None and gid == self.home_guild_id else HOME_ONLY_REPLY
        await interaction.response.send_message(text, ephemeral=True)

    async def _link_for(self, interaction):
        """交互该交给哪个 GuildLink。还没有会话的服务器:请 Hub 建一个,等它在 SESSION_WAIT 秒内
        准备好(Discord 要求 3 秒内答复,后面还有预检查);等不到回"还在启动",被拒绝回理由。
        已经答复过的返回 None。"""
        gid = interaction.guild_id
        if gid is None:
            await self._refuse(interaction, HOME_ONLY_REPLY)
            return None
        loop = asyncio.get_running_loop()
        deadline = loop.time() + SESSION_WAIT
        requested = False
        while True:
            link = self._links.get(gid)
            if link is not None and getattr(link, 'ready', True):
                return link
            if link is None and not requested:
                # 没有会话,或者正在休眠的会话刚摘下 GuildLink
                if self.on_session_needed is None:
                    await self._refuse(interaction)
                    return None
                requested = True
                refusal = self._need_session(gid)
                if refusal:
                    await self._refuse(interaction, refusal)
                    return None
            if loop.time() >= deadline:
                break
            await asyncio.sleep(0.05)
        if link is not None:
            return link  # 会话还在读状态:GuildLink 自己回"还在启动"
        await self._refuse(interaction, STARTING_REPLY)
        return None

    async def _invoke(self, spec, interaction, kwargs, ephemeral=None, silent=False):
        link = await self._link_for(interaction)
        if link is not None:
            await link._invoke(spec, interaction, kwargs, ephemeral=ephemeral, silent=silent)

    async def _on_panel_button(self, interaction, action):
        link = await self._link_for(interaction)
        if link is not None:
            await link._on_panel_button(interaction, action)

    async def _on_tree_error(self, interaction, error):
        log.error("discord: slash command error: %s", error, exc_info=error)
        try:
            if interaction.response.is_done():
                await interaction.followup.send("Something went wrong.", ephemeral=True)
            else:
                await interaction.response.send_message("Something went wrong.", ephemeral=True)
        except Exception:
            pass

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

        client = self

        async def callback(interaction: discord.Interaction, **kwargs):
            await client._invoke(spec, interaction, kwargs)

        callback.__signature__ = inspect.Signature(params)
        callback.__name__ = f"slash_{spec.key}"
        callback.__qualname__ = callback.__name__
        callback.__discord_app_commands_param_description__ = descriptions
        command = app_commands.Command(name=name, description=_desc(spec.desc, self.default_locale),
                                       callback=callback)
        command.guild_only = True
        command.default_permissions = _default_permissions(spec)
        for opt in spec.options:
            if opt.autocomplete:
                command.autocomplete(opt.name)(self._make_autocomplete(opt))
        return command

    def _make_autocomplete(self, opt):
        client = self

        async def autocomplete(interaction: discord.Interaction, current: str):
            link = client._links.get(interaction.guild_id) if interaction.guild_id is not None else None
            handler = link.on_autocomplete if link is not None else None
            if handler is None:
                if link is None and interaction.guild_id is not None and client.on_session_needed is not None:
                    client._need_session(interaction.guild_id)  # 有人在打命令了:先把会话建起来
                return []
            ctx = link._context(None, interaction, {})
            try:
                results = await asyncio.wait_for(
                    asyncio.get_running_loop().run_in_executor(client._autocomplete_pool, handler,
                                                               opt.autocomplete, ctx, current or ''),
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
                    value = str(value)
                    if len(value) > 100:
                        continue  # Discord 的选项值最多 100 字符;截断后可能选中别的条目,干脆不列
                choices.append(app_commands.Choice(name=str(label)[:100] or str(value), value=value))
            return choices

        return autocomplete


# =========================================================================
#   一个服务器
# =========================================================================

class GuildLink:
    """一个服务器(guild)的连接视图:语音、音频缓冲、成员 / 频道快照、公告频道、面板、语音频道状态。

    接口和以前的单服务器 DiscordLink 一样,DJBot / NowPlaying 不用关心底下是共享连接。
    回调在共享线程池里按 (guild_id, 'evt') 依次调用(不是事件循环线程)。
    """

    def __init__(self, client: DiscordClient, guild_id, announce_channel_id=None, admin_ids=(),
                 admin_permission=True, self_deaf=True, bitrate=0):
        self._dc = client
        self.guild_id = int(guild_id) if guild_id else None
        self.announce_channel_id = int(announce_channel_id) if announce_channel_id else None
        self.admin_ids = {int(x) for x in admin_ids}
        self.admin_permission = admin_permission
        self.self_deaf = self_deaf
        self.bitrate = int(bitrate or 0)

        self._closed = threading.Event()
        self._close_reason = ''

        self._users: Mapping[int, User] = {}
        self._channels: Dict[int, dict] = {}
        self._me_id: Optional[int] = None
        self._guild_name = ''
        self._last_command_channel: Optional[int] = None

        self._pcm = PCMStream()
        self._volume = 1.0
        self._cutting = False

        self.on_command: Optional[Callable[[CommandContext], None]] = None
        self.on_precheck: Optional[Callable[[CommandContext], Optional[str]]] = None
        self.on_autocomplete: Optional[Callable[[str, CommandContext, str], List[Tuple[str, str]]]] = None
        self.on_user_joined: Optional[Callable[[User], None]] = None
        self.on_user_updated: Optional[Callable[[User, frozenset], None]] = None
        self.on_user_left: Optional[Callable[[User], None]] = None
        self.on_self_moved: Optional[Callable[[Optional[int], Optional[int]], None]] = None
        #: 面板按钮 -> (命令 key, 参数);由 NowPlaying 提供。要很快返回(在事件循环里调用)
        self.on_panel_button: Optional[Callable[[str], Optional[Tuple[str, Dict[str, Any]]]]] = None
        #: 面板按钮的命令已经交给线程池:让面板马上刷新,不等下一秒的轮询
        self.on_panel_pressed: Optional[Callable[[], None]] = None

        # "正在播放"面板
        self._panel_msg: Any = None             # discord.Message / PartialMessage
        self._panel_adopted: Optional[Tuple[int, int]] = None  # 上次运行留下的 (频道, 消息)
        self._panel_cover: Optional[bytes] = None
        # 语音频道状态:(频道 id, 文字),是我们设置的
        self._voice_status: Tuple[Optional[int], str] = (None, '')
        self._voice_status_warned = False

    # ---- 共享连接 ----------------------------------------------------------

    @property
    def _client(self):
        return self._dc.client

    @property
    def _loop(self):
        return self._dc.loop

    def _call(self, coro, timeout=30.0):
        return self._dc.call(coro, timeout=timeout)

    def _emit(self, fn, *args):
        self._dc.emit((self.guild_id, 'evt'), fn, *args)

    def close(self, reason='closed'):
        """只断开这个服务器(会话休眠 / bot 被移出服务器):先从共享连接上摘下(之后的交互和事件
        不再交给它),再离开语音、清掉语音频道状态;面板 / 状态不再更新。共享连接不受影响。"""
        self._close_reason = reason
        self._closed.set()
        if self._dc.link(self.guild_id) is self:
            self._dc.remove_link(self.guild_id)
        for name in ('on_command', 'on_precheck', 'on_autocomplete', 'on_user_joined', 'on_user_updated',
                     'on_user_left', 'on_self_moved', 'on_panel_button', 'on_panel_pressed'):
            setattr(self, name, None)
        try:
            self._call(self._shutdown_voice(), timeout=10)
        except Exception:
            log.debug("discord: could not leave voice in %s", self.guild_id, exc_info=True)
        self._pcm.close()

    @property
    def closed(self):
        return self._closed.is_set()

    @property
    def ready(self):
        """会话读完状态、开始接命令了(之前来的命令回"还在启动")。"""
        return self.on_command is not None and not self._closed.is_set()

    async def _shutdown_voice(self):
        guild = self._guild()
        await self._clear_voice_status()
        if guild is not None and guild.voice_client is not None:
            try:
                await guild.voice_client.disconnect(force=True)
            except Exception:
                pass

    @property
    def alive(self):
        """连接还在。discord.py 自己会断线重连;只有彻底退出(token 失效等)才是 False。"""
        return not self._closed.is_set() and self._dc.alive

    @property
    def close_reason(self):
        return self._close_reason or self._dc.close_reason

    # ---- discord.py 事件(由 DiscordClient 转过来) ----------------------------

    def _guild(self) -> Optional[discord.Guild]:
        if self.guild_id is not None:
            return self._client.get_guild(self.guild_id)
        return None

    def _own_channel(self, channel_id):
        """按 id 取频道,只认本服务器的(公告频道配置错、面板记录串了都不能发到别的服务器去)。"""
        if not channel_id:
            return None
        channel = self._client.get_channel(int(channel_id))
        if channel is None:
            return None
        guild = getattr(channel, 'guild', None)
        if guild is None or getattr(guild, 'id', None) != self.guild_id:
            log.debug("discord: channel %s is not in server %s, ignored", channel_id, self.guild_id)
            return None
        return channel

    def _after_ready(self):
        """(重新)连上网关之后:刷新快照,检查语音连接是否还在。"""
        self._me_id = self._client.user.id if self._client.user else self._me_id
        old_cid = self.my_channel_id
        self._rebuild()
        new_cid = self.my_channel_id
        if old_cid != new_cid:
            # 网关重新 IDENTIFY 时 discord.py 会清掉 voice client:bot 已经不在语音里了,
            # 断开音频输出(否则播放线程卡在写缓冲上),并让上层按"被断开"处理
            log.warning("discord: voice connection lost after a gateway reconnect (%s)", self.guild_id)
            self._on_self_voice(new_cid)
            if self.on_self_moved:
                self._emit(self.on_self_moved, old_cid, new_cid)

    async def on_voice_state_update(self, member, before, after):
        if member.guild.id != self.guild_id:
            return
        old_users = self._users
        self._rebuild_users()
        new_users = self._users
        # 整份快照对比:几条事件挤在一起时,前一个处理函数重建的快照可能已经包含了后一条的变化,
        # 只看 member.id 会漏掉事件。bot 自己的变化先处理。
        ids = sorted(set(old_users) | set(new_users), key=lambda uid: uid != self._me_id)
        for uid in ids:
            old, new = old_users.get(uid), new_users.get(uid)
            if uid == self._me_id:
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
            elif old is not None and new is not None and old != new:
                changed = frozenset(k for k in ('channel_id', 'self_mute', 'self_deaf', 'mute', 'deaf', 'name')
                                    if getattr(old, k) != getattr(new, k))
                if changed and self.on_user_updated:
                    self._emit(self.on_user_updated, new, changed)

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

    def text_channels(self):
        """bot 能发言的文字频道(Web 上选公告频道用):[{'id': str, 'name': str}],按频道列表的顺序。"""
        async def collect():
            guild = self._guild()
            if guild is None:
                return []
            me = guild.me
            out = []
            for channel in sorted(guild.text_channels, key=lambda c: (c.category.position if c.category else -1,
                                                                       c.position)):
                if me is not None:
                    perms = channel.permissions_for(me)
                    if not (perms.view_channel and perms.send_messages):
                        continue
                out.append({'id': str(channel.id), 'name': channel.name})
            return out

        try:
            return self._call(collect(), timeout=10) or []
        except Exception:
            log.debug("discord: could not list the text channels of %s", self.guild_id, exc_info=True)
            return []

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
            # 走之前清掉旧频道的状态(离开后就没权限改它了)
            await self._clear_voice_status()
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
        await self._clear_voice_status()
        if guild is not None and guild.voice_client is not None:
            # force=True:语音正在重连时 force=False 会提前返回,bot 留在频道里成了"幽灵"
            await guild.voice_client.disconnect(force=True)
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
        if vc is None:
            # 根本没有语音连接(网关重连后被清掉等):断开音频输出,播放线程改为按实时速度丢弃
            self._on_self_voice(None)
            return
        if not vc.is_connected():
            if attempt < 100:
                # 刚 connect / move_to,语音握手还没完成
                self._loop.call_later(0.1, self._start_player, attempt + 1)
            else:
                self._pcm.player_unavailable()
            return
        if vc.is_playing():
            player = getattr(vc, '_player', None)
            stale = player is not None and not player.is_alive()
            if vc.source is self._pcm and not stale and attempt < 20:
                # 上一个 AudioPlayer 正在退出(read 刚返回 b'')
                self._loop.call_later(0.02, self._start_player, attempt + 1)
                return
            # AudioPlayer 线程已经退出却还占着(语音重连超时会这样),或者等不到它退出:清掉重开
            vc.stop()
        bitrate = self.bitrate or int((vc.channel.bitrate or 64000) / 1000)
        bitrate = min(max(bitrate, 16), 512)  # Opus 编码器只接受 16–512 kbps
        try:
            vc.play(self._pcm, after=self._player_after, application='audio', bitrate=bitrate,
                    signal_type='music')
        except discord.ClientException:
            if attempt < 20:
                self._loop.call_later(0.05, self._start_player, attempt + 1)
            else:
                self._pcm.player_unavailable()
        except Exception:
            # OpusNotLoaded(没装 libopus)等:不能让 _playing 一直是 True,否则播放线程卡死
            log.exception("discord: could not start playback")
            self._pcm.player_unavailable()

    def _player_after(self, error):
        if error is not None:
            log.warning("discord: audio player stopped with an error: %s", error)
        loop = self._loop
        if loop is not None and not loop.is_closed():
            loop.call_soon_threadsafe(self._clear_stale_player)
        self._pcm.player_stopped()

    def _clear_stale_player(self):
        """AudioPlayer 没走 stop() 就退出时(等语音重连超时),voice client 里还挂着它,
        is_playing() 一直是 True,下次 play() 就开不了。"""
        guild = self._guild()
        vc = guild.voice_client if guild is not None else None
        player = getattr(vc, '_player', None) if vc is not None else None
        if player is not None and not player.is_alive():
            vc.stop()

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
        if ctx.silent:
            # 面板按钮:交互的"原始消息"就是面板,编辑它会把面板换成这句回复;结果看面板就行
            log.debug("discord: dropped a reply to a panel button: %s", message)
            return
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
            if ephemeral:
                # 只给本人看的内容(比如 /web 的登录链接)不能改发到公开频道
                log.warning("discord: dropped a private reply to /%s: the interaction expired", ctx.command)
                return
            channel = self._own_channel(ctx.channel_id)
            if channel is not None:
                await channel.send(content, suppress_embeds=True)
            return
        if ctx._finish_handle is not None:
            ctx._finish_handle.cancel()
            ctx._finish_handle = None
        if not ctx.responded and not ctx.dropped and ephemeral == ctx.ephemeral:
            ctx.responded = True
            try:
                await interaction.edit_original_response(content=content)
                return
            except discord.NotFound:
                ctx.dropped = True  # "思考中…" 已经没了,改用 followup
        await interaction.followup.send(content, ephemeral=ephemeral, suppress_embeds=True)

    def finish(self, ctx: CommandContext):
        """命令处理完。还没回复过就过一会儿删掉 "思考中…"(期间有回复就不删)。"""
        ctx.finished = True
        loop = self._loop
        if loop is None or loop.is_closed() or ctx.interaction is None or ctx.silent:
            # silent:没有 "思考中…" 可删;delete_original_response 删的会是面板本身
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
        ctx.dropped = True  # 之后的回复(后台线程)走 followup,不能再编辑已删掉的消息
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

    def _announce_channels(self, need=(), prefer=()):
        """能发公告的频道,按优先级:配置的 announce_channel → 最近一次发命令的频道 → prefer →
        bot 所在语音频道的文字区。need:除了"看得到、能发言"之外还要的权限(如 embed_links)。"""
        guild = self._guild()
        me = guild.me if guild is not None else None
        tried = set()
        for cid in (self.announce_channel_id, self._last_command_channel, *prefer, self.my_channel_id):
            if not cid or cid in tried:
                continue
            tried.add(cid)
            channel = self._own_channel(cid)
            if channel is None or not hasattr(channel, 'send'):
                continue
            # 斜杠命令在 bot 没权限发言的频道里也能用(交互回复不受频道权限限制),公告却发不出去
            if me is not None and hasattr(channel, 'permissions_for'):
                perms = channel.permissions_for(me)
                if not (perms.view_channel and perms.send_messages):
                    continue
                if not all(getattr(perms, p, True) for p in need):
                    continue
            yield channel

    def _may(self, channel, permission):
        guild = self._guild()
        me = guild.me if guild is not None else None
        if me is None or not hasattr(channel, 'permissions_for'):
            return True
        return bool(getattr(channel.permissions_for(me), permission, True))

    async def _announce(self, text):
        for channel in self._announce_channels():
            try:
                for chunk in split_message(text):
                    await channel.send(chunk, suppress_embeds=True)
                return
            except discord.Forbidden:
                continue
        log.debug("discord: no channel to post announcements in")

    # ---- "正在播放"面板 -----------------------------------------------------
    #
    # 面板内容是 now_playing.build_panel() 产出的 dict:author / title / url / description / fields /
    # footer / color / has_cover / buttons,可选的 cover(JPEG 字节,封面换了才带)。

    @property
    def panel_ref(self) -> Optional[Tuple[int, int]]:
        """面板消息的 (频道 id, 消息 id),bot 重启后用它接着编辑同一条。"""
        msg = self._panel_msg
        if msg is None:
            return None
        return msg.channel.id, msg.id

    def panel_adopt(self, channel_id, message_id):
        self._panel_adopted = (int(channel_id), int(message_id))

    def panel_show(self, panel, new_track=False):
        """显示 / 更新面板。new_track:换歌了,面板已经被聊天顶上去的话删掉重发到最底下。返回是否成功。"""
        if self._closed.is_set():
            return False
        try:
            return bool(self._call(self._panel_show(panel, new_track), timeout=30))
        except Exception:
            log.warning("discord: could not update the now-playing panel", exc_info=True)
            return False

    def panel_end(self, panel):
        """播放结束:面板换成 panel 的内容并去掉按钮;panel 为 None 时只去掉按钮。"""
        if self._closed.is_set():
            return False
        try:
            return bool(self._call(self._panel_end(panel), timeout=30))
        except Exception:
            log.warning("discord: could not finish the now-playing panel", exc_info=True)
            return False

    def _take_adopted_panel(self):
        if self._panel_msg is not None or self._panel_adopted is None:
            return
        channel_id, message_id = self._panel_adopted
        self._panel_adopted = None
        channel = self._own_channel(channel_id)
        if channel is not None and hasattr(channel, 'get_partial_message'):
            self._panel_msg = channel.get_partial_message(message_id)

    def _panel_embed(self, panel):
        embed = discord.Embed(title=_clip(panel.get('title'), 256) or None,
                              url=panel.get('url') or None,
                              description=_clip(panel.get('description'), 4096) or None,
                              color=panel.get('color'))
        if panel.get('author'):
            embed.set_author(name=_clip(panel['author'], 256))
        for name, value in panel.get('fields') or ():
            embed.add_field(name=_clip(name, 256), value=_clip(value, 1024), inline=True)
        if panel.get('footer'):
            embed.set_footer(text=_clip(panel['footer'], 2048))
        if panel.get('has_cover') and self._panel_cover:
            embed.set_thumbnail(url=f'attachment://{PANEL_COVER_NAME}')
        return embed

    def _panel_channel(self):
        """面板发在哪。网页点歌时没有"最近发命令的频道":先留在面板原来的频道(重启后也记得),
        再用服务器的系统频道,最后才是语音频道自带的文字区(大家一般不看那里)。"""
        prefer = []
        if self._panel_msg is not None:
            prefer.append(self._panel_msg.channel.id)
        guild = self._guild()
        system = getattr(guild, 'system_channel', None) if guild is not None else None
        if system is not None:
            prefer.append(system.id)
        return next(self._announce_channels(need=('embed_links',), prefer=prefer), None)

    def _cover_file(self):
        return discord.File(BytesIO(self._panel_cover), filename=PANEL_COVER_NAME)

    async def _panel_is_latest(self, msg, channel):
        """面板还是频道里最新的一条消息吗(否则换歌时删掉重发,免得面板埋在聊天记录里)。"""
        if channel is None or msg.channel.id != channel.id:
            return False
        try:
            async for latest in channel.history(limit=1):
                return latest.id == msg.id
        except discord.HTTPException:
            return False
        return False

    async def _panel_show(self, panel, new_track):
        if 'cover' in panel:
            self._panel_cover = panel['cover']
        self._take_adopted_panel()
        msg = self._panel_msg
        target = None
        if new_track or msg is None:
            target = self._panel_channel()
            if msg is not None and not await self._panel_is_latest(msg, target):
                try:
                    await msg.delete()
                except discord.HTTPException:
                    pass
                self._panel_msg = msg = None
        view = self._dc._panel_view if panel.get('buttons') else None

        if msg is not None:
            kwargs = {'embed': self._panel_embed(panel), 'view': view}
            if 'cover' in panel:
                kwargs['attachments'] = [self._cover_file()] if self._panel_cover else []
            try:
                self._panel_msg = await msg.edit(**kwargs)
                return True
            except discord.NotFound:
                self._panel_msg = None  # 被人删了:下面重发一条
            except discord.HTTPException as e:
                log.warning("discord: could not edit the now-playing panel: %s", e)
                return False

        if target is None:
            target = self._panel_channel()
        if target is None:
            log.debug("discord: no channel to post the now-playing panel in")
            return False
        attach = bool(self._panel_cover) and self._may(target, 'attach_files')
        embed = self._panel_embed(panel if attach else {**panel, 'has_cover': False})
        kwargs = {'embed': embed}
        if view is not None:
            kwargs['view'] = view
        if attach:
            kwargs['file'] = self._cover_file()
        self._panel_msg = await target.send(**kwargs)
        log.info("discord: now-playing panel posted in #%s", getattr(target, 'name', target.id))
        return True

    async def _panel_end(self, panel):
        self._take_adopted_panel()
        msg = self._panel_msg
        if msg is None:
            return True
        try:
            if panel is None:
                await msg.edit(view=None)
            else:
                self._panel_msg = await msg.edit(embed=self._panel_embed(panel), view=None)
        except discord.NotFound:
            self._panel_msg = None
        except discord.HTTPException as e:
            log.warning("discord: could not finish the now-playing panel: %s", e)
            return False
        return True

    async def _on_panel_button(self, interaction, action):
        """面板按钮:换算成命令,和斜杠命令走同一套预检查 / 处理流程。不发回复,结果体现在面板上。"""
        resolver = self.on_panel_button
        resolved = resolver(action) if resolver is not None else None
        entry = self._dc._spec_by_key.get(resolved[0]) if resolved else None
        if entry is None:
            await interaction.response.send_message(STARTING_REPLY, ephemeral=True)
            return
        await self._invoke(entry[1], interaction, resolved[1], silent=True)

    # ---- 语音频道状态 -------------------------------------------------------

    def set_voice_status(self, text):
        """bot 所在语音频道的状态文字(频道名下面那行);'' 清除。没权限 / 不在语音里返回 False。"""
        if self._closed.is_set():
            return False
        try:
            return bool(self._call(self._set_voice_status(text), timeout=15))
        except Exception:
            log.debug("discord: could not set the voice channel status", exc_info=True)
            return False

    async def _set_voice_status(self, text):
        guild = self._guild()
        vc = guild.voice_client if guild is not None else None
        channel = vc.channel if vc is not None and vc.is_connected() else None
        if channel is None:
            return False
        if not self._may(channel, 'set_voice_channel_status'):
            if not self._voice_status_warned:
                self._voice_status_warned = True
                log.warning("discord: no 'Set Voice Channel Status' permission in %s, so the song is not "
                            "shown under the voice channel. Re-invite the bot with the link in the README "
                            "or give its role that permission.", channel.name)
            return False
        await self._client.http.edit_voice_channel_status(text or None, channel_id=channel.id)
        self._voice_status = (channel.id, text) if text else (None, '')
        return True

    async def _clear_voice_status(self):
        channel_id, text = self._voice_status
        self._voice_status = (None, '')
        if channel_id is None or not text:
            return
        try:
            await self._client.http.edit_voice_channel_status(None, channel_id=channel_id)
        except discord.HTTPException:
            log.debug("discord: could not clear the voice channel status", exc_info=True)

    def set_activity(self, text, state=''):
        """这个服务器在放什么(text 为 None = 没在放)。账号的状态由 DiscordClient / Hub 汇总所有服务器后决定。"""
        try:
            self._dc.report_activity(self.guild_id, text, state)
        except Exception:
            log.debug("discord: could not report the activity", exc_info=True)

    # ---- 斜杠命令 ----------------------------------------------------------

    def _context(self, spec, interaction, kwargs, ephemeral=None):
        member = interaction.user
        voice = getattr(member, 'voice', None)
        role_ids = tuple(r.id for r in getattr(member, 'roles', ()) or ())
        perms = getattr(member, 'guild_permissions', None)
        is_owner = member.id in self.admin_ids
        is_admin = (is_owner or any(r in self.admin_ids for r in role_ids)
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
            is_owner=bool(is_owner),
            ephemeral=(bool(ephemeral) if ephemeral is not None
                       else bool(spec.ephemeral) if spec is not None else True),
            interaction=interaction,
        )

    async def _invoke(self, spec, interaction, kwargs, ephemeral=None, silent=False):
        """ephemeral:覆盖命令自己的设置。silent:面板按钮,不发任何回复,只确认交互(面板自己会更新);
        被预检查拒绝时仍然只给本人看一句为什么。"""
        if interaction.guild_id is None or interaction.guild_id != self.guild_id:
            await interaction.response.send_message(
                HOME_ONLY_REPLY, ephemeral=True)
            return
        ctx = self._context(spec, interaction, kwargs, ephemeral=True if silent else ephemeral)
        ctx.silent = silent
        if self.on_precheck is not None:
            try:
                refusal = await asyncio.wait_for(
                    asyncio.get_running_loop().run_in_executor(self._dc._precheck_pool, self.on_precheck, ctx),
                    timeout=1.5)
            except Exception:
                # 检查不了就拒绝(否则管理员命令 / 封禁会被绕过);命令本身在 bot 里还会再查一遍权限
                log.exception("discord: precheck for /%s failed", spec.key)
                refusal = "The bot is busy, please try again in a moment."
            if refusal:
                await interaction.response.send_message(html_to_markdown(refusal)[:2000], ephemeral=True)
                return
        if silent:
            # 按钮交互不带 thinking 的 defer = "稍后更新这条消息":不产生任何新消息
            await interaction.response.defer()
        else:
            await interaction.response.defer(ephemeral=ctx.ephemeral, thinking=True)
        if not ctx.ephemeral:
            self._last_command_channel = interaction.channel_id
        if self.on_command is None:
            if not silent:
                await interaction.edit_original_response(content=STARTING_REPLY)
            return
        self._emit(self.on_command, ctx)
        if silent and self.on_panel_pressed is not None:
            self.on_panel_pressed()


def _clip(text, limit):
    text = str(text or '')
    return text if len(text) <= limit else text[:limit - 1] + '…'


#: 面板按钮:(动作, 图标)。custom_id 是 djbot:np:<动作>,重启后旧面板上的按钮照样能点
PANEL_BUTTONS = (('toggle', '⏯️'), ('skip', '⏭️'), ('stop', '⏹️'), ('mode', '🔁'))


class _PanelView(discord.ui.View):
    """所有服务器共用一个:按钮回调按 interaction.guild_id 找到那个服务器的 GuildLink。"""

    def __init__(self, client):
        super().__init__(timeout=None)
        for action, emoji in PANEL_BUTTONS:
            button = discord.ui.Button(emoji=emoji, style=discord.ButtonStyle.secondary,
                                       custom_id=f'djbot:np:{action}')
            button.callback = self._callback(client, action)
            self.add_item(button)

    @staticmethod
    def _callback(client, action):
        async def callback(interaction: discord.Interaction):
            await client._on_panel_button(interaction, action)
        return callback


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
