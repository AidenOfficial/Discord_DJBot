"""Web 请求操作的是哪个会话(服务器)。

Web 代码不直接用 var.bot / var.playlist,统一从这里取。现在只有一个会话,就是 var.bot;
多服务器后按请求里选的服务器返回对应的会话,调用方不用改。
"""

import variables as var


def session():
    """这个请求要操作的会话(DJBot)。"""
    return var.bot


def playlist():
    """这个会话的队列。测试替身没有 playlist 属性时退回 var.playlist。"""
    bot = session()
    queue = getattr(bot, 'playlist', None) if bot is not None else None
    return queue if queue is not None else var.playlist


def set_playlist(new):
    """换队列对象(切换播放模式)。"""
    bot = session()
    if bot is not None and hasattr(bot, 'set_playlist'):
        bot.set_playlist(new)
    else:
        var.playlist = new
