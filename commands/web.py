# coding=utf-8
import secrets
import datetime
import json

from constants import tr_cli as tr
import interface
import util
import variables as var
from web_context import TOKEN_GUILD_SECTION



def _web_user(text, user):
    """Web 登录(token / 密码)用的账号名:Discord 的唯一用户名,不是可以随便改的服务器昵称
    (否则改个昵称就能冒充别人的 Web 账号)。"""
    return getattr(text, 'username', None) or user


def cmd_web_access(bot, user, text, command, parameter):
    auth_method = var.config.get("webinterface", "auth_method")
    user = _web_user(text, user)

    if auth_method == 'token':
        interface.banned_ip = []
        interface.bad_access_count = {}

        user_info = var.db.get("user", user, fallback='{}')
        user_dict = json.loads(user_info)
        if 'token' in user_dict:
            var.db.remove_option("web_token", user_dict['token'])
            var.db.remove_option(TOKEN_GUILD_SECTION, user_dict['token'])

        token = secrets.token_urlsafe(5)
        user_dict['token'] = token
        user_dict['token_created'] = str(datetime.datetime.now())
        user_dict['last_ip'] = ''
        var.db.set("web_token", token, user)
        # 令牌只能操作发命令的这个服务器(多服务器时,见 web_context.token_guild_id)
        guild_id = getattr(text, 'guild_id', None) or getattr(bot, 'guild_id', None)
        if guild_id:
            var.db.set(TOKEN_GUILD_SECTION, token, str(guild_id))
        var.db.set("user", user, json.dumps(user_dict))

        access_address = var.config.get("webinterface", "access_address") + "/?token=" + token
    else:
        access_address = var.config.get("webinterface", "access_address")

    bot.send_msg(tr('webpage_address', address=access_address), text)


def cmd_user_password(bot, user, text, command, parameter):
    if not parameter:
        bot.send_msg(tr('bad_parameter', command=command), text)
        return

    user = _web_user(text, user)
    user_info = var.db.get("user", user, fallback='{}')
    user_dict = json.loads(user_info)
    user_dict['password'], user_dict['salt'] = util.get_salted_password_hash(parameter)

    var.db.set("user", user, json.dumps(user_dict))

    bot.send_msg(tr('user_password_set'), text)


def cmd_web_user_add(bot, user, text, command, parameter):
    if not parameter:
        bot.send_msg(tr('bad_parameter', command=command), text)
        return

    auth_method = var.config.get("webinterface", "auth_method")

    if auth_method == 'password':
        web_users = json.loads(var.db.get("privilege", "web_access", fallback='[]'))
        if parameter not in web_users:
            web_users.append(parameter)
        var.db.set("privilege", "web_access", json.dumps(web_users))
        bot.send_msg(tr('web_user_list', users=", ".join(web_users)), text)
    else:
        bot.send_msg(tr('command_disabled', command=command), text)


def cmd_web_user_remove(bot, user, text, command, parameter):
    if not parameter:
        bot.send_msg(tr('bad_parameter', command=command), text)
        return

    auth_method = var.config.get("webinterface", "auth_method")

    if auth_method == 'password':
        web_users = json.loads(var.db.get("privilege", "web_access", fallback='[]'))
        if parameter in web_users:
            web_users.remove(parameter)
        var.db.set("privilege", "web_access", json.dumps(web_users))
        bot.send_msg(tr('web_user_list', users=", ".join(web_users)), text)
    else:
        bot.send_msg(tr('command_disabled', command=command), text)


def cmd_web_user_list(bot, user, text, command, parameter):
    auth_method = var.config.get("webinterface", "auth_method")

    if auth_method == 'password':
        web_users = json.loads(var.db.get("privilege", "web_access", fallback='[]'))
        bot.send_msg(tr('web_user_list', users=", ".join(web_users)), text)
    else:
        bot.send_msg(tr('command_disabled', command=command), text)


