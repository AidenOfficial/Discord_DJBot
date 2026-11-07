# coding=utf-8
"""每个会话(服务器)自己的队列:bot.playlist / set_playlist、队列回指会话、校验失败找对会话。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import media.playlist as mp  # noqa: E402
import variables as var  # noqa: E402
from bot.player import PlayerMixin  # noqa: E402
from media.item import ValidationFailedError  # noqa: E402


class Session(PlayerMixin):
    def __init__(self):
        self.messages = []
        self.dropped = []

    def send_channel_msg(self, msg):
        self.messages.append(msg)

    def drop_from_queue(self, item_id):
        self.dropped.append(item_id)


class BadWrapper:
    """校验一定失败的条目。"""
    id = 'bad'
    version = 0

    def item(self):
        return self

    def format_debug_string(self):
        return 'bad'

    def validate(self):
        raise ValidationFailedError('nope')


class FakeCache:
    def __init__(self):
        self.deleted = []

    def free_and_delete(self, item_id):
        self.deleted.append(item_id)


def setup_function():
    global _saved
    _saved = (var.playlist, var.bot, var.cache)


def teardown_function():
    var.playlist, var.bot, var.cache = _saved


def test_unset_session_falls_back_to_global():
    var.playlist = mp.OneshotPlaylist()
    assert Session().playlist is var.playlist


def test_sessions_keep_their_own_queue():
    a, b = Session(), Session()
    qa, qb = mp.OneshotPlaylist(), mp.RepeatPlaylist()
    a.set_playlist(qa)
    b.set_playlist(qb)
    assert (a.playlist, b.playlist) == (qa, qb)
    assert (qa.session, qb.session) == (a, b)


def test_mode_switch_keeps_the_owner():
    a = Session()
    a.set_playlist(mp.OneshotPlaylist())
    a.set_playlist(mp.get_playlist('repeat', a.playlist))
    assert isinstance(a.playlist, mp.RepeatPlaylist)
    assert a.playlist.session is a
    assert mp.get_playlist('random', a.playlist).session is a


def test_validation_failure_goes_to_the_owning_session_not_var_bot():
    owner, other = Session(), Session()
    var.bot = other                     # 全局 bot 是另一个会话
    var.cache = FakeCache()
    queue = mp.OneshotPlaylist()
    owner.set_playlist(queue)
    queue.pending_items.append(BadWrapper())
    queue._validate_pending()
    assert owner.messages == ['nope'] and owner.dropped == ['bad']
    assert other.messages == [] and other.dropped == []
    assert var.cache.deleted == ['bad']


def test_all_playlists_lists_each_queue_once():
    a = Session()
    a.set_playlist(mp.OneshotPlaylist())   # 同时同步到 var.playlist
    var.bot = a
    assert var.all_playlists() == [a.playlist]
    var.playlist = mp.RepeatPlaylist()     # 测试里直接换了全局队列
    assert len(var.all_playlists()) == 2
