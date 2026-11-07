"""语音频道:服务器频道树、默认频道(Web 可配置)、自动跟随用户。

设置按服务器存(GuildStore,key 是 channel.<名字>),优先于 configuration.ini 的 [server] channel:
  default   默认语音频道路径(JSON 名字列表 [分类, 频道],不在分类里的频道就是 [频道];
            [] = 不自动进频道,等有人 /play 或 /join);启动时进这里
  follow    跟随模式:off / auto / user
              auto  所在频道没人了(只剩 bot)就去找人:优先去最后离开的那位去的频道,
                    否则去人最多的频道
              user  始终跟着 follow_user 指定的用户
  follow_user   user 模式下跟随的用户名
  return_home   服务器上一个人都没有时回到默认频道(1/0)
  idle_pause_minutes  bot 所在频道连续没人这么多分钟就自动暂停(0 = 关,默认 5)
  idle_resume         自动暂停后有人回来就自动继续播放(1/0,默认 1)

连接层的用户事件回调里只记录事件,真正的决策放到防抖定时器线程里做
(人在频道间来回切时不会被带着乱跑)。self.link 是 bot.discord_link.DiscordLink;
本模块不 import 通信库,单测用假的 link 对象即可。

Discord 的频道 dict 里多了 kind(guild / category / voice / stage)、joinable(bot 有权限进)、
afk(服务器的 AFK 频道)。根节点 0 是服务器本身,分类和语音频道挂在下面;只有 joinable 的
语音频道能进,跟随时也不会进 AFK 频道。
"""

import json
import logging
import threading
import time

from .session_queue import SessionQueue

log = logging.getLogger("bot")

FOLLOW_MODES = ('off', 'auto', 'user')
PREFIX = 'channel.'
DEBOUNCE_SECONDS = 2.5
LAST_LEAVER_TTL = 60  # "最后离开的人去了哪"多久内有效


class ChannelMixin(SessionQueue):

    # ---- 设置 -----------------------------------------------------------

    def _channel_opt(self, name, default=None):
        return self.setting(PREFIX + name, default)

    def channel_settings(self):
        default = None
        raw = self._channel_opt('default')
        if raw is not None:
            try:
                default = json.loads(raw)
            except ValueError:
                default = None
        if default is None:
            # 没在 Web 上配置过:沿用 ini / 命令行的 channel(A/B 形式)
            default = [p for p in (self.channel or '').split('/') if p]
        mode = self._channel_opt('follow', 'off')
        return {
            'default': default,
            'follow': mode if mode in FOLLOW_MODES else 'off',
            'follow_user': self._channel_opt('follow_user', ''),
            'return_home': self._channel_opt('return_home', '1') == '1',
            'idle_pause_minutes': self._idle_minutes(),
            'idle_resume': self._channel_opt('idle_resume', '1') == '1',
        }

    def _idle_minutes(self):
        try:
            return max(0, int(self._channel_opt('idle_pause_minutes', '5')))
        except ValueError:
            return 5

    def save_channel_settings(self, default=None, follow=None, follow_user=None, return_home=None,
                              idle_pause_minutes=None, idle_resume=None):
        if follow is not None and follow not in FOLLOW_MODES:
            raise ValueError(follow)
        if default is not None:
            self.save_setting(PREFIX + 'default', json.dumps(list(default), ensure_ascii=False))
        if follow is not None:
            self.save_setting(PREFIX + 'follow', follow)
        if follow_user is not None:
            self.save_setting(PREFIX + 'follow_user', follow_user)
        if return_home is not None:
            self.save_setting(PREFIX + 'return_home', '1' if return_home else '0')
        if idle_pause_minutes is not None:
            self.save_setting(PREFIX + 'idle_pause_minutes', str(max(0, int(idle_pause_minutes))))
        if idle_resume is not None:
            self.save_setting(PREFIX + 'idle_resume', '1' if idle_resume else '0')
        self.schedule_follow_check(delay=0.2)

    # ---- 频道树 -----------------------------------------------------------

    def _channels(self):
        return dict(self.link.channels)

    def _users(self):
        return list(self.link.users.values())

    def my_channel_id(self):
        return self.link.my_channel_id

    def channel_display_name(self, channel_id):
        ch = self._channels().get(channel_id)
        return ch.get('name', '?') if ch else '?'

    def channel_path(self, channel_id, channels=None):
        """根频道 -> [];其余返回从根往下的名字列表。"""
        channels = channels or self._channels()
        path = []
        seen = set()
        current = channels.get(channel_id)
        while current is not None and current.get('channel_id', 0) != 0 and current['channel_id'] not in seen:
            seen.add(current['channel_id'])
            path.insert(0, current.get('name', ''))
            current = channels.get(current.get('parent'))
        return path

    def find_channel_by_path(self, path, channels=None):
        """按名字逐级向下找,返回 channel_id;找不到返回 None。
        也接受只有一个元素的频道 ID(配置文件里直接写 ID 最不容易错)。"""
        channels = channels or self._channels()
        if len(path) == 1 and str(path[0]).isdigit() and int(path[0]) in channels:
            return int(path[0])
        current = 0 if 0 in channels else None
        if current is None:
            return None
        for name in path:
            nxt = None
            for cid, ch in channels.items():
                if ch.get('parent') == current and cid != current and ch.get('name') == name:
                    nxt = cid
                    break
            if nxt is None:
                return None
            current = nxt
        return current

    def _is_ignored(self, user):
        """bot 自己和 when_nobody_in_channel_ignore 里列出的其他 bot 不算人。"""
        myself = self.link.myself
        if myself is not None and user.session == myself.session:
            return True
        if getattr(user, 'bot', False):
            return True
        return user.name in getattr(self, 'bots', set())

    def _joinable(self, channel_id, channels=None):
        ch = (channels or self._channels()).get(channel_id)
        return bool(ch) and ch.get('joinable', True) and ch.get('kind', 'voice') == 'voice'

    def _follow_candidate(self, channel_id, channels):
        ch = channels.get(channel_id)
        return self._joinable(channel_id, channels) and not ch.get('afk')

    def humans_by_channel(self):
        counts = {}
        for user in self._users():
            if self._is_ignored(user):
                continue
            counts.setdefault(user.channel_id, []).append(user)
        return counts

    def channel_tree(self):
        """给 Web 用的嵌套频道树快照。"""
        channels = self._channels()
        users = self._users()
        myself = self.link.myself
        by_channel = {}
        for u in users:
            by_channel.setdefault(u.channel_id, []).append({
                'session': u.session,
                'name': u.name,
                'is_me': myself is not None and u.session == myself.session,
                'is_bot': self._is_ignored(u),
                'is_bot_account': bool(getattr(u, 'bot', False)),
                'muted': bool(getattr(u, 'self_mute', False) or getattr(u, 'mute', False)),
                'deafened': bool(getattr(u, 'self_deaf', False) or getattr(u, 'deaf', False)),
            })
        children = {}
        for cid, ch in channels.items():
            if cid == 0:
                continue
            children.setdefault(ch.get('parent', 0), []).append(cid)

        def node(cid, depth=0):
            ch = channels[cid]
            kids = sorted(children.get(cid, []),
                          key=lambda c: (channels[c].get('position', 0), channels[c].get('name', '')))
            return {
                'id': cid,
                'name': ch.get('name') or ('Root' if cid == 0 else '?'),
                'path': self.channel_path(cid, channels),
                'temporary': bool(ch.get('temporary', False)),
                'kind': ch.get('kind', 'voice'),
                'joinable': self._joinable(cid, channels),
                'afk': bool(ch.get('afk', False)),
                'users': sorted(by_channel.get(cid, []), key=lambda u: u['name'].lower()),
                'children': [node(k, depth + 1) for k in kids if depth < 32],
            }

        return node(0) if 0 in channels else None

    # ---- 移动 -------------------------------------------------------------

    def move_to_channel(self, channel_id, reason=''):
        if channel_id is None or channel_id == self.my_channel_id():
            return False
        if not self._joinable(channel_id):
            return False
        log.info("channel: moving to %s%s", '/'.join(self.channel_path(channel_id)) or '(root)',
                 f" ({reason})" if reason else '')
        return self.link.move(channel_id)

    def join_channel(self):
        """去默认频道(启动时调用)。没配置默认频道就不动。"""
        path = self.channel_settings()['default']
        if not path:
            return
        cid = self.find_channel_by_path(path)
        if cid is None:
            log.warning("channel: default channel %s not found on the server", '/'.join(path))
            return
        self.move_to_channel(cid, 'default channel')

    # ---- 跟随 -------------------------------------------------------------

    def _init_follow(self):
        self._follow_lock = threading.Lock()
        self._follow_timer = None
        self._user_channels = {}  # session -> channel_id,用来知道"从哪个频道走的"
        self._last_leaver = None  # (time, 去向 channel_id 或 None=下线)

    def _note_user_event(self, user, kind):
        """在连接层的用户事件回调里调用:只记账,不做决策。"""
        if not hasattr(self, '_follow_lock'):
            self._init_follow()
        mine = self.my_channel_id()
        old = self._user_channels.get(user.session)
        if kind == 'removed':
            self._user_channels.pop(user.session, None)
            if old is not None and old == mine and not self._is_ignored(user):
                self._last_leaver = (time.time(), None)
        else:
            new = getattr(user, 'channel_id', 0)
            self._user_channels[user.session] = new
            if old is not None and old != new and old == mine and not self._is_ignored(user):
                self._last_leaver = (time.time(), new)
        self.schedule_follow_check()

    def schedule_follow_check(self, delay=DEBOUNCE_SECONDS):
        if not hasattr(self, '_follow_lock'):
            self._init_follow()
        with self._follow_lock:
            if self._follow_timer is not None:
                self._follow_timer.cancel()
            self._follow_timer = threading.Timer(delay, self._safe_follow_check)
            self._follow_timer.daemon = True
            self._follow_timer.start()

    def _safe_follow_check(self):
        try:
            self.follow_check()
        except Exception:
            log.exception("channel: follow check failed")

    def follow_target(self):
        """按当前设置算出应该去的频道;不需要移动返回 None。"""
        settings = self.channel_settings()
        mode = settings['follow']
        mine = self.my_channel_id()
        channels = self._channels()
        humans = {cid: users for cid, users in self.humans_by_channel().items()
                  if cid == mine or self._follow_candidate(cid, channels)}

        if mode == 'user':
            name = settings['follow_user']
            for users in humans.values():
                for u in users:
                    if name in (u.name, getattr(u, 'username', None), str(u.session)):
                        return u.channel_id if u.channel_id != mine else None
            # 跟随对象不在线:退回到"空了就找人"的逻辑
        elif mode != 'auto':
            return None

        if mine is None:
            return None  # 不在语音里(还没人叫过 / 被 /leave 了):不主动进频道
        if humans.get(mine):
            return None  # 本频道还有人,不动
        if self._last_leaver and time.time() - self._last_leaver[0] < LAST_LEAVER_TTL:
            target = self._last_leaver[1]
            if target is not None and humans.get(target):
                return target
        if humans:
            # 人最多的频道;平手取 id 小的,结果稳定
            others = {cid: users for cid, users in humans.items() if cid != mine}
            if others:
                return max(others, key=lambda cid: (len(others[cid]), -cid))
        if settings['return_home'] and settings['default']:
            home = self.find_channel_by_path(settings['default'])
            if home is not None and home != mine:
                return home
        return None

    def follow_check(self):
        target = self.follow_target()
        if target is not None and self.move_to_channel(target, 'following users'):
            self._last_leaver = None

    def follow_would_move(self):
        """when_nobody_in_channel 用:跟随马上要带 bot 去别的频道时,就别暂停/清空了。"""
        try:
            return self.follow_target() is not None
        except Exception:
            return False

    # ---- 无人自动暂停 -------------------------------------------------------

    def idle_tick(self, now=None):
        """主循环里调用(内部节流到每 2 秒一次)。频道连续没人 N 分钟 -> 暂停;
        自动暂停后有人回来 -> 继续。只恢复自己暂停的,不会替人恢复手动暂停。"""
        now = now if now is not None else time.time()
        if now - getattr(self, '_idle_last_tick', 0.0) < 2:
            return
        self._idle_last_tick = now
        try:
            self._idle_check(now)
        finally:
            # 在最后记录:本轮自己调用的 pause()/resume() 也要算进"上一轮的状态"
            self._idle_was_paused = self.is_pause

    def _idle_check(self, now):
        settings = self.channel_settings()
        mine = self.my_channel_id()
        if mine is None:
            return
        humans = self.humans_by_channel().get(mine)

        if not self.is_pause:
            if getattr(self, '_idle_paused', False):
                self._idle_paused = False  # 有人手动恢复了
            if getattr(self, '_idle_was_paused', False):
                self._empty_since = now   # 刚从暂停恢复,重新计时

        if humans:
            self._empty_since = None
            if getattr(self, '_idle_paused', False):
                self._idle_paused = False
                if settings['idle_resume'] and self.is_pause:
                    log.info("channel: someone is back, resuming playback")
                    self.resume()
            return

        if getattr(self, '_empty_since', None) is None:
            self._empty_since = now
        minutes = settings['idle_pause_minutes']
        if minutes <= 0 or self.is_pause or len(self.playlist) == 0:
            return
        if now - self._empty_since >= minutes * 60 and not self.follow_would_move():
            log.info("channel: nobody here for %d min, pausing playback", minutes)
            self.pause()
            self._idle_paused = True
