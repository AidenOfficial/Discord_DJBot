# coding=utf-8
"""斜杠命令表:每条命令都接上了 commands 包里的 handler,名字 / 说明符合 Discord 的限制。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import configparser  # noqa: E402
from unittest import mock  # noqa: E402

import constants  # noqa: E402
import commands  # noqa: E402
from commands import slash  # noqa: E402
import variables as var  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def setup_module(module):
    module._saved_config = var.config
    config = configparser.ConfigParser(interpolation=None, allow_no_value=True)
    config.read(os.path.join(ROOT, "configuration.default.ini"), encoding="utf-8")
    var.config = config


def teardown_module(module):
    var.config = module._saved_config


class FakeBot:
    def __init__(self):
        self.registered = {}

    def register_slash_commands(self, named_specs):
        for name, spec in named_specs:
            self.registered[name] = spec


def test_register_all_commands_wires_everything():
    constants.load_lang("en_US")
    bot = FakeBot()
    commands.register_all_commands(bot)
    for expected in ("play", "file", "spotify", "bili", "live", "volume", "queue", "skip", "tag",
                     "search", "kill", "update", "web", "mode", "pick", "leave", "join", "bind"):
        assert expected in bot.registered, f"no slash command '{expected}'"
    for name, spec in bot.registered.items():
        assert callable(spec.handler), name
        assert spec.handler.__module__.startswith("commands."), f"{name} -> {spec.handler.__module__}"
    # Discord:每个服务器最多 100 条斜杠命令
    assert len(bot.registered) <= 100


def test_default_ini_matches_slash_table():
    keys = {spec.key for spec in slash.specs()}
    assert keys == set(var.config.options('commands'))


def test_names_and_descriptions_fit_discord_limits():
    for name, spec in slash.configured_specs(var.config):
        assert slash.NAME_RE.match(name), name
        assert set(spec.desc) == {'en', 'zh-CN', 'ja'}, name
        assert all(0 < len(v) <= 100 for v in spec.desc.values()), name
        seen_optional = False
        for opt in spec.options:
            assert slash.NAME_RE.match(opt.name), (name, opt.name)
            assert set(opt.desc) == {'en', 'zh-CN', 'ja'}, (name, opt.name)
            assert all(0 < len(v) <= 100 for v in opt.desc.values()), (name, opt.name)
            seen_optional = seen_optional or not opt.required
        assert len(spec.options) <= 25, name


def test_renaming_via_commands_section():
    config = configparser.ConfigParser(interpolation=None)
    config.read_dict({'commands': {'play': 'p, play', 'skip': 'next'}})
    names = dict((spec.key, name) for name, spec in slash.configured_specs(config))
    assert names['play'] == 'p' and names['skip'] == 'next'
    bad = configparser.ConfigParser(interpolation=None)
    bad.read_dict({'commands': {'skip': 'Not Valid'}})
    try:
        slash.configured_specs(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid slash command name accepted")


def test_help_lists_commands_in_every_language():
    def has(lines, name):
        return any(f'<code>/{name}</code>' in line for line in lines)

    for lang in ('en_US', 'zh_CN', 'ja_JP'):
        lines = slash.help_lines(lang, include_admin=False, config=var.config)
        assert has(lines, 'play')
        assert not has(lines, 'userban') and not has(lines, 'kill')  # 管理员命令只给管理员看
        admin = slash.help_lines(lang, include_admin=True, config=var.config)
        assert has(admin, 'userban') and has(admin, 'maxvolume')
        assert not has(admin, 'kill') and not has(admin, 'globalban')  # 服务器管理员看不到 bot 主人的命令
        owner = slash.help_lines(lang, include_admin=True, include_owner=True, config=var.config)
        assert has(owner, 'kill') and has(owner, 'globalban') and has(owner, 'userban')


def test_permission_levels():
    by_key = {spec.key: spec for spec in slash.specs()}
    owner = {'drop_database', 'rescan', 'update', 'kill', 'add_webinterface_user', 'remove_webinterface_user',
             'list_webinterface_user', 'global_ban', 'global_unban', 'global_ban_list', 'url_whitelist',
             'url_unwhitelist', 'delete_from_library'}
    server_admin = {'max_volume', 'user_ban', 'user_unban', 'url_ban', 'url_unban', 'ban_list'}
    assert {k for k, s in by_key.items() if s.owner_only} == owner
    assert {k for k, s in by_key.items() if s.admin} == server_admin
    assert not any(s.owner_only and s.admin for s in by_key.values())


def test_help_hides_owner_commands_from_guild_admins():
    from commands import admin
    from bot.discord_link import CommandContext
    constants.load_lang("en_US")
    saved_admin = var.config.get('bot', 'admin')
    var.config.set('bot', 'admin', '111')

    class Bot:
        def __init__(self):
            self.sent = []

        def is_admin(self, ctx):
            return ctx.is_admin

        def is_owner(self, ctx):
            return str(ctx.actor) == '111'

        def send_msg(self, msg, ctx):
            self.sent.append(msg)

        max_message_length = 100000

    def help_for(actor, is_admin):
        bot = Bot()
        ctx = CommandContext(actor=actor, name='x', username='x', command='help', argument='', is_admin=is_admin)
        with mock.patch('commands._shared.send_multi_lines', lambda b, lines, t: b.sent.extend(lines)):
            admin.cmd_help(bot, 'x', ctx, 'help', '')
        return '\n'.join(bot.sent)

    try:
        guild_admin = help_for(5, True)
        assert '/userban' in guild_admin and '/kill' not in guild_admin and '/globalban' not in guild_admin
        owner = help_for(111, True)
        assert '/kill' in owner and '/globalban' in owner
    finally:
        var.config.set('bot', 'admin', saved_admin)


def test_limits_default_to_config():
    from bot.limits import guild_max_volume, limits_for
    limits = limits_for('123')
    assert limits.max_queue == 0                                   # 默认不限
    assert limits.max_track_seconds == var.config.getint('bot', 'max_track_duration') * 60
    assert limits.max_playlist_tracks == var.config.getint('bot', 'max_track_playlist')
    assert limits.max_volume == 1.0
    assert limits_for('456') == limits                             # 现在每个服务器一样
    saved = var.store
    var.store = None
    try:
        assert guild_max_volume('123') == var.config.getfloat('bot', 'max_volume')
    finally:
        var.store = saved


def test_mode_aliases_map_to_known_modes():
    from commands.playback import MODE_ALIASES
    assert set(MODE_ALIASES.values()) <= {"one-shot", "repeat", "single", "random", "autoplay"}
    assert MODE_ALIASES["single"] == "single"
