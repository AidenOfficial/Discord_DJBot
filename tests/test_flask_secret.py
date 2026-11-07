# coding=utf-8
"""util.resolve_flask_secret:不能用公开的默认值签名会话 Cookie;没配置时生成一次存进 settings 库。"""
import configparser
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import util  # noqa: E402
import variables as var  # noqa: E402
from database import SettingsDatabase  # noqa: E402


@pytest.fixture
def config(monkeypatch):
    cfg = configparser.ConfigParser(interpolation=None, allow_no_value=True)
    cfg.read(util.solve_filepath('configuration.default.ini'), encoding='utf-8')
    monkeypatch.setattr(var, 'config', cfg)
    monkeypatch.setattr(var, 'db', None)
    return cfg


@pytest.fixture
def settings_db(tmp_path, monkeypatch):
    import sqlite3

    path = str(tmp_path / 'settings.db')
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE botamusique (section TEXT, option TEXT, value TEXT, UNIQUE(section, option))")
    conn.commit()
    conn.close()
    db = SettingsDatabase(path)
    monkeypatch.setattr(var, 'db', db)
    return db


def test_default_secret_without_db_is_random(config):
    assert config.get('webinterface', 'flask_secret') == util.DEFAULT_FLASK_SECRET
    first = util.resolve_flask_secret()
    assert first != util.DEFAULT_FLASK_SECRET
    assert len(first) >= 32
    # 没有数据库时每次都随机，不能退化成另一个固定值
    assert util.resolve_flask_secret() != first


def test_default_secret_is_generated_once_and_persisted(config, settings_db):
    first = util.resolve_flask_secret()
    assert first != util.DEFAULT_FLASK_SECRET
    assert len(first) >= 32
    assert settings_db.get('webinterface', 'flask_secret') == first
    # "重启":同一个库再取一次还是它
    var.db = SettingsDatabase(settings_db.db_path)
    assert util.resolve_flask_secret() == first


def test_broken_db_falls_back_to_random(config, monkeypatch):
    class Broken:
        def get(self, *a, **k):
            raise RuntimeError('db locked')

    monkeypatch.setattr(var, 'db', Broken())
    assert len(util.resolve_flask_secret()) >= 32


@pytest.mark.parametrize('value', ['', '   '])
def test_empty_secret_is_replaced(config, value):
    config.set('webinterface', 'flask_secret', value)
    assert util.resolve_flask_secret().strip()


def test_configured_secret_is_kept(config, settings_db):
    config.set('webinterface', 'flask_secret', ' my-long-random-secret ')
    assert util.resolve_flask_secret() == 'my-long-random-secret'
    # 配置了就不往库里写
    assert settings_db.get('webinterface', 'flask_secret', fallback=None) is None
