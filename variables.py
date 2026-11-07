from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import bot.cleanup
    import bot.hub
    import bot.store
    import bot.core
    import media.playlist
    import media.cache
    import database
    import web_users

bot: 'bot.core.DJBot' = None  # 主服务器的会话(兼容单服务器时代的代码;多服务器用 hub)
hub: 'bot.hub.Hub' = None  # 进程的总管:Discord 连接 + 所有会话
playlist: 'media.playlist.BasePlaylist' = None
cache: 'media.cache.MusicCache' = None
cleaner: 'bot.cleanup.CacheCleaner' = None
play_history: 'database.PlayHistoryDatabase' = None
user_db: 'web_users.UserDatabase' = None
store: 'bot.store.GuildStore' = None  # 按服务器分开的设置 / 队列 / 封禁规则

user = ""
is_proxified = False

settings_db_path = None
music_db_path = None
db = None
music_db: 'database.MusicDatabase' = None
config: 'database.SettingsDatabase' = None

bot_logger = None

music_folder = ""
tmp_folder = ""

language = ""


def all_playlists():
    """所有会话的队列(清理缓存时要保护所有队列里的文件)。有 Hub 时是它的每个会话;
    另外带上 var.bot / var.playlist(没有 Hub 的测试、还没登记进 Hub 的会话)。"""
    queues = []
    candidates = []
    if hub is not None:
        candidates.extend(getattr(s, 'playlist', None) for s in hub.sessions())
    candidates.append(getattr(bot, 'playlist', None) if bot is not None else None)
    candidates.append(playlist)
    for queue in candidates:
        if queue is not None and all(queue is not q for q in queues):
            queues.append(queue)
    return queues
