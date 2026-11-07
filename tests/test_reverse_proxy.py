# coding=utf-8
"""反向代理后面拿访问者的真实 IP(is_web_proxified = True 时启用 ReverseProxied)。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interface import ReverseProxied  # noqa: E402


def remote_addr(headers):
    seen = {}

    def app(environ, start_response):
        seen['addr'] = environ.get('REMOTE_ADDR')
        return []

    environ = {'REMOTE_ADDR': '172.22.0.3', 'PATH_INFO': '/'}
    environ.update(headers)
    ReverseProxied(app)(environ, None)
    return seen['addr']


def test_cloudflare_tunnel_client_ip():
    # cloudflared 不发 X-Real-IP,真实 IP 在 Cf-Connecting-IP
    assert remote_addr({'HTTP_CF_CONNECTING_IP': '203.0.113.7'}) == '203.0.113.7'


def test_nginx_real_ip_still_works():
    assert remote_addr({'HTTP_X_REAL_IP': '198.51.100.2'}) == '198.51.100.2'


def test_cloudflare_header_wins_over_x_real_ip():
    assert remote_addr({'HTTP_CF_CONNECTING_IP': '203.0.113.7', 'HTTP_X_REAL_IP': '10.0.0.1'}) == '203.0.113.7'


def test_without_proxy_headers_keeps_the_socket_address():
    assert remote_addr({}) == '172.22.0.3'
