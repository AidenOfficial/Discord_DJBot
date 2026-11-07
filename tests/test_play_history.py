import os
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import PlayHistoryDatabase  # noqa: E402


class PlayHistoryTestCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.db = PlayHistoryDatabase(os.path.join(self.dir.name, 'music.db'))

    def tearDown(self):
        self.dir.cleanup()

    def seed(self):
        # deterministic timestamps: two days, known local hours
        base = time.mktime((2026, 7, 1, 20, 0, 0, 0, 0, -1))  # 20:00 local
        self.db.record('a', 'Song A', 'url', 'alice', 180, base)
        self.db.record('a', 'Song A', 'url', 'bob', 180, base + 3600)      # 21:00
        self.db.record('b', 'Song B', 'file', 'alice', 240, base + 7200)   # 22:00
        self.db.record('c', 'Song C', 'url', 'carol', 0, base + 86400)     # next day 20:00
        return base

    def test_record_and_totals(self):
        self.seed()
        stats = self.db.stats()
        self.assertEqual(4, stats['total_plays'])
        self.assertEqual(600, stats['total_seconds'])
        self.assertEqual(3, stats['unique_tracks'])

    def test_top_tracks_and_users(self):
        self.seed()
        stats = self.db.stats()
        self.assertEqual('a', stats['top_tracks'][0]['item_id'])
        self.assertEqual(2, stats['top_tracks'][0]['count'])
        self.assertEqual('alice', stats['top_users'][0]['user'])
        self.assertEqual(2, stats['top_users'][0]['count'])

    def test_by_type(self):
        self.seed()
        by_type = {row['type']: row['count'] for row in self.db.stats()['by_type']}
        self.assertEqual({'url': 3, 'file': 1}, by_type)

    def test_hour_histogram(self):
        self.seed()
        hours = self.db.stats()['hours']
        self.assertEqual(24, len(hours))
        self.assertEqual(2, hours[20])  # two plays at 20:00 local
        self.assertEqual(1, hours[21])
        self.assertEqual(1, hours[22])
        self.assertEqual(4, sum(hours))

    def test_busiest_day(self):
        self.seed()
        busiest = self.db.stats()['busiest_day']
        self.assertEqual('2026-07-01', busiest['date'])
        self.assertEqual(3, busiest['count'])

    def test_mark_skipped_hits_latest_play(self):
        base = self.seed()
        self.db.record('a', 'Song A', 'url', 'dave', 180, base + 999999)
        self.db.mark_skipped('a')
        stats = self.db.stats()
        self.assertEqual(1, len(stats['most_skipped']))
        self.assertEqual('a', stats['most_skipped'][0]['item_id'])
        self.assertEqual(1, stats['most_skipped'][0]['count'])
        # only the latest row for 'a' was flagged
        import sqlite3
        conn = sqlite3.connect(self.db.db_path)
        flagged = conn.execute(
            "SELECT user FROM play_history WHERE skipped = 1").fetchall()
        conn.close()
        self.assertEqual([('dave',)], flagged)

    def test_mark_skipped_unknown_item_is_noop(self):
        self.seed()
        self.db.mark_skipped('zzz')
        self.assertEqual([], self.db.stats()['most_skipped'])

    def test_guild_filter(self):
        base = self.seed()                                      # 4 条旧记录:guild_id 是 NULL
        self.db.record('x', 'Song X', 'url', 'eve', 60, base + 10, guild_id='1')
        self.db.record('y', 'Song Y', 'url', 'eve', 60, base + 20, guild_id='2')
        self.db.record('y', 'Song Y', 'url', 'eve', 60, base + 30, guild_id='2')
        self.assertEqual(7, self.db.stats()['total_plays'])
        self.assertEqual(1, self.db.stats(guild_id='1')['total_plays'])
        self.assertEqual(5, self.db.stats(guild_id='1', include_unscoped=True)['total_plays'])
        two = self.db.stats(guild_id=2)
        self.assertEqual((2, 1), (two['total_plays'], two['unique_tracks']))
        self.assertEqual([{'item_id': 'y', 'title': 'Song Y', 'count': 2}], two['top_tracks'])
        self.assertEqual(0, self.db.stats(guild_id='3')['total_plays'])

    def test_mark_skipped_per_guild(self):
        base = time.time()
        self.db.record('a', 'Song A', 'url', 'u', 60, base, guild_id='1')
        self.db.record('a', 'Song A', 'url', 'u', 60, base + 5, guild_id='2')   # 另一个服务器更晚放
        self.db.mark_skipped('a', guild_id='1')
        self.assertEqual(1, len(self.db.stats(guild_id='1')['most_skipped']))
        self.assertEqual([], self.db.stats(guild_id='2')['most_skipped'])

    def test_old_table_gets_guild_column(self):
        import sqlite3
        path = os.path.join(self.dir.name, 'old.db')
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE play_history (id INTEGER PRIMARY KEY AUTOINCREMENT, item_id TEXT NOT NULL, "
                     "title TEXT NOT NULL DEFAULT '', type TEXT NOT NULL DEFAULT '', user TEXT NOT NULL DEFAULT '', "
                     "duration REAL NOT NULL DEFAULT 0, played_at REAL NOT NULL, skipped INTEGER NOT NULL DEFAULT 0)")
        conn.execute("INSERT INTO play_history (item_id, played_at) VALUES ('old', 1)")
        conn.commit()
        conn.close()
        db = PlayHistoryDatabase(path)
        PlayHistoryDatabase(path)                               # 第二次打开不再 ALTER
        db.record('new', 'N', 'url', 'u', guild_id='9')
        self.assertEqual(1, db.stats(guild_id='9')['total_plays'])
        self.assertEqual(2, db.stats(guild_id='9', include_unscoped=True)['total_plays'])

    def test_empty_db_stats(self):
        stats = self.db.stats()
        self.assertEqual(0, stats['total_plays'])
        self.assertEqual([0] * 24, stats['hours'])
        self.assertIsNone(stats['busiest_day'])
        self.assertEqual([], stats['top_tracks'])


class LaunchInstrumentationTestCase(unittest.TestCase):
    """launch_music must append exactly one history row per fresh start."""

    def test_record_on_fresh_start_only(self):
        import variables as var
        from bot.player import PlayerMixin

        class Recorder:
            rows = []

            def record(self, *args, **kwargs):
                self.rows.append(args)

        class FakeItem:
            id = 'x1'
            type = 'url'
            duration = 100

            def format_title(self):
                return 'T'

        class FakeWrapper:
            user = 'alice'

            def item(self):
                return FakeItem()

            def uri(self):
                return '/nope'

            def is_ready(self):
                return True

            def format_debug_string(self):
                return 'dbg'

            def format_current_playing(self):
                return 'np'

            def playable_from(self, *a):
                return True

        import configparser
        from unittest import mock
        saved = var.play_history, var.config
        var.play_history = Recorder()
        # launch_music 在记录之前就要读配置;以前靠别的测试模块泄漏的 var.config 才能通过
        var.config = configparser.ConfigParser(interpolation=None, allow_no_value=True)
        var.config.read(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                     'configuration.default.ini'), encoding='utf-8')
        try:
            player = PlayerMixin.__new__(PlayerMixin)
            import logging
            player.log = logging.getLogger('test')
            recorded = []
            Recorder.rows = recorded

            # Only exercise the instrumentation block, not the ffmpeg launch:
            # call launch_music and swallow the failure once it gets past the
            # recording step (Popen is stubbed so no ffmpeg is spawned).
            with mock.patch('bot.player.sp.Popen', side_effect=OSError('no ffmpeg in tests')):
                for start_from in (0, 42.5):
                    try:
                        player.launch_music(FakeWrapper(), start_from)
                    except Exception:
                        pass
            self.assertEqual(1, len(recorded))
            self.assertEqual(('x1', 'T', 'url', 'alice', 100), recorded[0])
        finally:
            var.play_history, var.config = saved


if __name__ == '__main__':
    unittest.main()
