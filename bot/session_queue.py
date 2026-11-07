# coding=utf-8
"""会话(服务器)自己的队列和数据。

以前所有代码直接用全局的 var.playlist;多服务器时每个会话一个队列。PlayerMixin 和 ChannelMixin
都继承这个基类,用 self.playlist 访问队列。

过渡期:没设置过(测试替身用 __new__ 构造)时回退到 var.playlist,set_playlist() 也同步一份到
var.playlist,单服务器的旧代码照常工作。

会话的设置(音量、播放模式、频道设置……)和封禁检查都按 guild_id 走 bot.store.GuildStore;
guild_id 连上 Discord 才知道(bind_guild),之前是 ''。store 没单独给就用全局的 var.store。
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

    # ---- 服务器数据 ----

    @property
    def guild_id(self):
        return self.__dict__.get('_guild_id') or ''

    @property
    def store(self):
        store = self.__dict__.get('_store')
        return store if store is not None else var.store

    def bind_guild(self, guild_id, store=None):
        self._guild_id = str(guild_id) if guild_id else ''
        if store is not None:
            self._store = store

    def setting(self, key, default=None):
        store = self.store
        return default if store is None else store.get(self.guild_id, key, default)

    def save_setting(self, key, value):
        store = self.store
        if store is not None:
            store.set(self.guild_id, key, value)

    def has_rule(self, kind, value):
        """全局或本服务器的封禁 / 白名单里有没有 value。"""
        store = self.store
        return store is not None and store.has_rule(kind, value, self.guild_id)
