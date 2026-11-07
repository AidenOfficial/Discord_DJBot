# coding=utf-8
import logging

from bot.limits import guild_max_volume, limits_for
from constants import tr_cli as tr

log = logging.getLogger("bot")


def _max_percent(bot):
    """这个服务器的最大音量(百分比,整数)。"""
    return int(round(guild_max_volume(bot.guild_id, bot.store) * 100))


def cmd_volume(bot, user, text, command, parameter):
    # The volume is a percentage
    max_vol = _max_percent(bot)
    if parameter and parameter.isdigit() and 0 <= int(parameter) <= 100:
        if int(parameter) <= max_vol:
            vol = int(parameter)
            bot.send_msg(tr('change_volume', volume=int(parameter), user=user), text)
        else:
            vol = max_vol
            bot.send_msg(tr('max_volume', max=int(vol)), text)
        bot.volume_helper.set_volume(float(vol) / 100.0)
        bot.save_setting('volume', str(float(vol) / 100.0))
        log.info(f'cmd: volume set to {float(vol) / 100.0}')
    else:
        bot.send_msg(tr('current_volume', volume=int(bot.volume_helper.plain_volume_set * 100)), text)


def cmd_max_volume(bot, user, text, command, parameter):
    """服务器管理员:这个服务器的最大音量(存在 guild_settings 的 max_volume),不超过限额的硬上限。"""
    if parameter and parameter.isdigit() and 0 <= int(parameter) <= 100:
        ceiling = int(round(limits_for(bot.guild_id).max_volume * 100))
        percent = min(int(parameter), ceiling)
        max_vol = percent / 100.0
        bot.save_setting('max_volume', max_vol)
        bot.send_msg(tr('change_max_volume', max=percent, user=user), text)
        if bot.volume_helper.plain_volume_set > max_vol:
            bot.volume_helper.set_volume(max_vol)
            bot.save_setting('volume', str(max_vol))
        log.info(f'cmd: max volume of {bot.guild_id or "-"} set to {max_vol}')
    else:
        bot.send_msg(tr('current_max_volume', max=_max_percent(bot)), text)
