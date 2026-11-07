from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import bot.cleanup
    import bot.core
    import media.playlist
    import media.cache
    import database
    import web_users

bot: 'bot.core.DJBot' = None
playlist: 'media.playlist.BasePlaylist' = None
cache: 'media.cache.MusicCache' = None
cleaner: 'bot.cleanup.CacheCleaner' = None
play_history: 'database.PlayHistoryDatabase' = None
user_db: 'web_users.UserDatabase' = None

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
    """所有会话的队列(清理缓存时要保护所有队列里的文件)。现在只有一个会话;多服务器后由 Hub 提供全部。"""
    queues = []
    for queue in (getattr(bot, 'playlist', None) if bot is not None else None, playlist):
        if queue is not None and all(queue is not q for q in queues):
            queues.append(queue)
    return queues
