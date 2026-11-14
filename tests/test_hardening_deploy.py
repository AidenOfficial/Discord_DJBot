"""部署相关的默认配置、compose 和文档要和代码的行为对得上。"""
import configparser
import ipaddress
import os
import re

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding='utf-8') as f:
        return f.read()


@pytest.fixture(scope='module')
def defaults():
    config = configparser.ConfigParser(interpolation=None, allow_no_value=True)
    config.read(os.path.join(ROOT, 'configuration.default.ini'), encoding='utf-8')
    return config


# ---- configuration.default.ini ---------------------------------------------------

def test_trusted_proxies_default_is_loopback_and_private(defaults):
    raw = defaults.get('webinterface', 'trusted_proxies')
    nets = [ipaddress.ip_network(v.strip()) for v in raw.split(',') if v.strip()]
    assert [str(n) for n in nets] == ['127.0.0.0/8', '::1/128', '10.0.0.0/8',
                                      '172.16.0.0/12', '192.168.0.0/16', 'fc00::/7']
    # cloudflared 在 compose 默认网桥(172.x)里,必须被默认值覆盖
    assert any(ipaddress.ip_address('172.18.0.5') in n for n in nets)
    assert not any(ipaddress.ip_address('203.0.113.7') in n for n in nets)


def test_new_webinterface_and_bot_defaults(defaults):
    assert defaults.getboolean('webinterface', 'honor_script_name') is False
    assert defaults.get('webinterface', 'uploaders') == ''
    assert defaults.getint('bot', 'max_download_mb') == 300
    for key in ('trusted_proxies', 'honor_script_name', 'uploaders'):
        assert not defaults.has_option('bot', key)
    assert not defaults.has_option('webinterface', 'max_download_mb')


# ---- configuration.example.ini -----------------------------------------------------

def _commented_keys_by_section(text):
    section, found = None, {}
    for line in text.splitlines():
        m = re.match(r'^\[(\w+)\]', line)
        if m:
            section = m.group(1)
            continue
        m = re.match(r'^#(\w+)\s*=', line)
        if m and section:
            found.setdefault(section, set()).add(m.group(1))
    return found


def test_example_documents_new_keys_in_the_right_section():
    keys = _commented_keys_by_section(_read('configuration.example.ini'))
    assert {'trusted_proxies', 'honor_script_name', 'uploaders'} <= keys['webinterface']
    assert 'max_download_mb' in keys['bot']


def test_example_values_match_defaults(defaults):
    text = _read('configuration.example.ini')
    for section, key in (('webinterface', 'trusted_proxies'), ('webinterface', 'honor_script_name'),
                         ('bot', 'max_download_mb')):
        m = re.search(rf'^#{key}\s*=\s*(.*)$', text, re.M)
        assert m and m.group(1).strip() == defaults.get(section, key)


# ---- docker-compose.yml ------------------------------------------------------------

def _services(text):
    """按两格缩进的服务名把 services 切成块(不依赖 PyYAML)。"""
    body = text.split('\nservices:\n', 1)[1]
    blocks, name = {}, None
    for line in body.splitlines():
        m = re.match(r'^  ([\w-]+):\s*$', line)
        if m:
            name = m.group(1)
            blocks[name] = []
        elif name:
            blocks[name].append(line)
    return {k: '\n'.join(v) for k, v in blocks.items()}


@pytest.fixture(scope='module')
def services():
    return _services(_read('docker-compose.yml'))


def _active(block):
    return '\n'.join(line for line in block.splitlines() if not line.lstrip().startswith('#'))


def test_cloudflared_is_pinned(services):
    cf = _active(services['cloudflared'])
    assert re.search(r'^    image: cloudflare/cloudflared:2026\.10\.0$', cf, re.M)
    assert ':latest' not in cf


def test_services_drop_new_privileges_and_have_limits(services):
    bot, cf = _active(services['botamusique']), _active(services['cloudflared'])
    for block in (bot, cf):
        assert re.search(r'^    security_opt:\n      - no-new-privileges:true$', block, re.M)
    assert re.search(r'^    mem_limit: 1536m$', bot, re.M)
    assert re.search(r'^    pids_limit: 512$', bot, re.M)
    assert re.search(r'^    mem_limit: 256m$', cf, re.M)
    # entrypoint 要用默认能力装 iptables 规则
    assert 'cap_drop' not in bot


def test_web_port_is_not_published(services):
    bot = services['botamusique']
    assert 'ports' not in _active(bot)
    assert '# ports: ["8181:8181"]' in bot
    assert '绝对不要' in bot


# ---- 文档 ---------------------------------------------------------------------------

def test_webui_doc_covers_public_checklist():
    doc = _read('deploy', 'WEBUI.md')
    for needle in ('Always Use HTTPS', 'HSTS', 'trusted_proxies', 'honor_script_name', 'SameSite=Lax',
                   'uploaders', 'max_download_mb', 'allowed_guilds', 'max_active_sessions',
                   'Public Bot', 'POST /auth/logout', 'application/json', '/userban'):
        assert needle in doc, needle
    assert 'GET 显示页面' not in doc
    assert '重启不掉登录' not in doc


def test_docker_doc_mentions_pin_and_limits():
    doc = _read('deploy', 'DOCKER.md')
    for needle in ('cloudflare/cloudflared:2026.10.0', 'no-new-privileges', 'mem_limit', 'pids_limit'):
        assert needle in doc, needle
