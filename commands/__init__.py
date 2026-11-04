# coding=utf-8
"""Command layer: one module per domain; commands/slash.py lists every slash command."""
from ._shared import _spotify_available  # noqa: F401  (probed by scripts/smoke_test.py)
from . import slash


def register_all_commands(bot):
    import variables as var
    bot.register_slash_commands(slash.configured_specs(var.config))
