# coding=utf-8
"""KeyedExecutor:同一个 key 按顺序,不同 key 并行,出错不影响后面的任务。"""
import os
import sys
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot import executor as ex  # noqa: E402
from bot.executor import KeyedExecutor  # noqa: E402


class KeyedExecutorTest(unittest.TestCase):
    def test_same_key_runs_in_submission_order(self):
        pool = KeyedExecutor(max_workers=8, name='T')
        order = []
        running = []

        def task(n):
            running.append(n)
            assert len(running) == 1, "two tasks of one key ran at once"
            time.sleep(0.005)
            order.append(n)
            running.remove(n)

        futures = [pool.submit(('g', 'cmd'), task, n) for n in range(20)]
        for f in futures:
            f.result(5)
        self.assertEqual(order, list(range(20)))
        self.assertFalse(pool.pending(('g', 'cmd')))

    def test_different_keys_run_in_parallel(self):
        pool = KeyedExecutor(max_workers=4, name='T')
        a_started, b_done = threading.Event(), threading.Event()

        def a():
            a_started.set()
            return b_done.wait(2)       # 只有 b 能并行跑完,a 才会返回 True

        def b():
            a_started.wait(2)
            b_done.set()

        fa = pool.submit(('1', 'cmd'), a)
        fb = pool.submit(('2', 'cmd'), b)
        self.assertTrue(fa.result(3))
        fb.result(3)

    def test_slow_command_does_not_block_events_of_the_same_guild(self):
        pool = KeyedExecutor(max_workers=4, name='T')
        release = threading.Event()
        pool.submit(('1', 'cmd'), release.wait, 2)
        self.assertEqual(pool.submit(('1', 'evt'), lambda: 'event').result(1), 'event')
        release.set()

    def test_errors_are_contained(self):
        pool = KeyedExecutor(max_workers=2, name='T')

        def boom():
            raise RuntimeError('kaboom')

        failed = pool.submit('k', boom)
        after = pool.submit('k', lambda: 'still running')
        with self.assertRaises(RuntimeError):
            failed.result(2)
        self.assertEqual(after.result(2), 'still running')

    def test_worker_count_is_bounded_and_threads_named(self):
        pool = KeyedExecutor(max_workers=2, name='Pool')
        release = threading.Event()
        names = []

        def task():
            names.append(threading.current_thread().name)
            release.wait(2)

        futures = [pool.submit(('g', n), task) for n in range(5)]
        time.sleep(0.1)
        self.assertEqual(len(names), 2)                     # 最多 2 个同时跑,其余排队
        release.set()
        for f in futures:
            f.result(3)
        self.assertEqual(len(names), 5)
        self.assertTrue(all(n.startswith('Pool-') and '[g:' in n for n in names))  # 日志里看得出是哪个服务器

    def test_idle_workers_exit(self):
        pool = KeyedExecutor(max_workers=2, name='T')
        with mock.patch.object(ex, 'IDLE_EXIT', 0.05):
            pool.submit('k', lambda: None).result(2)
            deadline = time.time() + 2
            while pool._workers and time.time() < deadline:
                time.sleep(0.01)
        self.assertEqual(pool._workers, 0)
        self.assertEqual(pool.submit('k', lambda: 'again').result(2), 'again')

    def test_shutdown_refuses_new_work(self):
        pool = KeyedExecutor(max_workers=1, name='T')
        pool.shutdown()
        with self.assertRaises(RuntimeError):
            pool.submit('k', lambda: None)


class TimersTest(unittest.TestCase):
    def setUp(self):
        self.pool = KeyedExecutor(max_workers=4, name='T')
        self.timers = ex.Timers(self.pool, name='TestTimers')

    def tearDown(self):
        self.timers.shutdown()
        self.pool.shutdown()

    def test_runs_on_the_pool_under_its_key(self):
        names = []
        done = threading.Event()
        self.timers.schedule(('7', 'follow'), 0.02, ('7', 'evt'),
                             lambda: (names.append(threading.current_thread().name), done.set()))
        self.assertTrue(done.wait(2))
        self.assertIn('[7:evt]', names[0])
        self.assertFalse(self.timers.scheduled(('7', 'follow')))

    def test_same_slot_debounces_and_cancel(self):
        calls = []
        for n in range(5):
            self.timers.schedule('slot', 0.05, 'k', calls.append, n)
        self.timers.schedule('other', 0.01, 'k', calls.append, 'other')
        self.timers.schedule('gone', 0.01, 'k', calls.append, 'gone')
        self.assertTrue(self.timers.cancel('gone'))
        self.assertFalse(self.timers.cancel('gone'))
        time.sleep(0.3)
        self.assertEqual(calls, ['other', 4])               # 只有最后一次 schedule 生效,取消的不跑

    def test_one_thread_for_all_timers(self):
        before = threading.active_count()
        hits = []
        for n in range(50):
            self.timers.schedule(('g', n), 0.05, ('g', n), hits.append, n)
        self.assertLessEqual(threading.active_count(), before + 1)
        deadline = time.time() + 2
        while len(hits) < 50 and time.time() < deadline:
            time.sleep(0.01)
        self.assertEqual(sorted(hits), list(range(50)))

    def test_without_executor_runs_inline(self):
        timers = ex.Timers(name='Inline')
        done = threading.Event()
        timers.schedule('s', 0, None, done.set)
        self.assertTrue(done.wait(2))
        timers.shutdown()
        timers.schedule('s', 0, None, mock.Mock())          # 关了以后不再接


if __name__ == '__main__':
    unittest.main()
