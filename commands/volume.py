# coding=utf-8
import logging

from constants import tr_cli as tr
import variables as var

log = logging.getLogger("bot")


def cmd_volume(bot, user, text, command, parameter):
    # The volume is a percentage
    max_vol = min(int(var.config.getfloat('bot', 'max_volume') * 100), 100.0)
    saved_max = bot.setting('max_volume')
    if saved_max is not None:
        max_vol = float(saved_max) * 100.0
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
    
    if parameter and parameter.isdigit() and 0 <= int(parameter) <= 100:
        max_vol = float(parameter) / 100.0
        bot.save_setting('max_volume', float(parameter) / 100.0)
        bot.send_msg(tr('change_max_volume', max=parameter, user=user), text)
        if int(bot.volume_helper.plain_volume_set) > max_vol:
            bot.volume_helper.set_volume(max_vol)
        log.info(f'cmd: max volume set to {max_vol}')
    else:
        max_vol = var.config.getfloat('bot', 'max_volume') * 100.0
        saved_max = bot.setting('max_volume')
        if saved_max is not None:
            max_vol = float(saved_max) * 100.0
        bot.send_msg(tr('current_max_volume', max=int(max_vol)), text)
