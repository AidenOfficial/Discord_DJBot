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


if __name__ == '__main__':
    unittest.main()
