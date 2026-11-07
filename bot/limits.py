# coding=utf-8
"""每个服务器能用多少:队列长度、单曲时长、歌单条数、音量上限。

现在每个服务器都一样,取 configuration.ini 的值;以后按服务器分档(付费档位)只需要改 limits_for()。
检查点:队列加歌(media.playlist.BasePlaylist)、链接校验的时长(media.url)、歌单展开(media.url_from_playlist)、
音量(/volume、/maxvolume、Web 音量、启动时读存的音量)。0 表示不限。
"""

from dataclasses import dataclass

import variables as var


@dataclass(frozen=True)
class Limits:
    max_queue: int = 0             # 队列最多几首(0 = 不限)
    max_track_seconds: int = 0     # 链接单曲最长几秒(0 = 不限;白名单链接例外)
    max_playlist_tracks: int = 20  # 一次展开歌单最多几首
    max_volume: float = 1.0        # 音量硬上限(0–1):服务器管理员的 /maxvolume 也不能超过它


def _get(kind, section, option, fallback):
    config = var.config
    if config is None:
        return fallback
    try:
        return type(fallback)(getattr(config, kind)(section, option, fallback=fallback))
    except (AttributeError, TypeError, ValueError):
        return fallback


def limits_for(guild_id) -> Limits:
    """guild_id 这个服务器的限额。现在所有服务器相同(配置文件的值)。"""
    return Limits(
        max_queue=max(0, _get('getint', 'bot', 'max_queue_length', 0)),
        max_track_seconds=max(0, _get('getint', 'bot', 'max_track_duration', 0)) * 60,
        max_playlist_tracks=max(1, _get('getint', 'bot', 'max_track_playlist', 20)),
        max_volume=1.0,
    )


def guild_max_volume(guild_id, store=None):
    """这个服务器现在的最大音量(0–1):服务器管理员 /maxvolume 设的值,没设过用配置的 [bot] max_volume;
    都不超过限额的硬上限。"""
    ceiling = limits_for(guild_id).max_volume
    value = _get('getfloat', 'bot', 'max_volume', 1.0)
    store = store if store is not None else var.store
    if store is not None:
        saved = store.get(str(guild_id or ''), 'max_volume')
        if saved is not None:
            try:
                value = float(saved)
            except ValueError:
                pass
    return max(0.0, min(value, ceiling))
