# coding=utf-8
"""出站连接守卫:bot 进程里任何 Python socket 都不能连到内网 / 本机地址。

为什么在连接这一层拦:入口处的 util.is_public_url 只检查用户给的链接本身,挡不住
- HTTP 跳转:公网链接 302 到 http://192.168.1.1/(requests / yt-dlp 都会自动跟随);
- DNS 重绑定:检查时域名解析到公网,真正连接时解析到内网;
- 链接里间接带出来的地址:网页里的 og:image、播放列表里的条目、封面图链接。
这些最终都要 socket.connect(),所以在 socket.socket.connect / connect_ex 上检查目标 IP。
传进来的是主机名(不是 IP)时自己解析、只连检查过的那个 IP,不给二次解析留机会。

拦不住的(要靠容器网络层的过滤,见 entrypoint.sh 的 BAM_EGRESS_FILTER 和 deploy/DOCKER.md):
ffmpeg / deno / spotdl 这些子进程,和 curl_cffi(yt-dlp 伪装浏览器时用,C 库自己连)。

配置([bot]):
- block_private_network = True:装上守卫(默认);
- private_network_allow = 192.168.1.10/32, ...:放行的内网网段(比如局域网里的代理、Icecast 电台)。
环境变量 HTTP(S)_PROXY / ALL_PROXY 里的代理地址自动放行。
"""

import errno
import ipaddress
import logging
import os
import socket
import threading
import time
from urllib.parse import urlparse

import util

log = logging.getLogger("bot")

_orig_connect = socket.socket.connect
_orig_connect_ex = socket.socket.connect_ex
_orig_socketpair = socket.socketpair

_allowed = util.private_network_allow  # 和入口检查共用同一个列表
_installed = False
_bypass = threading.local()
_last_warn = {}
WARN_INTERVAL = 60


class EgressBlocked(PermissionError):
    pass


def allowed_networks():
    return list(_allowed)


def is_allowed_ip(ip):
    return util.ip_is_allowed(ip)


def _warn(ip, port):
    now = time.monotonic()
    if now - _last_warn.get(ip, 0) > WARN_INTERVAL:
        _last_warn[ip] = now
        if len(_last_warn) > 1000:
            _last_warn.clear()
        log.warning("egress: blocked connection to private address %s:%s "
                    "(allow it with [bot] private_network_allow)", ip, port)


def _resolve_checked(sock, address):
    """返回可以连的地址;目标是内网 → EgressBlocked。"""
    host, port = address[0], address[1]
    try:
        ipaddress.ip_address(str(host).split('%', 1)[0])
        is_literal = True
    except ValueError:
        is_literal = False
    if is_literal:
        if not is_allowed_ip(host):
            _warn(host, port)
            raise EgressBlocked(errno.EACCES, f"connection to private address {host} blocked")
        return address
    # 主机名:自己解析,只连检查过的 IP(socket.connect 内部会再解析一次,那就留了重绑定的空子)
    infos = socket.getaddrinfo(host, port, sock.family, sock.type)
    for info in infos:
        ip = info[4][0]
        if is_allowed_ip(ip):
            return (ip, port) + tuple(address[2:])
    blocked = infos[0][4][0] if infos else host
    _warn(blocked, port)
    raise EgressBlocked(errno.EACCES, f"connection to private address {blocked} ({host}) blocked")


def _needs_check(sock, address):
    if getattr(_bypass, 'on', False):
        return False
    return sock.family in (socket.AF_INET, socket.AF_INET6) and isinstance(address, tuple) and len(address) >= 2


def _guarded_connect(self, address):
    if _needs_check(self, address):
        address = _resolve_checked(self, address)
    return _orig_connect(self, address)


def _guarded_connect_ex(self, address):
    if _needs_check(self, address):
        try:
            address = _resolve_checked(self, address)
        except EgressBlocked:
            return errno.EACCES
    return _orig_connect_ex(self, address)


def _guarded_socketpair(*args, **kwargs):
    # Windows 上 socketpair() 是用连 127.0.0.1 模拟的(asyncio 的事件循环要用),放行
    _bypass.on = True
    try:
        return _orig_socketpair(*args, **kwargs)
    finally:
        _bypass.on = False


def _proxy_networks():
    nets = []
    for name in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'http_proxy', 'https_proxy', 'all_proxy'):
        value = os.environ.get(name)
        if not value:
            continue
        try:
            host = urlparse(value if '://' in value else 'http://' + value).hostname
            if not host:
                continue
            for info in socket.getaddrinfo(host, None):
                ip = ipaddress.ip_address(info[4][0].split('%', 1)[0])
                nets.append(ipaddress.ip_network(ip))
        except (OSError, ValueError, UnicodeError):
            log.warning("egress: cannot resolve proxy %s=%s; it is not allow-listed", name, value)
    return nets


def parse_networks(raw):
    nets = []
    for part in (raw or '').replace(';', ',').replace(' ', ',').split(','):
        part = part.strip()
        if not part:
            continue
        try:
            nets.append(ipaddress.ip_network(part, strict=False))
        except ValueError:
            log.warning("egress: ignoring invalid network %r in private_network_allow", part)
    return nets


def install(config=None):
    """按配置装上守卫(重复调用只更新放行列表)。返回是否装上。"""
    global _installed
    enabled, allow = True, ''
    if config is not None:
        enabled = config.getboolean('bot', 'block_private_network', fallback=True)
        allow = config.get('bot', 'private_network_allow', fallback='')
    if not enabled:
        uninstall()
        log.info("egress: private network guard disabled ([bot] block_private_network = False)")
        return False
    _allowed[:] = parse_networks(allow) + _proxy_networks()
    if not _installed:
        socket.socket.connect = _guarded_connect
        socket.socket.connect_ex = _guarded_connect_ex
        socket.socketpair = _guarded_socketpair
        _installed = True
    if _allowed:
        log.info("egress: private network guard on, allowed: %s", ', '.join(str(n) for n in _allowed))
    else:
        log.info("egress: private network guard on")
    return True


def uninstall():
    global _installed
    socket.socket.connect = _orig_connect
    socket.socket.connect_ex = _orig_connect_ex
    socket.socketpair = _orig_socketpair
    _allowed.clear()
    _installed = False


def installed():
    return _installed
