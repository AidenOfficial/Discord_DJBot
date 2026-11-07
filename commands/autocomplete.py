# coding=utf-8
"""斜杠命令参数的自动补全。DiscordLink 在线程池里调用,要在 2.5 秒内返回。

suggest() 返回 [(显示文字, 值)],最多 25 条;值是真正填进参数的内容。
"""
import logging

import variables as var
from database import Condition

log = logging.getLogger("bot")

LIMIT = 25


def _matches(current, *texts):
    current = (current or '').strip().lower()
    if not current:
        return True
    return any(current in (t or '').lower() for t in texts)


def _queue(bot, ctx, current):
    out = []
    playlist = bot.playlist
    if playlist is None:
        return out
    current_index = playlist.current_index
    for i, wrapper in enumerate(list(playlist)):
        try:
            title = wrapper.format_title()
        except Exception:
            continue
        if not _matches(current, title, str(i + 1)):
            continue
        marker = '▶ ' if i == current_index else ''
        out.append((f"{i + 1}. {marker}{title}", i + 1))
        if len(out) >= LIMIT:
            break
    return out


def _playlist(bot, ctx, current):
    from .personal import _identity
    identity = _identity(bot, ctx)
    if identity is None:
        return []
    out = []
    for pl in var.user_db.list_playlists(identity):
        if _matches(current, pl['name']):
            out.append((f"{pl['name']} ({pl['count']})", pl['name']))
    return out[:LIMIT]


def _file(bot, ctx, current):
    condition = Condition().and_equal('type', 'file')
    if current:
        condition = condition.and_like('path', f'%{current}%', case_sensitive=False)
    condition = condition.order_by('path').limit(LIMIT)
    return [(row['path'], row['path']) for row in var.music_db.query_music(condition)]


def _radio(bot, ctx, current):
    out = []
    for name, value in var.config.items('radio'):
        comment = value.split(maxsplit=1)[1].strip('"') if len(value.split(maxsplit=1)) == 2 else ''
        if _matches(current, name, comment):
            out.append((f"{name} — {comment}" if comment else name, name))
    return out[:LIMIT]


def _tag(bot, ctx, current):
    # 多个标签用逗号分隔:只补全最后一个
    head, _, last = (current or '').rpartition(',')
    prefix = f"{head}," if head else ''
    out = []
    for tag in sorted(var.music_db.query_all_tags()):
        if _matches(last, tag):
            value = f"{prefix}{tag}"
            out.append((value, value))
        if len(out) >= LIMIT:
            break
    return out


_KINDS = {'queue': _queue, 'playlist': _playlist, 'file': _file, 'radio': _radio, 'tag': _tag}


def suggest(bot, kind, ctx, current):
    fn = _KINDS.get(kind)
    if fn is None:
        return []
    try:
        return fn(bot, ctx, current)[:LIMIT]
    except Exception:
        log.debug("autocomplete: %s failed", kind, exc_info=True)
        return []
