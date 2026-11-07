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


# 封禁分两级(见 GuildStore):
#   服务器管理员的 /userban /userunban /urlban /urlunban /banlist 只管本服务器(scope = 服务器 ID);
#   bot 主人的 /globalban /globalunban /globalbanlist /urlwhitelist /urlunwhitelist 管全局(scope '')。
# 全局封禁对服务器管理员也有效,只有 bot 主人自己不受影响(见 DJBot.banned)。
GLOBAL = ''


def _option_user_name(text, parameter):
    options = getattr(text, 'options', None) or {}
    return options.get('user_name') or parameter


def _actor(text):
    return str(getattr(text, 'actor', '') or '')


def _guild_scope(bot, text, command):
    """本服务器的规则写到哪个 scope。没绑定服务器(不该发生)就拒绝,免得写成全局规则。"""
    gid = bot.guild_id
    if not gid:
        bot.send_msg(tr('bad_parameter', command=command), text)
    return gid


def _resolve_url(bot, raw):
    """(url, item_id):raw 给了就只认 raw;没给用当前这首(只有链接类的才行)。都没有是 (None, None)。"""
    if raw:
        url = util.get_url_from_input(raw)
        return (url, item_id_generators['url'](url=url)) if url else (None, None)
    current = bot.playlist.current_item()
    if current and current.type == 'url':
        return current.item().url, current.id
    return None, None


def _user_rules(rules):
    if not rules:
        return tr('ban_list_empty')
    return "<ul>" + "".join(f"<li>{rule['note'] or '?'} ({rule['value']})</li>" for rule in rules) + "</ul>"


def _url_rules(rules):
    if not rules:
        return tr('ban_list_empty')
    return "<ul>" + "".join(f"<li>{rule['value']}</li>" for rule in rules) + "</ul>"


# ---- 服务器管理员:本服务器 ----

def cmd_user_ban(bot, user, text, command, parameter):
    # parameter 是 Discord user id(斜杠命令的 user 参数);值里记显示名,列表好认
    gid = _guild_scope(bot, text, command)
    if not gid:
        return
    if not parameter:
        bot.send_msg(tr('bad_parameter', command=command), text)
        return
    name = _option_user_name(text, parameter)
    bot.store.add_rule(gid, 'user_ban', parameter, created_by=_actor(text), note=html.escape(name))
    bot.send_msg(tr("user_ban_success", user=html.escape(name)), text)


def cmd_user_unban(bot, user, text, command, parameter):
    gid = _guild_scope(bot, text, command)
    if not gid:
        return
    name = html.escape(_option_user_name(text, parameter))
    if parameter and bot.store.remove_rule(gid, 'user_ban', parameter):
        bot.send_msg(tr("user_unban_success", user=name), text)
    else:
        bot.send_msg(tr("user_not_banned", user=name), text)
    if parameter and bot.store.has_rule('user_ban', parameter):
        bot.send_msg(tr('still_banned_globally', target=name), text)


def cmd_url_ban(bot, user, text, command, parameter):
    gid = _guild_scope(bot, text, command)
    if not gid:
        return
    url, item_id = _resolve_url(bot, parameter)
    if not url:
        bot.send_msg(tr('bad_parameter', command=command), text)
        return
    # 只从本服务器的队列里拿掉;曲库和缓存是大家共用的,不删
    bot.drop_from_queue(item_id)
    bot.store.add_rule(gid, 'url_ban', url, created_by=_actor(text))
    bot.send_msg(tr("url_ban_success", url=url), text)


def cmd_url_unban(bot, user, text, command, parameter):
    gid = _guild_scope(bot, text, command)
    if not gid:
        return
    url = util.get_url_from_input(parameter)
    if not url:
        bot.send_msg(tr('bad_parameter', command=command), text)
        return
    bot.store.remove_rule(gid, 'url_ban', url)
    bot.send_msg(tr("url_unban_success", url=url), text)
    if bot.store.has_rule('url_ban', url):
        bot.send_msg(tr('still_banned_globally', target=url), text)


def cmd_ban_list(bot, user, text, command, parameter):
    gid = _guild_scope(bot, text, command)
    if not gid:
        return
    bot.send_msg(tr('ban_list', users=_user_rules(bot.store.list_rules('user_ban', gid)),
                    urls=_url_rules(bot.store.list_rules('url_ban', gid))), text)


# ---- bot 主人:全局 ----

def _ban_options(text):
    options = getattr(text, 'options', None) or {}
    return options.get('user'), options.get('user_name'), options.get('url')


def cmd_global_ban(bot, user, text, command, parameter):
    """/globalban [user] [url]:两个都不填 = 封禁当前这首的链接。"""
    target, target_name, raw_url = _ban_options(text)
    if target:
        name = html.escape(target_name or target)
        bot.store.add_rule(GLOBAL, 'user_ban', target, created_by=_actor(text), note=name)
        bot.send_msg(tr("user_ban_success", user=name), text)
    if raw_url or not target:
        url, item_id = _resolve_url(bot, raw_url)
        if not url:
            bot.send_msg(tr('bad_parameter', command=command), text)
            return
        # 全局封禁:所有服务器的队列都拿掉,文件和曲库记录也删
        bot.drop_from_queue(item_id)
        discard_everywhere(item_id, done=bot.playlist)
        if bot.store.remove_rule(GLOBAL, 'url_whitelist', url):
            bot.send_msg(tr("url_unwhitelist_success", url=url), text)
        bot.store.add_rule(GLOBAL, 'url_ban', url, created_by=_actor(text))
        bot.send_msg(tr("url_ban_success", url=url), text)


def cmd_global_unban(bot, user, text, command, parameter):
    target, target_name, raw_url = _ban_options(text)
    if not target and not raw_url:
        bot.send_msg(tr('bad_parameter', command=command), text)
        return
    if target:
        name = html.escape(target_name or target)
        if bot.store.remove_rule(GLOBAL, 'user_ban', target):
            bot.send_msg(tr("user_unban_success", user=name), text)
        else:
            bot.send_msg(tr("user_not_banned", user=name), text)
    if raw_url:
        url = util.get_url_from_input(raw_url)
        if not url:
            bot.send_msg(tr('bad_parameter', command=command), text)
            return
        bot.store.remove_rule(GLOBAL, 'url_ban', url)
        bot.send_msg(tr("url_unban_success", url=url), text)


def cmd_global_ban_list(bot, user, text, command, parameter):
    bot.send_msg(tr('global_ban_list', users=_user_rules(bot.store.list_rules('user_ban', GLOBAL)),
                    urls=_url_rules(bot.store.list_rules('url_ban', GLOBAL)),
                    whitelist=_url_rules(bot.store.list_rules('url_whitelist', GLOBAL))), text)


def cmd_url_whitelist(bot, user, text, command, parameter):
    url = util.get_url_from_input(parameter)
    if url:
        # Unban first
        if bot.store.remove_rule(GLOBAL, 'url_ban', url):
            bot.send_msg(tr("url_unban_success", url=url), text)

        # Then add to whitelist
        bot.store.add_rule(GLOBAL, 'url_whitelist', url, created_by=_actor(text))
        bot.send_msg(tr("url_whitelist_success", url=url), text)
    else:
        bot.send_msg(tr('bad_parameter', command=command), text)


def cmd_url_unwhitelist(bot, user, text, command, parameter):
    url = util.get_url_from_input(parameter)
    if url:
        bot.store.remove_rule(GLOBAL, 'url_whitelist', url)
        bot.send_msg(tr("url_unwhitelist_success", url=url), text)
    else:
        bot.send_msg(tr('bad_parameter', command=command), text)



def cmd_help(bot, user, text, command, parameter):
    from . import slash
    from ._shared import send_multi_lines
    owner = bot.is_owner(text)
    lines = slash.help_lines(var.language, include_admin=owner or bot.is_admin(text), include_owner=owner,
                             config=var.config)
    send_multi_lines(bot, [tr('help_header')] + lines, text)



def cmd_kill(bot, user, text, command, parameter):
    bot.pause()
    if var.hub is not None:
        var.hub.stop()  # 整个进程退出:所有服务器的播放循环都停
    else:
        bot.exit = True


def cmd_update(bot, user, text, command, parameter):
    if bot.is_owner(text):
        bot.send_msg(tr('start_updating'), text)
        bot.send_msg(util.upgrade_extractors(), text)
    else:
        bot.send_msg(tr('not_owner'), text)



def cmd_version(bot, user, text, command, parameter):
    bot.send_msg(tr('report_version', version=bot.get_version()), text)
