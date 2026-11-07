# coding=utf-8
"""所有测试共用的隔离:
- DNS:util.is_public_url 要解析域名,测试里不联网——IP 字面量原样返回,localhost 是 127.0.0.1,
  其它域名都当成解析到一个公网地址。要测别的解析结果的测试自己 monkeypatch util.resolve_host。
- 限流计数和出站守卫是进程级的状态,每个测试前后清掉。
"""
import ipaddress
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PUBLIC_TEST_IP = '93.184.215.14'


def fake_resolve_host(host):
    host = (host or '').strip('[]')
    try:
        return [str(ipaddress.ip_address(host))]
    except ValueError:
        pass
    if host == 'localhost' or host.endswith('.localhost'):
        return ['127.0.0.1']
    return [PUBLIC_TEST_IP]


@pytest.fixture(autouse=True)
def _hermetic_network_state(monkeypatch):
    import util
    monkeypatch.setattr(util, 'resolve_host', fake_resolve_host)
    import web_security
    web_security.limiter.reset()
    yield
    web_security.limiter.reset()
    from bot import egress
    if egress.installed():
        egress.uninstall()
