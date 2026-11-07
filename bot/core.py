# coding=utf-8
import collections
import logging
import time
import traceback

import media.playlist
import util
import variables as var
from constants import tr_cli as tr

from .channels import ChannelMixin
from .discord_link import CommandContext
from .limits import guild_max_volume
from .now_playing import NowPlaying
from .player import PlayerMixin


PLAYBACK_MODES = ("one-shot", "repeat", "single", "random", "autoplay")
#: 服务器设置里的公告频道(频道 id;'' = 不指定)
ANNOUNCE_KEY = 'announce_channel'


def new_queue(mode):
    if mode not in PLAYBACK_MODES:
        raise KeyError(f"Unknown playback mode '{mode}'")
    return media.playlist.get_playlist(mode)


def owner_ids():
    """[bot] admin 里的 ID(用户或身份组,',' 或 ';' 分隔)。"""
    raw = var.config.get('bot', 'admin', fallback='') if var.config is not None else ''
    return {a.strip() for a in (raw or '').replace(';', ',').split(',') if a.strip()}


def _as_float(value, fallback):
    try:
        return float(value) if value is not None else fallback
    except ValueError:
        return fallback


class DJBot(PlayerMixin, ChannelMixin):
    """一个服务器的会话:队列、播放循环、频道跟随、命令处理。连接(GuildLink)和进程级的事
    (信号、看门狗、心跳、Bot 状态汇总)由 bot.hub.Hub 管。"""

    version = 'git'

    def __init__(self, args, link, executor=None, ticker=None, timers=None):
        self.log = logging.getLogger("bot")
        self.cmd_handle = {}
        self.slash_names = {}  # spec.key -> 斜杠命令名(帮助 / 提示文字用)

        # Discord 只收立体声
        self.stereo = True

        self.channel = args.channel if args.channel else var.config.get("discord", "channel")

        var.is_proxified = var.config.getboolean(
            "webinterface", "is_web_proxified")

        # 播放循环该停了(Ctrl-C、/kill,由 Hub 设置)
        self.exit = False

        # Related to ffmpeg thread
        self.thread = None
        self.thread_stderr = None
        self.read_pcm_size = 0
        self.pcm_buffer_size = 0
        self.last_ffmpeg_err = ""
        self._ffmpeg_stderr_lines = collections.deque(maxlen=20)

        # 看门狗和心跳(Hub)看这个时间判断播放循环还活着
        self.last_loop_at = time.time()

        # Play/pause status
        self.is_pause = False
        self.pause_at_id = ""
        self.playhead = -1  # current position in a song.
        self.song_start_at = -1
        self.wait_for_ready = False  # flag for the loop are waiting for download to complete in the other thread

        #
        self.on_interrupting = False
        self._leaving_until = 0.0  # /leave 之后这段时间里的"离开语音"是自己走的,不算被踢
        self._activity = None

        self.link = link
        #: 共享线程池(bot.executor.KeyedExecutor):命令按 (guild_id, 'cmd') 依次处理
        self.executor = executor
        self.ticker = ticker
        #: 共用的定时线程(bot.executor.Timers):跟随检查的防抖
        self.timers = timers
        # 公告频道里的"正在播放"面板 + 语音频道状态
        self.now_playing = NowPlaying(
            self, self.link,
            panel=var.config.getboolean('discord', 'now_playing_panel', fallback=True),
            voice=var.config.getboolean('discord', 'voice_channel_status', fallback=True))

        # ====== Volume ======
        # 先用配置文件的值;服务器自己存的音量 / 播放模式 / 队列连上 Discord 后再读(load_guild_state)
        self.volume_helper = util.VolumeHelper()
        self.volume_helper.set_volume(min(var.config.getfloat('bot', 'volume'),
                                          var.config.getfloat('bot', 'max_volume')))
        self.last_volume_cycle_time = time.time()
        self._guild_state_loaded = False
        self.set_playlist(new_queue(var.config.get('bot', 'playback_mode')))

        assert var.config.get("bot", "when_nobody_in_channel") in ['pause', 'pause_resume', 'stop', 'nothing', ''], \
            "Unknown action for when_nobody_in_channel"

        self._react_to_empty_channel = \
            var.config.get("bot", "when_nobody_in_channel") in ['pause', 'pause_resume', 'stop']

        # Debug use
        self._loop_status = 'Idle'

        self.redirect_ffmpeg_log = var.config.getboolean('debug', 'redirect_ffmpeg_log')

        self._init_follow()
        bots = var.config.get("bot", "when_nobody_in_channel_ignore", fallback="")
        self.bots = set(b.strip() for b in bots.split(',') if b.strip())
        self._humans_in_channel = 0

    def start(self, startup=True):
        """连接(GuildLink)已经就绪:读这个服务器的状态、接上回调、进语音频道。
        register_slash_commands() 之后调用;播放循环(loop)由 Hub 另开线程跑。

        语音频道:重启前在的频道还有人就回去;否则 startup(进程启动时建的会话)才进默认频道,
        按需建 / 从休眠恢复的会话不主动进频道。最后还不在语音里,恢复的队列先暂停着,不对着空气放。"""
        self.link.on_user_joined = self._on_user_created
        self.link.on_user_updated = self._on_user_updated
        self.link.on_user_left = self._on_user_removed
        self.link.on_self_moved = self._on_self_moved
        self.link.on_panel_button = self.now_playing.resolve_button
        self.link.on_panel_pressed = self.now_playing.poke
        self.bind_guild(self.link.guild_id)
        self.load_guild_state()
        # 状态读完才接命令:之前来的命令由连接层回"还在启动"
        self.link.on_autocomplete = self.autocomplete
        self.link.on_precheck = self.precheck
        self.link.on_command = self.command_received
        self.now_playing.start(getattr(self, 'ticker', None))
        # 启动时已经在语音里的人不会逐个触发"加入"回调:直接从快照记下每人所在频道,跟随逻辑要用
        for user in self.link.users.values():
            self._user_channels[user.session] = user.channel_id

        if not self.rejoin_saved_channel() and startup:
            self.join_channel()
        self._pause_outside_voice()
        self._humans_in_channel = self.get_user_count_in_channel()
        # 默认频道可能本来就没人:连上后按跟随设置检查一次
        self.schedule_follow_check(delay=5)

    def load_guild_state(self):
        """读这个服务器存的音量、播放模式和队列(bind_guild 之后)。第一次先接收旧版不分服务器的设置。"""
        if self.guild_id:
            self.store.adopt_legacy(self.guild_id)

        max_vol = guild_max_volume(self.guild_id, self.store)
        volume = _as_float(self.setting('volume'), var.config.getfloat('bot', 'volume'))
        self.volume_helper.set_volume(min(volume, max_vol))

        mode = self.setting('playback_mode') or var.config.get('bot', 'playback_mode')
        if mode not in PLAYBACK_MODES:
            self.log.warning("bot: unknown saved playback mode %r, using the configured one", mode)
            mode = var.config.get('bot', 'playback_mode')
        self.set_playlist(new_queue(mode))

        if var.config.getboolean('bot', 'save_playlist'):
            self.log.info("bot: load playlist from previous session (%s)", self.guild_id or '-')
            self.playlist.load()
        self.load_announce_channel()
        self._guild_state_loaded = True

    def _pause_outside_voice(self):
        """启动后不在语音里:恢复的队列先暂停(/play 或 Web 上点播放再继续,从当前这首开头放)。"""
        if self.link.my_channel_id is not None or len(self.playlist) == 0:
            return
        self.is_pause = True
        self.pause_at_id = ""
        self.wait_for_ready = self.playlist.current_index != -1
        self.log.info("bot: not in a voice channel, the restored queue of %s waits paused", self.guild_id or '-')

    # ---- 公告频道(按服务器存,key announce_channel;配置文件的是主服务器的后备) ----

    def load_announce_channel(self):
        saved = self.setting(ANNOUNCE_KEY)
        if saved is not None and hasattr(self.link, 'announce_channel_id'):
            self.link.announce_channel_id = int(saved) if str(saved).isdigit() else None

    def set_announce_channel(self, channel_id):
        """Web 设置页改公告频道;None / '' = 不指定(发到最近一次有人用命令的频道)。"""
        value = str(channel_id) if channel_id and str(channel_id).isdigit() else ''
        self.save_setting(ANNOUNCE_KEY, value)
        self.link.announce_channel_id = int(value) if value else None

    def announce_channel(self):
        cid = getattr(self.link, 'announce_channel_id', None)
        return str(cid) if cid else ''

    def save_queue(self):
        """退出时(信号)保存队列。"""
        # 还没读出存的队列就退出(连接 Discord 时被停):别拿空队列覆盖掉
        if var.config.getboolean('bot', 'save_playlist') \
                and var.config.get("bot", "save_music_library") \
                and getattr(self, '_guild_state_loaded', True):
            self.log.info("bot: save playlist into database (%s)", self.guild_id or '-')
            self.playlist.save()

    def stop_session(self):
        """让播放循环退出(它退出前会再存一次队列),面板不再更新。进程退出 / 休眠时由 Hub 调用。
        (不能叫 stop:那是 PlayerMixin 的"停止播放",/stop 命令和 Web 都在用。)"""
        self.exit = True
        now_playing = getattr(self, 'now_playing', None)
        if now_playing is not None:
            now_playing.stop()
        self.cancel_follow_check()

    def release(self):
        """播放循环退出后(休眠):结束还挂着的 ffmpeg 进程。"""
        thread, self.thread = getattr(self, 'thread', None), None
        if thread is not None:
            try:
                thread.kill()
            except Exception:
                pass

    def is_idle(self):
        """可以休眠:不在语音里,也没在放(暂停着、队列放完了),没有命令在排队。"""
        if self.link.my_channel_id is not None:
            return False
        executor = getattr(self, 'executor', None)
        if executor is not None and executor.pending((self.guild_id, 'cmd')):
            return False
        if self.is_pause or len(self.playlist) == 0:
            return True
        return self.thread is None and not self.wait_for_ready

    def get_version(self):
        if self.version != "git":
            return self.version
        else:
            return util.get_snapshot_version()

    def register_slash_commands(self, named_specs):
        """[(斜杠命令名, Spec)]:命令分发表按 spec.key 索引。命令树由 Hub 在连接前注册给 DiscordClient。"""
        for name, spec in named_specs:
            self.cmd_handle[spec.key] = {'handle': spec.handler, 'spec': spec, 'name': name}
            self.slash_names[spec.key] = name

    # =======================
    #   Voice channel events
    # =======================

    def _on_user_created(self, user):
        self._note_user_event(user, 'created')
        self._dispatch_users_changed(user, 'created')

    def _on_user_updated(self, user, changed):
        if 'channel_id' not in (changed or ()):
            return  # 只关心换频道(静音之类的更新忽略)
        self._note_user_event(user, 'updated')
        self._dispatch_users_changed(user, changed)

    def _on_user_removed(self, user):
        self._note_user_event(user, 'removed')
        self._dispatch_users_changed(user, 'removed')

    def _dispatch_users_changed(self, user, action):
        """when_nobody_in_channel 的处理会暂停 / 继续播放(切歌要淡出几十毫秒):排到这个服务器的事件队列
        (guild_id, 'evt') 末尾,不阻塞当前这条事件,也不再每条事件开一个线程。"""
        if not getattr(self, '_react_to_empty_channel', False):
            return
        executor = getattr(self, 'executor', None)
        if executor is None:
            self.users_changed(user, action)
            return
        try:
            executor.submit((self.guild_id, 'evt'), self.users_changed, user, action)
        except RuntimeError:
            pass  # 线程池已关闭(正在退出)

    def _on_self_moved(self, old_channel, new_channel):
        """bot 自己进出 / 换语音频道(包括被管理员拖走、踢出)。记下所在频道,重启后回去;
        退出进程时断开语音不算(那时要留着记录)。"""
        if not getattr(self, 'exit', False):
            self.remember_voice_channel(new_channel)
        if new_channel is None and old_channel is not None and time.time() >= self._leaving_until:
            # 被人从语音里踢出去了:暂停,别在没人听的情况下继续"播"
            if not self.is_pause and len(self.playlist) > 0:
                self.log.info("bot: disconnected from voice, pausing playback")
                self.pause()
        self._humans_in_channel = self.get_user_count_in_channel()
        self.schedule_follow_check()

    # =======================
    #         Commands
    # =======================

    def _run_command(self, ctx):
        try:
            self._handle_command(ctx)
        except Exception:
            self.log.exception("bot: failed to handle a command")
        finally:
            try:
                self.link.finish(ctx)
            except Exception:
                pass

    def command_received(self, ctx):
        """连接层回调:交给共享线程池,立刻返回。

        命令处理可能很慢(建条目、写库、起校验线程、回消息),和语音状态事件在同一条队列里会拖住
        后者:命令走 (guild_id, 'cmd'),事件走 (guild_id, 'evt'),同一服务器的命令仍按顺序执行。"""
        executor = getattr(self, 'executor', None)
        if executor is None:
            # 没走 __init__ 的场景(测试替身):退回同步处理
            try:
                self._handle_command(ctx)
            except Exception:
                self.log.exception("bot: failed to handle a command")
            return
        executor.submit((self.guild_id, 'cmd'), self._run_command, ctx)

    def precheck(self, ctx):
        """在 Discord 等回应的 3 秒内调用:返回拒绝理由(HTML)就只回给本人,不执行命令。"""
        entry = self.cmd_handle.get(ctx.command)
        if entry is None:
            return tr('bad_command', command=ctx.command)
        spec = entry['spec']
        refusal = self._permission_refusal(spec, ctx, check_url=True)
        if refusal:
            return refusal
        admin = self.is_owner(ctx) or self.is_admin(ctx)

        mine = self.link.my_channel_id
        if not spec.outside_channel and not admin \
                and not var.config.getboolean('bot', 'allow_other_channel_message') \
                and mine is not None and ctx.voice_channel_id != mine:
            return tr('not_in_my_channel')

        if spec.joins_voice and mine is None and ctx.voice_channel_id is None:
            return tr('join_voice_first')
        return None

    def _permission_refusal(self, spec, ctx, check_url=False):
        """封禁 / 管理员 / bot 主人检查,预检查和真正执行前各查一次。返回拒绝理由或 None。"""
        owner = self.is_owner(ctx)
        admin = owner or self.is_admin(ctx)
        if self.banned('user_ban', str(ctx.actor), admin=admin, owner=owner):
            return tr('user_ban')
        if check_url and ctx.argument:
            input_url = util.get_url_from_input(ctx.argument)
            if input_url and self.banned('url_ban', input_url, admin=admin, owner=owner):
                return tr('url_ban', url=input_url)
        if getattr(spec, 'owner_only', False) and not owner:
            return tr('not_owner')
        if spec.admin and not admin:
            return tr('not_admin')
        return None

    def banned(self, kind, value, admin=False, owner=False):
        """value 被封禁了没有:全局规则(bot 主人定的)管所有人,只有 bot 主人自己不受影响;
        本服务器的规则(服务器管理员定的)管不到本服务器的管理员。"""
        if owner:
            return False
        store = self.store
        if store is None:
            return False
        if store.has_rule(kind, value):
            return True
        return not admin and bool(self.guild_id) \
            and store.has_rule(kind, value, self.guild_id, include_global=False)

    def _handle_command(self, ctx):
        entry = self.cmd_handle.get(ctx.command)
        if entry is None:
            self.send_msg(tr('bad_command', command=ctx.command), ctx)
            return
        spec = entry['spec']
        user = ctx.name
        self.log.info(f'bot: received /{entry["name"]} "{ctx.argument}" from {user} ({ctx.actor})')

        # 预检查之外再查一遍权限:管理员 / bot 主人命令的 handler 自己不检查,不能只靠预检查
        refusal = self._permission_refusal(spec, ctx)
        if refusal:
            self.send_msg(refusal, ctx)
            return
        self._refresh_discord_link(ctx)

        # 点歌类命令:bot 不在语音里就先进发命令的人所在的频道
        if spec.joins_voice and self.link.my_channel_id is None and ctx.voice_channel_id is not None:
            if not self.move_to_channel(ctx.voice_channel_id, f'requested by {user}'):
                self.send_msg(tr('cannot_join_voice'), ctx)
                return

        try:
            entry['handle'](self, user, ctx, entry['name'], ctx.argument)
        except media.playlist.QueueFullError as e:
            self.send_msg(tr('queue_full', max=e.limit), ctx)
        except Exception:
            error_traceback = traceback.format_exc()
            error = error_traceback.rstrip().split("\n")[-1]
            self.log.error(f"bot: command {ctx.command} failed with error: {error_traceback}\n")
            self.send_msg(tr('error_executing_command', command=entry['name'], error=error), ctx)

    def autocomplete(self, kind, ctx, current):
        """斜杠命令参数的自动补全:[(显示文字, 值)],最多 25 条。"""
        from commands import autocomplete
        return autocomplete.suggest(self, kind, ctx, current)

    # 发消息从不抛异常:它被下载线程、进度播报、校验线程等到处调用。
    def send_msg(self, msg, text):
        """回复发命令的人(text 是 CommandContext);没有上下文(Web / 后台)就发到公告频道。"""
        try:
            msg = msg.encode('utf-8', 'ignore').decode('utf-8')
            if isinstance(text, CommandContext):
                self.link.reply(text, msg)
            else:
                self.link.send_announcement(msg)
        except Exception:
            self.log.warning("bot: could not send a reply", exc_info=True)

    def send_channel_msg(self, msg):
        try:
            msg = msg.encode('utf-8', 'ignore').decode('utf-8')
            self.link.send_announcement(msg)
        except Exception:
            self.log.warning("bot: could not send channel message", exc_info=True)

    def _refresh_discord_link(self, ctx):
        """绑定表里记着 Discord 显示名(Web 队列 / 统计靠它把聊天点歌对上 Web 昵称),
        改名后在这里跟上;没绑定就是一次查不到。"""
        if var.user_db is None:
            return
        try:
            from commands.personal import discord_key
            key, name = discord_key(self, ctx)
            if key:
                var.user_db.identity_for_discord(key, name)
        except Exception:
            self.log.debug("bot: could not refresh discord link", exc_info=True)

    def is_admin(self, user):
        """这个服务器的 bot 管理员。user 是 CommandContext(斜杠命令)或 Discord user id。"""
        if isinstance(user, CommandContext):
            return user.is_admin
        return str(user) in owner_ids()

    def is_owner(self, user):
        """bot 主人([bot] admin 里的 Discord 用户 ID):全局封禁和运维命令只认这个,每次都对照配置检查;
        服务器管理员(管理服务器权限)不算。user 是 CommandContext 或 user id。"""
        actor = user.actor if isinstance(user, CommandContext) else user
        return str(actor) in owner_ids()

    def command_name(self, key):
        """spec.key -> 当前的斜杠命令名(改过名也对)。"""
        return self.slash_names.get(key, key)

    # =======================
    #   Other voice events
    # =======================

    def get_user_count_in_channel(self):
        """bot 所在语音频道里的真人数(不算 bot 自己和其他 bot)。"""
        mine = self.link.my_channel_id
        if mine is None:
            return 0
        return len(self.humans_by_channel().get(mine, []))

    def users_changed(self, user, message):
        try:
            self._users_changed()
        except Exception:
            self.log.exception("bot: error while reacting to a channel user change")

    def _users_changed(self):
        # only react when the first person comes back, so the music doesn't
        # restart every time somebody joins a channel that already has listeners
        humans = self.get_user_count_in_channel()

        if humans > self._humans_in_channel and humans == 1:
            if var.config.get("bot", "when_nobody_in_channel") == "pause_resume":
                self.resume()
            elif var.config.get("bot", "when_nobody_in_channel") == "pause" and self.is_pause:
                self.send_channel_msg(tr("auto_paused"))
        elif humans == 0 and self.link.my_channel_id is not None and len(self.playlist) != 0:
            # 频道里只剩 bot 了
            if self.follow_would_move():
                # 跟随模式马上会带 bot 去有人的频道,继续放,别暂停/清空
                self.log.info('bot: No user in my channel, following users instead of pausing.')
            elif var.config.get("bot", "when_nobody_in_channel") == "stop":
                self.log.info('bot: No user in my channel. Stop music now.')
                self.clear()
            else:
                self.log.info('bot: No user in my channel. Pause music now.')
                self.pause()

        self._humans_in_channel = humans

    def leave_voice(self):
        """/leave:离开语音频道(不触发"被踢出就暂停")。"""
        if self.link.my_channel_id is None:
            return
        self._leaving_until = time.time() + 15
        self.link.leave_voice()
