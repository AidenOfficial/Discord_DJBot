# coding=utf-8
"""会话(服务器)自己的队列。

以前所有代码直接用全局的 var.playlist;多服务器时每个会话一个队列。PlayerMixin 和 ChannelMixin
都继承这个基类,用 self.playlist 访问队列。

过渡期:没设置过(测试替身用 __new__ 构造)时回退到 var.playlist,set_playlist() 也同步一份到
var.playlist,单服务器的旧代码照常工作。
"""

import variables as var


class SessionQueue:
    @property
    def playlist(self):
        playlist = self.__dict__.get('_playlist')
        return playlist if playlist is not None else var.playlist

    def set_playlist(self, playlist):
        """换队列对象(启动、切换播放模式)。队列记住自己属于哪个会话。"""
        self._playlist = playlist
        if playlist is not None:
            playlist.session = self
        var.playlist = playlist
