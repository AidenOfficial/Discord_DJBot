# coding=utf-8
import html

from constants import tr_cli as tr
import util
import variables as var
from media.cache import discard_everywhere
from media.item import item_id_generators



def cmd_joinme(bot, user, text, command, parameter):
    channel_id = getattr(text, 'voice_channel_id', None)
    if channel_id is None:
        bot.send_msg(tr('join_voice_first'), text)
        return
    if channel_id == bot.my_channel_id():
        bot.send_msg(tr('already_here'), text)
        return
    if bot.move_to_channel(channel_id, f'/join by {user}'):
        bot.send_msg(tr('joined_channel', channel=bot.channel_display_name(channel_id)), text)
    else:
        bot.send_msg(tr('cannot_join_voice'), text)


def _option_user_name(text, parameter):
    options = getattr(text, 'options', None) or {}
    return options.get('user_name') or parameter


# 封禁 / 白名单命令现在都写全局规则(scope '');检查时全局和本服务器的规则都算(见 GuildStore.has_rule)
GLOBAL = ''


def _actor(text):
    return str(getattr(text, 'actor', '') or '')


def cmd_user_ban(bot, user, text, command, parameter):
    # parameter 是 Discord user id(斜杠命令的 user 参数);值里记显示名,列表好认
    if parameter:
        name = _option_user_name(text, parameter)
        bot.store.add_rule(GLOBAL, 'user_ban', parameter, created_by=_actor(text), note=html.escape(name))
        bot.send_msg(tr("user_ban_success", user=html.escape(name)), text)
    else:
        ban_list = "<ul>"
        for rule in bot.store.list_rules('user_ban', GLOBAL):
            ban_list += "<li>" + (rule['note'] or '?') + f" ({rule['value']})</li>"
        ban_list += "</ul>"
        bot.send_msg(tr("user_ban_list", list=ban_list), text)


def cmd_user_unban(bot, user, text, command, parameter):
    name = html.escape(_option_user_name(text, parameter))
    if parameter and bot.store.remove_rule(GLOBAL, 'user_ban', parameter):
        bot.send_msg(tr("user_unban_success", user=name), text)
    else:
        bot.send_msg(tr("user_not_banned", user=name), text)


def cmd_url_ban(bot, user, text, command, parameter):
    url = util.get_url_from_input(parameter)
    if url:
        _id = item_id_generators['url'](url=url)
        bot.drop_from_queue(_id)
        discard_everywhere(_id, done=bot.playlist)
    else:
        if bot.playlist.current_item() and bot.playlist.current_item().type == 'url':
            item = bot.playlist.current_item().item()
            url = item.url
            bot.drop_from_queue(item.id)
            discard_everywhere(item.id, done=bot.playlist)
        else:
            bot.send_msg(tr('bad_parameter', command=command), text)
            return

    # Remove from the whitelist first
    if bot.store.remove_rule(GLOBAL, 'url_whitelist', url):
        bot.send_msg(tr("url_unwhitelist_success", url=url), text)

    bot.store.add_rule(GLOBAL, 'url_ban', url, created_by=_actor(text))
    bot.send_msg(tr("url_ban_success", url=url), text)


def cmd_url_ban_list(bot, user, text, command, parameter):
    ban_list = "<ul>"
    for rule in bot.store.list_rules('url_ban', GLOBAL):
        ban_list += "<li>" + rule['value'] + "</li>"
    ban_list += "</ul>"

    bot.send_msg(tr("url_ban_list", list=ban_list), text)


def cmd_url_unban(bot, user, text, command, parameter):
    url = util.get_url_from_input(parameter)
    if url:
        bot.store.remove_rule(GLOBAL, 'url_ban', url)
        bot.send_msg(tr("url_unban_success", url=url), text)
    else:
        bot.send_msg(tr('bad_parameter', command=command), text)


def cmd_url_whitelist(bot, user, text, command, parameter):
    url = util.get_url_from_input(parameter)
    if url:
        # Unban first
        if bot.store.remove_rule(GLOBAL, 'url_ban', url):
            bot.send_msg(tr("url_unban_success"), text)

        # Then add to whitelist
        bot.store.add_rule(GLOBAL, 'url_whitelist', url, created_by=_actor(text))
        bot.send_msg(tr("url_whitelist_success", url=url), text)
    else:
        bot.send_msg(tr('bad_parameter', command=command), text)


def cmd_url_whitelist_list(bot, user, text, command, parameter):
    ban_list = "<ul>"
    for rule in bot.store.list_rules('url_whitelist', GLOBAL):
        ban_list += "<li>" + rule['value'] + "</li>"
    ban_list += "</ul>"

    bot.send_msg(tr("url_whitelist_list", list=ban_list), text)


def cmd_url_unwhitelist(bot, user, text, command, parameter):
    url = util.get_url_from_input(parameter)
    if url:
        bot.store.remove_rule(GLOBAL, 'url_whitelist', url)
        bot.send_msg(tr("url_unwhitelist_success"), text)
    else:
        bot.send_msg(tr('bad_parameter', command=command), text)



def cmd_help(bot, user, text, command, parameter):
    from . import slash
    from ._shared import send_multi_lines
    lines = slash.help_lines(var.language, include_admin=bot.is_admin(text), config=var.config)
    send_multi_lines(bot, [tr('help_header')] + lines, text)



def cmd_kill(bot, user, text, command, parameter):
    bot.pause()
    if var.hub is not None:
        var.hub.stop()  # 整个进程退出:所有服务器的播放循环都停
    else:
        bot.exit = True


def cmd_update(bot, user, text, command, parameter):
    if bot.is_admin(text):
        bot.send_msg(tr('start_updating'), text)
        bot.send_msg(util.upgrade_extractors(), text)
    else:
        bot.send_msg(tr('not_admin'), text)



def cmd_version(bot, user, text, command, parameter):
    bot.send_msg(tr('report_version', version=bot.get_version()), text)

