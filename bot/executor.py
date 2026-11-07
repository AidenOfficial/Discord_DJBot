# coding=utf-8
"""按 key 串行、不同 key 并行的共享线程池。

多服务器时不能每个服务器开几条常驻线程(命令线程、事件线程……)。所有服务器共用一个池:
同一个 key(如 (guild_id, 'cmd'))的任务按提交顺序一个接一个跑,不同 key 的任务并行。
一个服务器里慢吞吞的命令不会拖住它自己的语音事件((gid, 'evt')),更不会拖住别的服务器。

工作线程按需创建、空闲一会儿自己退出;运行任务时线程名带上 key,日志里看得出是哪个服务器。
定时任务(跟随检查的防抖等)也不各开线程:Timers 一个线程管全部,到点交给线程池。
"""

import collections
import concurrent.futures
import heapq
import logging
import threading
import time

log = logging.getLogger("bot")

#: 空闲多久(秒)工作线程退出
IDLE_EXIT = 60.0


def _label(key):
    if isinstance(key, tuple):
        return ':'.join(str(k) for k in key)
    return str(key)


class KeyedExecutor:
    def __init__(self, max_workers=16, name='Worker'):
        self._max = max(1, int(max_workers))
        self._name = name
        self._cond = threading.Condition()
        self._pending = {}                     # key -> deque[(future, fn, args, kwargs)];有 key 说明在排队或在跑
        self._ready = collections.deque()      # 可以开跑的 key(没有同 key 的任务正在跑)
        self._workers = 0
        self._idle = 0
        self._counter = 0
        self._shutdown = False

    def submit(self, key, fn, *args, **kwargs):
        """提交任务,返回 concurrent.futures.Future。任务里的异常记日志并放进 future。"""
        future = concurrent.futures.Future()
        with self._cond:
            if self._shutdown:
                raise RuntimeError('executor is shut down')
            tasks = self._pending.get(key)
            if tasks is None:
                self._pending[key] = collections.deque([(future, fn, args, kwargs)])
                self._ready.append(key)
                self._wake_or_spawn()
            else:
                # 同 key 的任务正在跑或在排队:跟在后面,跑完前一个时自动接上
                tasks.append((future, fn, args, kwargs))
        return future

    def pending(self, key):
        """这个 key 还有没跑完的任务吗。"""
        with self._cond:
            return key in self._pending

    def shutdown(self):
        """不再接新任务;已经排队的照常跑完(工作线程是 daemon,不阻塞进程退出)。"""
        with self._cond:
            self._shutdown = True
            self._cond.notify_all()

    # ---- 内部 ----

    def _wake_or_spawn(self):
        # 持锁调用。被唤醒的空闲线程要等拿到锁才把 _idle 减掉,所以按"就绪的 key 比空闲线程多"判断要不要加线程
        self._cond.notify()
        if len(self._ready) <= self._idle or self._workers >= self._max:
            return  # 有空闲线程接手,或者都在忙:等哪个跑完了接着取
        self._workers += 1
        self._counter += 1
        name = f"{self._name}-{self._counter}"
        threading.Thread(target=self._work, args=(name,), name=name, daemon=True).start()

    def _next_key(self):
        # 持锁调用;没活干时等,空闲太久返回 None(线程退出)
        while not self._ready:
            if self._shutdown:
                return None
            self._idle += 1
            try:
                woke = self._cond.wait(IDLE_EXIT)
            finally:
                self._idle -= 1
            if not woke and not self._ready:
                return None
        return self._ready.popleft()

    def _work(self, name):
        thread = threading.current_thread()
        while True:
            with self._cond:
                key = self._next_key()
                if key is None:
                    self._workers -= 1
                    return
                future, fn, args, kwargs = self._pending[key][0]
            thread.name = f"{name}[{_label(key)}]"
            try:
                if future.set_running_or_notify_cancel():
                    try:
                        future.set_result(fn(*args, **kwargs))
                    except BaseException as e:  # noqa: BLE001 - 一个任务出错不能带走工作线程
                        log.exception("executor: task %s for %s failed", getattr(fn, '__name__', fn), _label(key))
                        future.set_exception(e)
            finally:
                thread.name = name
                with self._cond:
                    tasks = self._pending[key]
                    tasks.popleft()
                    if tasks:
                        # 同 key 还有任务:排到就绪队尾(别的 key 也有机会),不在本线程里连着跑
                        self._ready.append(key)
                        if self._idle > 0:
                            self._cond.notify()
                    else:
                        del self._pending[key]


class Timers:
    """一个线程管所有服务器的定时任务(以前每次防抖都开一个 threading.Timer 线程)。

    schedule(slot, delay, key, fn, *args):delay 秒后把 fn 交给 executor 按 key 执行;同一个 slot
    再 schedule 会替换掉还没到点的那个(防抖)。没给 executor 就在定时线程里直接调用(要很快返回)。
    """

    def __init__(self, executor=None, name='Timers'):
        self.executor = executor
        self._name = name
        self._cond = threading.Condition()
        self._slots = {}                       # slot -> (到点时间, 序号, key, fn, args)
        self._heap = []                        # (到点时间, 序号, slot)
        self._seq = 0
        self._thread = None
        self._shutdown = False

    def schedule(self, slot, delay, key, fn, *args):
        due = time.monotonic() + max(0.0, float(delay))
        with self._cond:
            if self._shutdown:
                return
            self._seq += 1
            self._slots[slot] = (due, self._seq, key, fn, args)
            heapq.heappush(self._heap, (due, self._seq, slot))
            if self._thread is None:
                self._thread = threading.Thread(target=self._run, name=self._name, daemon=True)
                self._thread.start()
            self._cond.notify()

    def cancel(self, slot):
        with self._cond:
            return self._slots.pop(slot, None) is not None

    def scheduled(self, slot):
        with self._cond:
            return slot in self._slots

    def shutdown(self):
        with self._cond:
            self._shutdown = True
            self._slots.clear()
            self._heap.clear()
            self._cond.notify_all()

    def _run(self):
        while True:
            with self._cond:
                fire = None
                while fire is None:
                    if self._shutdown:
                        return
                    now = time.monotonic()
                    while self._heap and self._heap[0][0] <= now:
                        _, seq, slot = heapq.heappop(self._heap)
                        entry = self._slots.get(slot)
                        if entry is not None and entry[1] == seq:  # 被替换 / 取消的旧条目直接丢掉
                            del self._slots[slot]
                            fire = entry
                            break
                    if fire is None:
                        self._cond.wait(self._heap[0][0] - now if self._heap else None)
            _, _, key, fn, args = fire
            executor = self.executor
            try:
                if executor is not None:
                    executor.submit(key, fn, *args)
                else:
                    fn(*args)
            except RuntimeError:
                if executor is not None:
                    return  # 线程池已关闭(正在退出)
                log.exception("timers: %s failed", getattr(fn, '__name__', fn))
            except Exception:
                log.exception("timers: %s failed", getattr(fn, '__name__', fn))


_default_timers = None
_default_lock = threading.Lock()


def default_timers():
    """没有 Hub 时(测试替身)共用的那个:回调直接在定时线程里跑。"""
    global _default_timers
    with _default_lock:
        if _default_timers is None:
            _default_timers = Timers(name='Timers-default')
        return _default_timers
