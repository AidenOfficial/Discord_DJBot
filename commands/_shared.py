# coding=utf-8
"""State and helpers shared by every command module."""
import logging

from constants import tr_cli as tr

try:
    import media.spotify
    _spotify_available = True
except ImportError:
    # Spotify is an optional fork feature (media/spotify.py + the spotdl CLI).
    # If the module is missing the rest of the bot must still start - only the
    # /spotify command becomes unavailable. (See cmd_play_spotify.)
    _spotify_available = False

log = logging.getLogger("bot")

ITEMS_PER_PAGE = 50

# Last search/browse results (/filematch, /ysearch, /search, /listfile,
# /findtagged ...) - read back by /pick and /delete. Kept per session (server):
# a search in one server must not change what /pick 2 means in another.

def shortlist(bot):
    return getattr(bot, 'song_shortlist', None) or []


def set_shortlist(bot, items):
    bot.song_shortlist = list(items)


def send_multi_lines(bot, lines, text, linebreak="<br />"):
    msg = ""
    br = ""
    for newline in lines:
        msg += br
        br = linebreak
        if bot.link.max_message_length \
                and (len(msg) + len(newline)) > (bot.link.max_message_length - 4):  # 4 == len("<br>")
            bot.send_msg(msg, text)
            msg = ""
        msg += newline

    bot.send_msg(msg, text)


def send_multi_lines_in_channel(bot, lines, linebreak="<br />"):
    msg = ""
    br = ""
    for newline in lines:
        msg += br
        br = linebreak
        if bot.link.max_message_length \
                and (len(msg) + len(newline)) > (bot.link.max_message_length - 4):  # 4 == len("<br>")
            bot.send_channel_msg(msg)
            msg = ""
        msg += newline

    bot.send_channel_msg(msg)


def send_item_added_message(bot, wrapper, index, text):
    if index == bot.playlist.current_index + 1:
        bot.send_msg(tr('file_added', item=wrapper.format_song_string()) +
                     tr('position_in_the_queue', position=tr('next_to_play')), text)
    elif index == len(bot.playlist) - 1:
        bot.send_msg(tr('file_added', item=wrapper.format_song_string()) +
                     tr('position_in_the_queue', position=tr('last_song_on_the_queue')), text)
    else:
        bot.send_msg(tr('file_added', item=wrapper.format_song_string()) +
                     tr('position_in_the_queue', position=f"{index + 1}/{len(bot.playlist)}."), text)


