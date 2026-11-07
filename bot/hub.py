# coding=utf-8
"""进程的总管(var.hub):一个 Discord 连接,若干个服务器会话(DJBot)。

  - 启动:连上 Discord(失败就退出)-> 建主服务器的会话 -> 读它存的状态 -> 进默认频道 ->
    每个会话的播放循环在自己的线程(Player-<guild_id>)里跑,主线程在 run() 里等
  - 进程级的事:SIGINT / SIGTERM、看门狗、Docker 心跳文件、bot 账号的状态(几个服务器在放歌)
  - 给 Web 层的接口:sessions / session_for / guild_ids / guild_info / home_guild_id / is_member

现在仍然只有主服务器一个会话(配置的 [discord] guild_id,没配就是 bot 看到的第一个服务器);
以后按需给别的服务器建会话时,接口不变。
"""

import logging
import os
import signal
import sys
import threading
import time

import util
import variables as var
from constants import tr_cli as tr

from .core import DJBot
from .discord_link import DiscordClient, GuildLink
from .executor import KeyedExecutor
from .now_playing import NowPlayingTicker

log = logging.getLogger("bot")

#: 成员查询结果缓存多久(秒);"不是成员"缓存得短一些,刚加入的人不用等太久
MEMBER_TTL = 300
MEMBER_MISS_TTL = 60
#: 看门狗 / 心跳检查间隔(秒)
MONITOR_EVERY = 5
#: 播放循环这么久(秒)没转一圈就不再刷新心跳(docker-compose 的健康检查 90 秒没心跳判 unhealthy)
HEARTBEAT_STALE = 60


class Hub:
    def __init__(self, args, install_signals=True):
        self.args = args
        #: 所有服务器共用的线程池:命令 (gid, 'cmd')、连接层事件 (gid, 'evt')、面板更新
        self.executor = KeyedExecutor(max_workers=16, name='Worker')
        self.ticker = NowPlayingTicker(executor=self.executor)
        self.client = None
        self.named_specs = []

        self._lock = threading.RLock()
        self._sessions = {}          # guild id(str)-> DJBot
        self._threads = {}           # guild id(str)-> 播放循环线程
        self._home = ''

        self.exit = False
        self.nb_exit = 0
        self.exit_code = 0
        self._done = threading.Event()

        self._presence_lock = threading.Lock()
        self._activities = {}        # guild id -> (歌名, 歌手):正在放歌的服务器
        self._presence = None        # 账号现在显示的 (text, state);None = 没有

        self._members_lock = threading.Lock()
        self._members = {}           # (guild id, user id) -> (是不是成员, 过期时间)

        self.watchdog_timeout = var.config.getint("bot", "watchdog_timeout", fallback=0) if var.config else 0
        self.heartbeat_file = os.environ.get("BAM_HEARTBEAT") or \
            os.path.join(var.tmp_folder or '.', "djbot.heartbeat")
        self._exit_process = os._exit

        if install_signals:
            # docker stop / restart 发的是 SIGTERM:默认处理会直接杀进程,队列来不及落盘。按 Ctrl-C 同样处理
            signal.signal(signal.SIGINT, self._on_signal)
            signal.signal(signal.SIGTERM, self._on_signal)

    # =====================================================================
    #   启动
    # =====================================================================

    def register_slash_commands(self, named_specs):
        """[(斜杠命令名, Spec)]:连接前交给 DiscordClient 建命令树,每个会话也按它建分发表。"""
        self.named_specs = list(named_specs)

    def start(self):
        """连上 Discord,建好主服务器的会话(读状态、进默认频道)。播放循环在 run() 里启动。"""
        version = DJBot.version if DJBot.version != 'git' else util.get_snapshot_version()
        log.info("bot: Discord-DJBot version %s, starting...", version)
        self.connect()
        var.bot = self._create_session(self._home)
        return var.bot

    def connect(self):
        token = getattr(self.args, 'token', None) or os.environ.get("DISCORD_TOKEN") \
            or var.config.get("discord", "token")
        if not token:
            log.error("bot: no Discord bot token. Set [discord] token in configuration.ini "
                      "or the DISCORD_TOKEN environment variable.")
            sys.exit(1)
        home = getattr(self.args, 'guild', None) or var.config.get("discord", "guild_id")
        self.client = DiscordClient(
            token, home_guild_id=home or None, language=var.language,
            debug=var.config.getboolean('debug', 'discord_connection'), executor=self.executor)
        self.client.on_activity = self.report_activity
        self.client.register_commands(self.named_specs)
        try:
            self.client.connect()
        except Exception as e:
            log.error("bot: failed to connect to Discord: %s", e)
            sys.exit(1)
        self._home = str(self.client.home_guild_id or '')

    def _create_session(self, guild_id):
        admin_ids = [a.strip() for a in var.config.get('bot', 'admin').replace(';', ',').split(',')
                     if a.strip().isdigit()]
        link = GuildLink(
            self.client, guild_id or None,
            # 配置文件里的公告频道是主服务器的;GuildLink 只认本服务器的频道
            announce_channel_id=(var.config.get("discord", "announce_channel") or None)
            if guild_id == self._home else None,
            admin_ids=admin_ids,
            admin_permission=var.config.getboolean("discord", "admin_by_permission"),
            self_deaf=var.config.getboolean("discord", "self_deaf"),
            bitrate=var.config.getint("discord", "bitrate"))
        self.client.add_link(link)
        session = DJBot(self.args, link, executor=self.executor, ticker=self.ticker)
        session.exit = self.exit
        session.register_slash_commands(self.named_specs)
        session.start()
        with self._lock:
            self._sessions[str(guild_id or '')] = session
        return session

    # =====================================================================
    #   运行 / 退出
    # =====================================================================

    def run(self):
        """主线程:启动各会话的播放循环,等到全部退出(Ctrl-C、/kill、连接断开),再断开 Discord。
        返回进程退出码。"""
        if not self.exit:
            for gid, session in self.sessions_by_id().items():
                self._start_player(gid, session)
            threading.Thread(target=self._monitor, name="Monitor", daemon=True).start()
        self._check_done()
        while not self._done.wait(1.0):
            pass
        self.shutdown()
        return self.exit_code

    def _start_player(self, gid, session):
        thread = threading.Thread(target=self._run_session, args=(gid, session),
                                  name=f"Player-{gid or 'none'}", daemon=True)
        with self._lock:
            self._threads[gid] = thread
        thread.start()

    def _run_session(self, gid, session):
        try:
            session.loop()
        except Exception:
            log.exception("bot: playback loop of %s crashed", gid or '-')
        finally:
            if not self.exit:
                client = self.client
                reason = client.close_reason if client is not None and not client.alive else 'loop ended'
                log.error("bot: playback loop of %s stopped (%s), exiting for restart", gid or '-', reason)
                self.exit_code = 1
                self.stop()
            self._check_done()

    def _check_done(self):
        me = threading.current_thread()
        with self._lock:
            running = [t for t in self._threads.values() if t is not me and t.is_alive()]
        if self.exit and not running:
            self._done.set()

    def stop(self):
        """所有会话的播放循环退出(各自存一次队列),之后 run() 断开 Discord 返回。/kill 也走这里。"""
        self.exit = True
        for session in self.sessions():
            try:
                session.stop_session()
            except Exception:
                log.exception("bot: could not stop session %s", session.guild_id)
        self._check_done()

    def shutdown(self):
        self.ticker.stop()
        if self.client is not None:
            self.client.close()
        self.executor.shutdown()

    def save_queues(self):
        for session in self.sessions():
            try:
                session.save_queue()
            except Exception:
                log.exception("bot: could not save the queue of %s", session.guild_id)

    def _on_signal(self, signum, frame):
        log.info("bot: signal %s caught, quitting, %d more to kill", signum, 2 - self.nb_exit)
        self.save_queues()
        if self.nb_exit > 1:
            log.info("bot: forced quit")
            sys.exit(0)
        self.nb_exit += 1
        self.stop()

    # =====================================================================
    #   看门狗 / 心跳
    # =====================================================================

    def _monitor(self):
        while not self._done.wait(MONITOR_EVERY):
            if self.exit:
                return
            now = time.time()
            self.check_watchdog(now)
            self.write_heartbeat(now)

    def _loops(self):
        """[(guild id, 会话, 播放循环线程或 None)]"""
        with self._lock:
            return [(gid, s, self._threads.get(gid)) for gid, s in self._sessions.items()]

    def check_watchdog(self, now=None):
        """有会话的播放循环卡住(比如 ffmpeg 读不动)超过 watchdog_timeout:退出进程,让 Docker 拉起新的。
        [bot] watchdog_timeout = 0 关闭。返回卡住的服务器 id(测试用)。"""
        timeout = self.watchdog_timeout
        if timeout <= 0 or self.exit:
            return None
        now = time.time() if now is None else now
        for gid, session, thread in self._loops():
            if thread is None or not thread.is_alive():
                continue
            stalled = now - session.last_loop_at
            if stalled > timeout:
                log.critical("bot: playback loop of %s stalled for %.0fs (> %ds), exiting for restart",
                             gid or '-', stalled, timeout)
                self._exit_process(1)
                return gid
        return None

    def healthy(self, now=None):
        """每个会话的播放循环都活着、最近转过。"""
        now = time.time() if now is None else now
        for _, session, thread in self._loops():
            if thread is None or not thread.is_alive():
                return False
            if now - session.last_loop_at > HEARTBEAT_STALE:
                return False
        return True

    def write_heartbeat(self, now=None):
        """健康时刷新心跳文件(docker-compose 的 healthcheck 看它的修改时间)。"""
        now = time.time() if now is None else now
        if not self.healthy(now):
            return False
        try:
            with open(self.heartbeat_file, "w") as f:
                f.write(str(now))
        except Exception:
            return False
        return True

    # =====================================================================
    #   bot 账号的状态
    # =====================================================================

    def report_activity(self, guild_id, title, artist=''):
        """会话报告自己在放什么(GuildLink.set_activity)。账号只有一个状态:
        没有服务器在放 -> 清除;一个 -> 那首歌(第二行歌手);多个 -> "正在听 N 个服务器"。"""
        gid = str(guild_id or '')
        with self._presence_lock:
            if title:
                self._activities[gid] = (title, artist or '')
            else:
                self._activities.pop(gid, None)
            desired = self._desired_presence()
            if desired == self._presence:
                return
            self._presence = desired
            client = self.client
            if client is not None:
                client.set_presence(*(desired or (None, '')))

    def _desired_presence(self):
        playing = list(self._activities.values())
        if not playing:
            return None
        if len(playing) == 1:
            return playing[0]
        return tr('presence_servers', count=len(playing)), ''

    # =====================================================================
    #   给 Web 层的接口
    # =====================================================================

    def sessions(self):
        """在运行的会话(DJBot)。"""
        with self._lock:
            return list(self._sessions.values())

    def sessions_by_id(self):
        with self._lock:
            return dict(self._sessions)

    def session_for(self, guild_id, create=True):
        """这个服务器的会话;没有返回 None。现在只有主服务器有会话(create 暂时不起作用,
        以后会按需建 / 从休眠恢复)。"""
        gid = str(guild_id or '')
        if not gid:
            return None
        with self._lock:
            return self._sessions.get(gid)

    @property
    def home_guild_id(self):
        return self._home

    def guild_ids(self):
        """bot 加入的所有服务器。"""
        client = self.client
        if client is None:
            return [self._home] if self._home else []
        return [str(gid) for gid in client.guild_ids()]

    def guild_info(self, guild_id):
        """{'id', 'name', 'icon'}(icon 是 CDN 地址或 '');bot 不在这个服务器返回 None。"""
        client = self.client
        return client.guild_info(guild_id) if client is not None else None

    def is_member(self, guild_id, user_id):
        """user 是不是这个服务器的成员(REST 查询,不需要 members intent,结果缓存几分钟)。"""
        gid, uid = str(guild_id or ''), str(user_id or '')
        if not (gid.isdigit() and uid.isdigit()):
            return False
        key = (gid, uid)
        now = time.time()
        with self._members_lock:
            hit = self._members.get(key)
            if hit is not None and hit[1] > now:
                return hit[0]
        client = self.client
        result = client.fetch_member(gid, uid) if client is not None else None
        if result is None:
            return False  # 查不了(网络 / 权限):不缓存,下次再查
        with self._members_lock:
            if len(self._members) > 10000:
                self._members = {k: v for k, v in self._members.items() if v[1] > now}
            self._members[key] = (result, now + (MEMBER_TTL if result else MEMBER_MISS_TTL))
        return result
