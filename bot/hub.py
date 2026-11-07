# coding=utf-8
"""进程的总管(var.hub):一个 Discord 连接,若干个服务器会话(DJBot)。

  - 启动:连上 Discord(失败就退出)-> 建主服务器的会话 -> 读它存的状态 -> 进语音频道 ->
    重启前在语音里、现在那里还有人的服务器也建会话回去 -> 每个会话的播放循环在自己的线程
    (Player-<guild_id>)里跑,主线程在 run() 里等
  - 按需建会话:别的服务器第一次有人用命令(DiscordClient.on_session_needed)、Web 选了它
    (session_for)时才建;[discord] allowed_guilds 限定服务器,[bot] max_active_sessions 限定同时几个
  - 休眠:会话 [bot] session_idle_minutes 分钟不在语音里、也没在放,就存好队列、停掉播放循环、
    断开 GuildLink;下次 session_for 时从库里恢复(队列还在)。主服务器的会话不休眠:Web 页面和
    旧代码还通过 var.bot 用它
  - 进程级的事:SIGINT / SIGTERM、看门狗、Docker 心跳文件、bot 账号的状态(几个服务器在放歌)
  - 给 Web 层的接口:sessions / session_for / guild_ids / guild_info / home_guild_id / is_member

主服务器 = 配置的 [discord] guild_id,没配就是 bot 看到的第一个服务器;除了 var.bot,它只决定
旧版(不分服务器)的数据迁移给谁(store.adopt_legacy)。
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

from .channels import VOICE_KEY
from .core import DJBot
from .discord_link import STARTING_REPLY, DiscordClient, GuildLink
from .executor import KeyedExecutor, Timers
from .now_playing import NowPlayingTicker

log = logging.getLogger("bot")

#: 成员查询结果缓存多久(秒);"不是成员"缓存得短一些,刚加入的人不用等太久
MEMBER_TTL = 300
MEMBER_MISS_TTL = 60
#: 看门狗 / 心跳 / 休眠检查间隔(秒)
MONITOR_EVERY = 5
#: 播放循环这么久(秒)没转一圈就不再刷新心跳(docker-compose 的健康检查 90 秒没心跳判 unhealthy)
HEARTBEAT_STALE = 60
#: 等别的线程建好 / 休眠完一个会话最多等多久(秒)
TRANSITION_WAIT = 60
#: 休眠时等播放循环退出(它退出前存队列)最多多久(秒)
LOOP_JOIN_TIMEOUT = 15


def _id_set(text):
    return {p.strip() for p in (text or '').replace(';', ',').split(',') if p.strip().isdigit()}


class Hub:
    def __init__(self, args, install_signals=True):
        self.args = args
        #: 所有服务器共用的线程池:命令 (gid, 'cmd')、连接层事件 (gid, 'evt')、面板更新、
        #: 会话的建立 / 休眠 (gid, 'session')
        self.executor = KeyedExecutor(max_workers=16, name='Worker')
        #: 所有服务器共用的定时线程(跟随检查的防抖),到点交给 executor
        self.timers = Timers(self.executor, name='Timers')
        self.ticker = NowPlayingTicker(executor=self.executor)
        self.client = None
        self.named_specs = []

        self._lock = threading.RLock()
        self._sessions = {}          # guild id(str)-> DJBot(在运行的)
        self._threads = {}           # guild id(str)-> 播放循环线程
        self._transitions = {}       # guild id -> (Event, 线程 ident, 'create' / 'hibernate'):正在建 / 正在休眠
        self._idle_since = {}        # guild id -> 从什么时候开始闲着
        self._pinned = set()         # 不休眠的会话(主服务器)
        self._running = False        # run() 之后新建的会话马上开播放循环
        self._home = ''
        self._explicit_home = False

        self.exit = False
        self.nb_exit = 0
        self.exit_code = 0
        self._done = threading.Event()

        self._presence_lock = threading.Lock()
        self._activities = {}        # guild id -> (歌名, 歌手):正在放歌的服务器
        self._presence = None        # 账号现在显示的 (text, state);None = 没有

        self._members_lock = threading.Lock()
        self._members = {}           # (guild id, user id) -> (是不是成员, 过期时间)

        config = var.config
        self.watchdog_timeout = config.getint("bot", "watchdog_timeout", fallback=0) if config else 0
        #: 空 = bot 加入的所有服务器都服务
        self.allowed_guilds = _id_set(config.get("discord", "allowed_guilds", fallback='')) if config else set()
        self.idle_minutes = config.getfloat("bot", "session_idle_minutes", fallback=10) if config else 0
        self.max_sessions = config.getint("bot", "max_active_sessions", fallback=0) if config else 0
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
        """连上 Discord,建好主服务器的会话(读状态、进语音频道),再让重启前在语音里的服务器回去。
        播放循环在 run() 里启动。"""
        version = DJBot.version if DJBot.version != 'git' else util.get_snapshot_version()
        log.info("bot: Discord-DJBot version %s, starting...", version)
        self.connect()
        self._pinned.add(self._home)
        var.bot = self._ensure(self._home, startup=True, check=False, raise_errors=True)
        self.rejoin_voice_channels()
        return var.bot

    def connect(self):
        token = getattr(self.args, 'token', None) or os.environ.get("DISCORD_TOKEN") \
            or var.config.get("discord", "token")
        if not token:
            log.error("bot: no Discord bot token. Set [discord] token in configuration.ini "
                      "or the DISCORD_TOKEN environment variable.")
            sys.exit(1)
        home = getattr(self.args, 'guild', None) or var.config.get("discord", "guild_id")
        self._explicit_home = bool(home)
        self.client = DiscordClient(
            token, home_guild_id=home or None, language=var.language,
            debug=var.config.getboolean('debug', 'discord_connection'), executor=self.executor)
        self.client.on_activity = self.report_activity
        self.client.on_session_needed = self.request_session
        self.client.on_guild_joined = self._on_guild_joined
        self.client.on_guild_removed = self._on_guild_removed
        self.client.register_commands(
            self.named_specs,
            owner_guild_id=var.config.get("discord", "owner_guild_id", fallback='') or None,
            dev_guild_id=var.config.get("discord", "dev_guild_id", fallback='') or None,
            sync_state=var.db)
        try:
            self.client.connect()
        except Exception as e:
            log.error("bot: failed to connect to Discord: %s", e)
            sys.exit(1)
        self._home = self._pick_home(str(self.client.home_guild_id or ''))

    def _pick_home(self, home):
        """没配 guild_id 时 DiscordClient 用第一个服务器;有 allowed_guilds 的话改用第一个允许的。"""
        if self._explicit_home or not self.allowed_guilds or not home or home in self.allowed_guilds:
            return home
        allowed = [g for g in self.guild_ids() if g in self.allowed_guilds]
        new = allowed[0] if allowed else ''
        log.info("bot: %s is not in [discord] allowed_guilds, using %s as the home server", home, new or '-')
        if self.client is not None:
            self.client.home_guild_id = int(new) if new else None
        return new

    def rejoin_voice_channels(self):
        """重启前 bot 在语音里(store 的 voice_channel)、现在那个频道里还有人的服务器:建会话回去
        (在线程池里各自进行,不拖慢启动)。频道已经没人的忘掉。返回要回去的服务器。"""
        store, client = var.store, self.client
        if store is None or client is None or not hasattr(client, 'humans_in'):
            return []
        try:
            saved = store.guilds_with(VOICE_KEY)
        except Exception:
            log.exception("bot: could not read the saved voice channels")
            return []
        present = set(self.guild_ids())
        targets = []
        for gid, channel_id in saved.items():
            if gid in self.sessions_by_id() or gid not in present or not str(channel_id).isdigit():
                continue  # 主服务器自己的 start() 会回去;bot 不在的服务器留着记录
            if not self._allowed(gid):
                continue
            if not client.humans_in(gid, channel_id):
                log.info("bot: nobody left in the voice channel %s of %s, not rejoining", channel_id, gid)
                store.delete(gid, VOICE_KEY)
                continue
            targets.append(gid)
            self.executor.submit((gid, 'session'), self._ensure, gid, True)
        return targets

    def _create_session(self, guild_id, startup=False):
        gid = str(guild_id or '')
        admin_ids = [a.strip() for a in var.config.get('bot', 'admin').replace(';', ',').split(',')
                     if a.strip().isdigit()]
        link = GuildLink(
            self.client, guild_id or None,
            # 配置文件里的公告频道是主服务器的(服务器自己在 Web 上设置过的优先,load_guild_state 时读);
            # GuildLink 只认本服务器的频道
            announce_channel_id=(var.config.get("discord", "announce_channel") or None)
            if gid == self._home else None,
            admin_ids=admin_ids,
            admin_permission=var.config.getboolean("discord", "admin_by_permission"),
            self_deaf=var.config.getboolean("discord", "self_deaf"),
            bitrate=var.config.getint("discord", "bitrate"))
        self.client.add_link(link)
        try:
            session = DJBot(self.args, link, executor=self.executor, ticker=self.ticker, timers=self.timers)
            if gid != self._home:
                session.channel = ''  # 配置文件 / 命令行的默认频道是主服务器的
            session.exit = self.exit
            session.register_slash_commands(self.named_specs)
            session.start(startup=startup)
        except BaseException:
            link.close('session failed to start')
            raise
        with self._lock:
            self._sessions[gid] = session
            if self._running:
                self._start_player(gid, session)
        return session

    # =====================================================================
    #   按需建会话
    # =====================================================================

    def _allowed(self, gid):
        return not self.allowed_guilds or gid in self.allowed_guilds or (bool(gid) and gid == self._home)

    def _refusal(self, gid):
        """能不能给这个服务器建会话:None = 可以,否则是回给用户的理由。持锁调用。"""
        if self.exit:
            return STARTING_REPLY
        if not self._allowed(gid):
            return tr('server_not_allowed')
        client = self.client
        if client is not None and gid not in {str(g) for g in client.guild_ids()}:
            return tr('server_not_allowed')
        if self.max_sessions > 0:
            creating = sum(1 for _, _, kind in self._transitions.values() if kind == 'create')
            if len(self._sessions) + creating >= self.max_sessions:
                return tr('server_limit_reached')
        return None

    def session_for(self, guild_id, create=True):
        """这个服务器的会话。create:没有就建(或从休眠恢复),阻塞到建好;不允许 / 到上限 / bot 不在
        这个服务器时返回 None。两个线程同时要同一个服务器的会话只会建一个。"""
        gid = str(guild_id or '')
        if not gid:
            return None
        if not create:
            with self._lock:
                return self._sessions.get(gid)
        return self._ensure(gid)

    def _ensure(self, gid, startup=False, check=True, raise_errors=False):
        me = threading.get_ident()
        while True:
            with self._lock:
                session = self._sessions.get(gid)
                if session is not None:
                    return session
                busy = self._transitions.get(gid)
                if busy is None:
                    if check:
                        refusal = self._refusal(gid)
                        if refusal is not None:
                            log.debug("bot: no session for %s: %s", gid, refusal)
                            return None
                    done = threading.Event()
                    self._transitions[gid] = (done, me, 'create')
                    break
            event, owner, _ = busy
            if owner == me:
                return None  # 建会话的过程中又要这个会话(start() 里):还没好
            if not event.wait(TRANSITION_WAIT):
                log.warning("bot: timed out waiting for the session of %s", gid)
                return None
            # 建好了就拿到;刚休眠完就重新建
        try:
            log.info("bot: starting the session of %s", gid or '-')
            return self._create_session(gid, startup=startup)
        except Exception:
            if raise_errors:
                raise
            log.exception("bot: could not start the session of %s", gid or '-')
            return None
        finally:
            with self._lock:
                self._transitions.pop(gid, None)
            done.set()

    def request_session(self, guild_id):
        """DiscordClient 在事件循环里调用,必须马上返回:没有会话就在线程池里建一个。
        返回 None(有了 / 在建了)或拒绝理由。"""
        gid = str(guild_id or '')
        with self._lock:
            if gid in self._sessions:
                return None
            busy = self._transitions.get(gid)
            if busy is not None and busy[2] == 'create':
                return None
            if busy is None:
                refusal = self._refusal(gid)
                if refusal is not None:
                    return refusal
        try:
            # 和休眠同一个 key:正在休眠的话等它做完再建
            self.executor.submit((gid, 'session'), self._ensure, gid)
        except RuntimeError:
            return STARTING_REPLY
        return None

    # =====================================================================
    #   休眠
    # =====================================================================

    def check_idle(self, now=None):
        """闲置够久的会话交给线程池休眠。返回这次要休眠的服务器。"""
        minutes = self.idle_minutes
        if minutes <= 0 or self.exit:
            return []
        now = time.time() if now is None else now
        due = []
        for gid, session in self.sessions_by_id().items():
            with self._lock:
                skip = gid in self._pinned or gid in self._transitions
            try:
                idle = not skip and session.is_idle()
            except Exception:
                log.debug("bot: idle check of %s failed", gid, exc_info=True)
                idle = False
            with self._lock:
                if not idle:
                    self._idle_since.pop(gid, None)
                    continue
                since = self._idle_since.setdefault(gid, now)
                if now - since >= minutes * 60:
                    self._idle_since.pop(gid, None)
                    due.append(gid)
        for gid in due:
            try:
                self.executor.submit((gid, 'session'), self.hibernate, gid)
            except RuntimeError:
                break
        return due

    def hibernate(self, guild_id, reason='idle', force=False):
        """停掉这个服务器的会话:存队列、停播放循环、断开 GuildLink、去掉它的账号状态。数据都留着,
        下次 session_for 时恢复。reason 为 'idle' 时再确认一次还闲着。force:主服务器也停。"""
        gid = str(guild_id or '')
        with self._lock:
            session = self._sessions.get(gid)
            if session is None or gid in self._transitions:
                return False
            if gid in self._pinned and not force:
                return False
            if reason == 'idle':
                try:
                    if not session.is_idle():
                        return False
                except Exception:
                    return False
            done = threading.Event()
            self._transitions[gid] = (done, threading.get_ident(), 'hibernate')
            del self._sessions[gid]
            thread = self._threads.pop(gid, None)
            self._idle_since.pop(gid, None)
        try:
            log.info("bot: session of %s goes to sleep (%s)", gid, reason)
            session.stop_session()
            # 先断开连接:之后的交互不再交给这个会话(DiscordClient 会请我们重新建一个,
            # 建会话和休眠在同一个 key 上,等这里做完才开始,读到的是刚存好的队列)
            link = getattr(session, 'link', None)
            if link is not None:
                link.close(f'hibernated ({reason})')
            if thread is not None and thread is not threading.current_thread():
                thread.join(LOOP_JOIN_TIMEOUT)
            if thread is None or thread.is_alive():
                session.save_queue()  # 播放循环退出时自己会存;没跑 / 没退出就在这里存
            release = getattr(session, 'release', None)
            if release is not None:
                release()
        except Exception:
            log.exception("bot: error while putting the session of %s to sleep", gid)
        finally:
            self.report_activity(gid, None)
            with self._lock:
                self._transitions.pop(gid, None)
            done.set()
        return True

    def _on_guild_joined(self, guild_id):
        log.info("bot: added to server %s; its session starts on first use", guild_id)

    def _on_guild_removed(self, guild_id):
        """bot 被移出服务器:停掉会话(数据留着,再被邀请回来接着用)。在事件循环里调用。"""
        gid = str(guild_id)
        with self._members_lock:
            self._members = {k: v for k, v in self._members.items() if k[0] != gid}
        with self._lock:
            if gid not in self._sessions:
                return
        try:
            self.executor.submit((gid, 'session'), self.hibernate, gid, 'removed from the server', True)
        except RuntimeError:
            pass

    # =====================================================================
    #   运行 / 退出
    # =====================================================================

    def run(self):
        """主线程:启动各会话的播放循环,等到全部退出(Ctrl-C、/kill、连接断开),再断开 Discord。
        返回进程退出码。"""
        if not self.exit:
            with self._lock:
                self._running = True
                for gid, session in self._sessions.items():
                    if gid not in self._threads:
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
            with self._lock:
                # 休眠时先把线程摘下再停:那是故意停的,不是出事了
                current = self._threads.get(gid) is threading.current_thread()
            if not self.exit and current:
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
        self.timers.shutdown()
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
            try:
                self.check_idle(now)
            except Exception:
                log.exception("bot: idle check failed")

    def _loops(self):
        """[(guild id, 会话, 播放循环线程或 None)]:只有在运行的会话(休眠的不算)。"""
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
        """每个在运行的会话的播放循环都活着、最近转过。"""
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
        """在运行的会话(DJBot);休眠的不在里面。"""
        with self._lock:
            return list(self._sessions.values())

    def sessions_by_id(self):
        with self._lock:
            return dict(self._sessions)

    @property
    def home_guild_id(self):
        return self._home

    def guild_ids(self):
        """bot 加入的、允许服务的服务器。"""
        client = self.client
        if client is None:
            return [self._home] if self._home else []
        return [str(gid) for gid in client.guild_ids() if self._allowed(str(gid))]

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
