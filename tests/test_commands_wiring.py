# coding=utf-8
"""斜杠命令表:每条命令都接上了 commands 包里的 handler,名字 / 说明符合 Discord 的限制。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import configparser  # noqa: E402

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
    for lang in ('en_US', 'zh_CN', 'ja_JP'):
        lines = slash.help_lines(lang, include_admin=False, config=var.config)
        assert any('/play' in line for line in lines)
        assert not any('/kill' in line for line in lines)  # 管理员命令只给管理员看
        assert any('/kill' in line for line in slash.help_lines(lang, include_admin=True, config=var.config))


def test_mode_aliases_map_to_known_modes():
    from commands.playback import MODE_ALIASES
    assert set(MODE_ALIASES.values()) <= {"one-shot", "repeat", "single", "random", "autoplay"}
    assert MODE_ALIASES["single"] == "single"
