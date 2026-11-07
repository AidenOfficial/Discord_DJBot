# coding=utf-8
"""整个进程共用的下载登记。

缓存(var.cache)是所有会话共用的:两个服务器排了同一首时,队列里是两个 wrapper、同一个条目对象。
以前每个 bot 各记各的"正在下载",B 看不到 A 的下载,会再起一个;那次 prepare() 因为
item.downloading 立刻返回,几次补发后 B 把共用的条目标成 failed,A 正在下载的歌也跟着没了。

现在按条目 id 全局登记:谁 begin() 成功谁下载,其他会话看到 is_active() 就等它下完。"""

import threading

_lock = threading.Lock()
_active = set()


def begin(item_id):
    """登记开始下载。已经有人在下载这首时返回 False(调用方不要再下载)。"""
    with _lock:
        if item_id in _active:
            return False
        _active.add(item_id)
        return True


def end(item_id):
    """下载线程结束(成功或失败)时调用;没登记过也没关系。"""
    with _lock:
        _active.discard(item_id)


def is_active(item_id):
    with _lock:
        return item_id in _active


def active_count():
    """所有会话加起来正在下载的数量(预下载的并发上限按这个算)。"""
    with _lock:
        return len(_active)
