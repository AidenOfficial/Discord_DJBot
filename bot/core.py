# coding=utf-8
import collections
import logging
import os
import queue
import signal
import sys
import threading
import time
import traceback

import util
import variables as var
from constants import tr_cli as tr

from .channels import ChannelMixin
from .discord_link import CommandContext, DiscordLink
from .now_playing import NowPlaying
from .player import PlayerMixin


class DJBot(PlayerMixin, ChannelMixin):
    version = 'git'

    def __init__(self, args):
        self.log = logging.getLogger("bot")
        self.log.info(f"bot: Discord-DJBot version {self.get_version()}, starting...")
        signal.signal(signal.SIGINT, self.ctrl_caught)
        # docker stop / restart 发的是 SIGTERM:默认处理会直接杀进程,
        # 队列来不及落盘。按 Ctrl-C 同样的路径优雅退出。
        signal.signal(signal.SIGTERM, self.ctrl_caught)
        self.cmd_handle = {}
        self.slash_names = {}  # spec.key -> 斜杠命令名(帮助 / 提示文字用)

        # Discord 只收立体声
        self.stereo = True

        self.channel = args.channel if args.channel else var.config.get("discord", "channel")

        var.is_proxified = var.config.getboolean(
            "webinterface", "is_web_proxified")

        # Flags to indicate the bot is exiting (Ctrl-C, or /kill)
        self.exit = False
        self.nb_exit = 0

        # Related to ffmpeg thread
        self.thread = None
        self.thread_stderr = None
        self.read_pcm_size = 0
        self.pcm_buffer_size = 0
        self.last_ffmpeg_err = ""
        self._ffmpeg_stderr_lines = collections.deque(maxlen=20)

        # Single-instance guard so the same item never spawns two concurrent
        # download / progress-reporter threads (which would double every
        # download message in chat).
        self._active_downloads = set()
        self._download_lock = threading.Lock()

        # Liveness tracking for the watchdog and the (Docker) healthcheck.
        self.last_loop_at = time.time()
        self._last_heartbeat_write = 0.0
        self.heartbeat_file = os.environ.get("BAM_HEARTBEAT") or \
            os.path.join(var.tmp_folder, "djbot.heartbeat")

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

        token = args.token or os.environ.get("DISCORD_TOKEN") or var.config.get("discord", "token")
        if not token:
            self.log.error("bot: no Discord bot token. Set [discord] token in configuration.ini "
                           "or the DISCORD_TOKEN environment variable.")
            sys.exit(1)
        guild_id = args.guild or var.config.get("discord", "guild_id")
        admin_ids = [a.strip() for a in var.config.get('bot', 'admin').replace(';', ',').split(',')
                     if a.strip().isdigit()]

        self.link = DiscordLink(
            token,
            guild_id=guild_id or None,
            announce_channel_id=var.config.get("discord", "announce_channel") or None,
            admin_ids=admin_ids,
            admin_permission=var.config.getboolean("discord", "admin_by_permission"),
            self_deaf=var.config.getboolean("discord", "self_deaf"),
            bitrate=var.config.getint("discord", "bitrate"),
            language=var.language,
            debug=var.config.getboolean('debug', 'discord_connection'))
        # 公告频道里的"正在播放"面板 + 语音频道状态
        self.now_playing = NowPlaying(
            self, self.link,
            panel=var.config.getboolean('discord', 'now_playing_panel', fallback=True),
            voice=var.config.getboolean('discord', 'voice_channel_status', fallback=True))

        # ====== Volume ======
        self.volume_helper = util.VolumeHelper()

        max_vol = var.config.getfloat('bot', 'max_volume')
        if var.db.has_option('bot', 'max_volume'):
            max_vol = var.db.getfloat('bot', 'max_volume')
        _volume = var.config.getfloat('bot', 'volume')
        if var.db.has_option('bot', 'volume'):
            _volume = var.db.getfloat('bot', 'volume')
        _volume = min(_volume, max_vol)
        self.volume_helper.set_volume(_volume)
        self.last_volume_cycle_time = time.time()

        assert var.config.get("bot", "when_nobody_in_channel") in ['pause', 'pause_resume', 'stop', 'nothing', ''], \
            "Unknown action for when_nobody_in_channel"

        self._react_to_empty_channel = \
            var.config.get("bot", "when_nobody_in_channel") in ['pause', 'pause_resume', 'stop']

        # Debug use
        self._loop_status = 'Idle'

        self.redirect_ffmpeg_log = var.config.getboolean('debug', 'redirect_ffmpeg_log')

        self._start_message_worker()
        self._init_follow()
        bots = var.config.get("bot", "when_nobody_in_channel_ignore", fallback="")
        self.bots = set(b.strip() for b in bots.split(',') if b.strip())
        self._humans_in_channel = 0

    def start(self):
        """连上 Discord。register_slash_commands() 之后调用。"""
        self.link.on_command = self.command_received
        self.link.on_precheck = self.precheck
        self.link.on_autocomplete = self.autocomplete
        self.link.on_user_joined = self._on_user_created
        self.link.on_user_updated = self._on_user_updated
        self.link.on_user_left = self._on_user_removed
        self.link.on_self_moved = self._on_self_moved
        self.link.on_panel_button = self.now_playing.resolve_button
        self.link.on_panel_pressed = self.now_playing.poke
        try:
            self.link.connect()
        except Exception as e:
            self.log.error("bot: failed to connect to Discord: %s", e)
            sys.exit(1)
        self.now_playing.start()
        # 启动时已经在语音里的人不会逐个触发"加入"回调:直接从快照记下每人所在频道,跟随逻辑要用
        for user in self.link.users.values():
            self._user_channels[user.session] = user.channel_id

        self.join_channel()
        self._humans_in_channel = self.get_user_count_in_channel()
        # 默认频道可能本来就没人:连上后按跟随设置检查一次
        self.schedule_follow_check(delay=5)

    # Set the CTRL+C shortcut
    def ctrl_caught(self, signal, frame):
        self.log.info(
            "\nSIGINT caught, quitting, {} more to kill".format(2 - self.nb_exit))

        if var.config.getboolean('bot', 'save_playlist') \
                and var.config.get("bot", "save_music_library"):
            self.log.info("bot: save playlist into database")
            self.playlist.save()

        if self.nb_exit > 1:
            self.log.info("Forced Quit")
            sys.exit(0)
        self.nb_exit += 1

        self.exit = True

    def get_version(self):
        if self.version != "git":
            return self.version
        else:
            return util.get_snapshot_version()

    def register_slash_commands(self, named_specs):
        """[(斜杠命令名, Spec)]:交给连接层注册,命令分发表按 spec.key 索引。"""
        for name, spec in named_specs:
            self.cmd_handle[spec.key] = {'handle': spec.handler, 'spec': spec, 'name': name}
            self.slash_names[spec.key] = name
        self.link.register_commands(named_specs)

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
        if getattr(self, '_react_to_empty_channel', False):
            threading.Thread(target=self.users_changed, args=(user, action), daemon=True).start()

    def _on_self_moved(self, old_channel, new_channel):
        """bot 自己进出 / 换语音频道(包括被管理员拖走、踢出)。"""
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

    def _start_message_worker(self):
        # 命令处理可能很慢(建条目、写库、起校验线程、回消息),放在连接层的事件线程里
        # 会拖住后面的语音状态事件。回调只把命令入队,由单独的线程按顺序处理。
        self._message_queue = queue.Queue()
        th = threading.Thread(target=self._message_worker, name="CommandWorker", daemon=True)
        th.start()

    def _message_worker(self):
        while True:
            ctx = self._message_queue.get()
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
        """连接层回调:只入队,立刻返回。"""
        message_queue = getattr(self, '_message_queue', None)
        if message_queue is None:
            # 没走 __init__ 的场景(测试替身):退回同步处理
            try:
                self._handle_command(ctx)
            except Exception:
                self.log.exception("bot: failed to handle a command")
            return
        message_queue.put(ctx)

    def precheck(self, ctx):
        """在 Discord 等回应的 3 秒内调用:返回拒绝理由(HTML)就只回给本人,不执行命令。"""
        entry = self.cmd_handle.get(ctx.command)
        if entry is None:
            return tr('bad_command', command=ctx.command)
        spec = entry['spec']
        admin = self.is_admin(ctx)

        if not admin and var.db.has_option('user_ban', str(ctx.actor)):
            return tr('user_ban')

        if not admin and ctx.argument:
            input_url = util.get_url_from_input(ctx.argument)
            if input_url and var.db.has_option('url_ban', input_url):
                return tr('url_ban', url=input_url)

        if spec.admin and not admin:
            return tr('not_admin')

        mine = self.link.my_channel_id
        if not spec.outside_channel and not admin \
                and not var.config.getboolean('bot', 'allow_other_channel_message') \
                and mine is not None and ctx.voice_channel_id != mine:
            return tr('not_in_my_channel')

        if spec.joins_voice and mine is None and ctx.voice_channel_id is None:
            return tr('join_voice_first')
        return None

    def _handle_command(self, ctx):
        entry = self.cmd_handle.get(ctx.command)
        if entry is None:
            self.send_msg(tr('bad_command', command=ctx.command), ctx)
            return
        spec = entry['spec']
        user = ctx.name
        self.log.info(f'bot: received /{entry["name"]} "{ctx.argument}" from {user} ({ctx.actor})')

        # 预检查之外再查一遍权限:管理员命令的 handler 自己不检查,不能只靠预检查
        admin = self.is_admin(ctx)
        if spec.admin and not admin:
            self.send_msg(tr('not_admin'), ctx)
            return
        if not admin and var.db.has_option('user_ban', str(ctx.actor)):
            self.send_msg(tr('user_ban'), ctx)
            return
        self._refresh_discord_link(ctx)

        # 点歌类命令:bot 不在语音里就先进发命令的人所在的频道
        if spec.joins_voice and self.link.my_channel_id is None and ctx.voice_channel_id is not None:
            if not self.move_to_channel(ctx.voice_channel_id, f'requested by {user}'):
                self.send_msg(tr('cannot_join_voice'), ctx)
                return

        try:
            entry['handle'](self, user, ctx, entry['name'], ctx.argument)
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
        """user 是 CommandContext(斜杠命令)或 Discord user id。"""
        if isinstance(user, CommandContext):
            return user.is_admin
        admins = {a.strip() for a in var.config.get('bot', 'admin').replace(';', ',').split(',') if a.strip()}
        return str(user) in admins

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
