# coding=utf-8
"""按 key 串行、不同 key 并行的共享线程池。

多服务器时不能每个服务器开几条常驻线程(命令线程、事件线程……)。所有服务器共用一个池:
同一个 key(如 (guild_id, 'cmd'))的任务按提交顺序一个接一个跑,不同 key 的任务并行。
一个服务器里慢吞吞的命令不会拖住它自己的语音事件((gid, 'evt')),更不会拖住别的服务器。

工作线程按需创建、空闲一会儿自己退出;运行任务时线程名带上 key,日志里看得出是哪个服务器。
"""

import collections
import concurrent.futures
import logging
import threading

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
