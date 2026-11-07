# coding=utf-8
"""多个会话共用一个下载缓存:释放要看所有队列、下载全局只跑一份、失败的条目从每个队列移出。

用 monkeypatch 让 var.all_playlists() 返回两个队列,模拟两个服务器。"""
import os
import sys
import threading
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import variables as var  # noqa: E402
from bot import downloads  # noqa: E402
from bot.player import PlayerMixin  # noqa: E402
from media import playlist as mp  # noqa: E402
from media.cache import CachedItemWrapper, MusicCache, discard_everywhere  # noqa: E402
from tests.test_queue_integrity import Base, FakeItem, FakeProc, Player, fill, ids  # noqa: E402


def real_cache():
    cache = MusicCache(mock.Mock())
    cache.free_and_delete = mock.Mock(side_effect=lambda id: cache.pop(id, None))
    return cache


def W(id_, ready='yes'):
    if id_ not in var.cache:
        var.cache[id_] = FakeItem(id_, ready)
    return CachedItemWrapper(var.cache, id_, 'url', 'u')


class SharedCacheBase(Base):
    def setUp(self):
        super().setUp()
        var.cache = real_cache()
        self.queues = []
        patcher = mock.patch.object(var, 'all_playlists', lambda: list(self.queues))
        patcher.start()
        self.addCleanup(patcher.stop)

    def two_queues(self, a_ids, b_ids, cls=mp.RepeatPlaylist):
        qa = fill(cls(), [W(i) for i in a_ids], 0)
        qb = fill(cls(), [W(i) for i in b_ids], 0)
        self.queues[:] = [qa, qb]
        return qa, qb


class ReferenceAwareFreeTest(SharedCacheBase):
    def test_clear_keeps_items_another_queue_still_holds(self):
        qa, qb = self.two_queues('AS', 'SB')
        qa.clear()
        self.assertIn('S', var.cache)       # B 还排着
        self.assertNotIn('A', var.cache)    # 只有 A 用的释放掉
        self.assertTrue(qb[0].is_ready())   # 以前 free_all() 之后这里 ItemNotCachedError
        self.assertIn('B', var.cache)       # 别的队列独有的不受影响

    def test_remove_keeps_item_for_the_other_queue_then_frees_with_the_last(self):
        qa, qb = self.two_queues('AS', 'SB')
        qa.remove(1)
        self.assertIn('S', var.cache)
        qb.remove(0)
        self.assertNotIn('S', var.cache)

    def test_autoplay_clear_goes_through_the_same_rule(self):
        qa, qb = self.two_queues('S', 'S', cls=mp.OneshotPlaylist)
        auto = mp.AutoPlaylist()
        list.extend(auto, list(qa))
        self.queues[0] = auto
        with mock.patch.object(mp.AutoPlaylist, 'refresh'):
            auto.clear()
        self.assertIn('S', var.cache)

    def test_free_all_only_frees_unqueued_items(self):
        self.two_queues('A', 'B')
        var.cache['loose'] = FakeItem('loose')
        var.cache.free_all()
        self.assertEqual({'A', 'B'}, set(var.cache))


class SingleQueueTest(SharedCacheBase):
    def test_clear_frees_its_items(self):
        q = fill(mp.RepeatPlaylist(), [W('A'), W('B')], 0)
        self.queues[:] = [q]
        q.clear()
        self.assertEqual({}, dict(var.cache))

    def test_one_shot_frees_played_items_unless_another_queue_has_them(self):
        q, other = self.two_queues('ABS', 'S', cls=mp.OneshotPlaylist)
        q.next()
        self.assertNotIn('A', var.cache)
        q.next()
        self.assertEqual(['S'], ids(q))
        q.next()
        self.assertIn('S', var.cache)

    def test_clear_frees_items_left_behind_by_a_mode_switch(self):
        # 换成 one-shot 时当前曲之前的条目直接从列表里拿掉、不释放;以前靠 clear() 的 free_all() 回收
        q = fill(mp.RepeatPlaylist(), [W('A'), W('B')], 1)
        q2 = mp.get_playlist('one-shot', q)
        self.assertEqual(['B'], ids(q2))
        self.queues[:] = [q2]
        self.assertIn('A', var.cache)
        q2.clear()
        self.assertEqual({}, dict(var.cache))

    def test_remove_frees_only_after_the_last_duplicate(self):
        q = fill(mp.RepeatPlaylist(), [W('A'), W('A'), W('B')], 0)
        self.queues[:] = [q]
        q.remove(0)
        self.assertIn('A', var.cache)
        q.remove(0)
        self.assertNotIn('A', var.cache)


class DiscardEverywhereTest(SharedCacheBase):
    def sessions(self, a_ids, b_ids):
        a, b = Player(), Player()
        a.set_playlist(fill(mp.RepeatPlaylist(), [W(i) for i in a_ids], 0))
        b.set_playlist(fill(mp.RepeatPlaylist(), [W(i) for i in b_ids], 0))
        self.queues[:] = [a.playlist, b.playlist]
        return a, b

    def test_failed_item_leaves_every_queue(self):
        a, b = self.sessions('XA', 'BX')
        discard_everywhere('X')
        self.assertEqual(['A'], ids(a.playlist))
        self.assertEqual(['B'], ids(b.playlist))
        var.cache.free_and_delete.assert_called_once_with('X')

    def test_queue_without_session_uses_remove_by_id(self):
        q = fill(mp.RepeatPlaylist(), [W('X'), W('A')], 0)
        self.queues[:] = [q]
        discard_everywhere('X')
        self.assertEqual(['A'], ids(q))

    def test_ffmpeg_failure_in_one_session_drops_it_from_the_other(self):
        a, b = self.sessions('X', 'BX')
        a.thread = FakeProc(1)
        a.run(1)
        self.assertNotIn('X', ids(a.playlist))
        self.assertEqual(['B'], ids(b.playlist))
        self.assertNotIn('X', var.cache)

    def test_validation_failure_drops_it_from_the_other_queue(self):
        from media.item import ValidationFailedError
        a, b = self.sessions('AX', 'X')
        var.cache['X'].validate = mock.Mock(side_effect=ValidationFailedError('too long'))
        a.playlist.pending_items.append(a.playlist[1])
        a.playlist._validate_pending()
        self.assertEqual(['A'], ids(a.playlist))
        self.assertEqual([], ids(b.playlist))
        self.assertEqual(['too long'], a.messages)  # 只在出问题的会话里说一次

    def test_queue_holding_a_deleted_item_skips_it_without_crashing(self):
        # 别的地方直接删了缓存(不在 all_playlists 里的队列、并发):主循环把它移出队列
        b = Player()
        b.set_playlist(fill(mp.RepeatPlaylist(), [W('X'), W('B')], 0))
        del var.cache['X']
        b.wait_for_ready = True
        self.assertEqual([], b.run(3))
        self.assertEqual(['B'], ids(b.playlist))
        self.assertEqual(['B'], b.launched)


class DownloadRegistryTest(Base):
    def test_only_one_concurrent_begin_wins(self):
        start = threading.Barrier(8)
        results = []

        def claim():
            start.wait()
            results.append(downloads.begin('X'))

        threads = [threading.Thread(target=claim) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(1, results.count(True))
        self.assertEqual(1, downloads.active_count())
        downloads.end('X')
        self.assertFalse(downloads.is_active('X'))
        downloads.end('X')  # 没登记也不报错
        self.assertTrue(downloads.begin('X'))

    def test_second_session_does_not_start_another_download(self):
        a, b = Player(), Player()
        item = W('X', ready='validated')
        # 用真的 async_download,只把线程换掉
        with mock.patch('bot.player.threading.Thread') as thread:
            self.assertIsNotNone(PlayerMixin.async_download(a, item))
            self.assertIsNone(PlayerMixin.async_download(b, item))
        self.assertEqual(2, thread.call_count)  # 只有 A 的下载线程 + 进度播报线程

    def test_waiting_session_waits_for_the_other_download_instead_of_failing_it(self):
        b = Player()
        b.set_playlist(fill(mp.RepeatPlaylist(), [W('X', ready='validated')], 0))
        b.wait_for_ready = True
        downloads.begin('X')    # 另一个会话正在下载
        self.assertEqual([], b.run(10))
        self.assertEqual([], b.downloads)
        self.assertEqual('validated', var.cache['X'].ready)  # 以前补发几次后被标成 failed
        self.assertEqual([], b.messages)
        var.cache['X'].ready = 'yes'
        downloads.end('X')
        b.run(1)
        self.assertEqual(['X'], b.launched)

    def test_prefetch_cap_counts_every_session(self):
        p = Player()
        p.set_playlist(fill(mp.RepeatPlaylist(), [W(i, ready='validated') for i in 'ABCD'], 0))
        var.config.set('bot', 'prefetch_count', '3')
        p._prefetch_upcoming()
        self.assertEqual(['C', 'D'], p.downloads)
        downloads.begin('other-1')
        downloads.begin('other-2')  # 别的服务器已经占满两个名额
        p.downloads.clear()
        p._prefetch_upcoming()
        self.assertEqual([], p.downloads)


class URLItemClaimTest(unittest.TestCase):
    def test_prepare_returns_at_once_while_another_thread_claimed_it(self):
        try:
            import media.url
        except Exception:
            self.skipTest('media.url deps missing')
        item = media.url.URLItem.__new__(media.url.URLItem)
        item.ready, item.downloading, item._preparing = 'validated', False, True
        item.is_ready = lambda: False
        item._download = mock.Mock()
        self.assertTrue(item.prepare())
        item._download.assert_not_called()

    def test_prepare_releases_its_claim(self):
        try:
            import media.url
        except Exception:
            self.skipTest('media.url deps missing')
        item = media.url.URLItem.__new__(media.url.URLItem)
        item.ready, item.downloading, item._preparing = 'validated', False, False
        item.is_ready = lambda: False
        item._download = mock.Mock(side_effect=RuntimeError('boom'))
        with self.assertRaises(RuntimeError):
            item.prepare()
        self.assertFalse(item._preparing)


if __name__ == '__main__':
    unittest.main()
