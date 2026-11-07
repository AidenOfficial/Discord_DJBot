# coding=utf-8
"""Web 界面的安全响应头和限流。

响应头(interface.py 的 after_request 统一加):
- Content-Security-Policy:脚本只能来自本站,不允许 eval / 内联脚本;frame-ancestors 只允许本站和
  Discord(Activity 是嵌在 discord.com 里的 iframe,经 <app id>.discordsays.com 代理),
  可用 [webinterface] frame_ancestors 改;
- X-Content-Type-Options: nosniff;Referrer-Policy: no-referrer(令牌登录的 ?token= 不会经
  Referer 漏给封面图所在的外站)。
  路由自己设过的同名头不覆盖。

限流:按「谁」计数,而不是只按 IP。Activity 的请求都从 Discord 代理的 IP 过来,只按 IP 一个人刷就会
把所有人一起限住。所以:
- client:登录身份(web_users.current_identity().key);没有身份(未登录、auth_method=none)才按 IP;
- guild:选中的服务器(web_context.guild_id()),防止一个服务器的人一起把 bot 刷爆;
- ip:只按 IP(登录前的接口,比如校验令牌)。
计数在本进程内存里(滑动窗口),重启清零。
"""

import collections
import threading
import time
from functools import wraps

from flask import g, has_request_context, jsonify, request
from werkzeug.exceptions import HTTPException

import variables as var

# =====================================================================
#  安全响应头
# =====================================================================

DEFAULT_FRAME_ANCESTORS = "'self' https://discord.com https://*.discord.com https://*.discordsays.com"

# 前端是 Vite 构建的 SPA:脚本 / 样式 / 字体都是本站的文件。
# - style 'unsafe-inline':Vue 的 :style 绑定和 need_token.html 的 <style>;样式注入的风险远小于脚本;
# - img https: / data::搜索结果和封面图来自各视频站 CDN,Discord 头像来自 cdn.discordapp.com,曲库缩略图是 data: URI;
# - connect 'self':前端只调本站的 /api/。
CSP_DIRECTIVES = (
    ("default-src", "'self'"),
    ("script-src", "'self'"),
    ("style-src", "'self' 'unsafe-inline'"),
    ("img-src", "'self' data: blob: https:"),
    ("media-src", "'self' blob: https:"),
    ("font-src", "'self' data:"),
    ("connect-src", "'self'"),
    ("object-src", "'none'"),
    ("base-uri", "'self'"),
    ("form-action", "'self'"),
)


def frame_ancestors():
    config = var.config
    value = DEFAULT_FRAME_ANCESTORS
    if config is not None:
        value = config.get('webinterface', 'frame_ancestors', fallback=DEFAULT_FRAME_ANCESTORS)
    # 只要第一行、去掉会破坏头部的字符;留空 = 谁都不能嵌
    value = ' '.join((value or '').replace(';', ' ').replace(',', ' ').split())
    return value or "'none'"


def content_security_policy():
    parts = [f"{name} {value}" for name, value in CSP_DIRECTIVES]
    parts.append(f"frame-ancestors {frame_ancestors()}")
    return '; '.join(parts)


def apply_security_headers(response):
    headers = response.headers
    headers.setdefault('Content-Security-Policy', content_security_policy())
    headers.setdefault('X-Content-Type-Options', 'nosniff')
    headers.setdefault('Referrer-Policy', 'no-referrer')
    return response


# =====================================================================
#  限流
# =====================================================================

# 规则:桶名 -> ((范围, 次数, 秒数), ...)。范围:client / guild / ip(见模块说明)
RULES = {
    # 搜索要跑 yt-dlp / 请求 B 站,最费资源
    'search': (('client', 30, 60), ('guild', 90, 60)),
    # 网页点歌入队(搜索结果、曲库、个人歌单整张入队)
    'enqueue': (('client', 40, 60), ('guild', 120, 60)),
    # 歌单导入:每首都要去搜索匹配
    'import': (('client', 6, 600),),
    # 往个人歌单 / 收藏里加链接
    'save': (('client', 60, 60),),
    # Discord 登录:跳转 + 回调(未登录时只能按 IP;Activity 不走这条)
    'discord_auth': (('client', 30, 60),),
    # 令牌校验(?token=):登录前,只能按 IP
    'token': (('ip', 30, 60),),
}

PRUNE_EVERY = 500


class RateLimiter:
    """滑动窗口:每个 key 记最近的请求时间。"""

    def __init__(self):
        self._hits = {}
        self._lock = threading.Lock()
        self._calls = 0

    def hit(self, key, limit, window, now=None):
        """记一次请求。超限返回还要等几秒(>0),没超返回 0(超限的那次不记)。"""
        now = time.monotonic() if now is None else now
        with self._lock:
            self._calls += 1
            if self._calls % PRUNE_EVERY == 0:
                self._prune(now)
            q = self._hits.get(key)
            if q is None:
                q = self._hits[key] = collections.deque()
            while q and q[0] <= now - window:
                q.popleft()
            if len(q) >= limit:
                return max(1, int(q[0] + window - now + 0.999))
            q.append(now)
            return 0

    def _prune(self, now):
        # 最长窗口之外的都可以丢掉
        horizon = max(w for rules in RULES.values() for _, _, w in rules)
        for key in [k for k, q in self._hits.items() if not q or q[-1] <= now - horizon]:
            del self._hits[key]

    def reset(self):
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()


def enabled():
    config = var.config
    if config is None:
        return True
    return config.getboolean('webinterface', 'rate_limit', fallback=True)


def remote_ip():
    return request.remote_addr or 'unknown'


def client_key():
    """登录身份;没有就看 Discord 登录的会话(登录流程中途);都没有才是 IP。"""
    ident = getattr(g, 'web_identity', None)
    key = getattr(ident, 'key', None)
    if key:
        return f"id:{key}"
    try:
        import web_auth_discord
        user = web_auth_discord.session_user()
    except Exception:
        user = None
    if user and user.get('id'):
        return f"discord:{user['id']}"
    return f"ip:{remote_ip()}"


def guild_key():
    """选中的服务器;这个请求选不了服务器(没有权限、个人歌单这类不分服务器的接口)就不按服务器限。"""
    try:
        import web_context
        gid = web_context.guild_id()
    except HTTPException:
        return None
    except Exception:
        return None
    return f"guild:{gid}" if gid else None


def _key_for(scope):
    if scope == 'client':
        return client_key()
    if scope == 'guild':
        return guild_key()
    return f"ip:{remote_ip()}"


def check(bucket):
    """当前请求在 bucket 里是否超限:超了返回要等的秒数,没超返回 0。"""
    if not enabled() or not has_request_context():
        return 0
    for scope, limit, window in RULES[bucket]:
        key = _key_for(scope)
        if key is None:
            continue
        wait = limiter.hit(f"{bucket}|{key}", limit, window)
        if wait:
            return wait
    return 0


def too_many(wait):
    resp = jsonify({'error': 'rate_limited', 'retry_after': wait})
    resp.status_code = 429
    resp.headers['Retry-After'] = str(wait)
    return resp


def rate_limited(bucket):
    """路由装饰器,放在 requires_auth 下面(先鉴权、有了身份再计数)。"""
    if bucket not in RULES:
        raise KeyError(bucket)

    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            wait = check(bucket)
            if wait:
                return too_many(wait)
            return f(*args, **kwargs)
        return wrapper
    return decorator


# =====================================================================
#  输错令牌 / 密码的封禁
# =====================================================================
# 只拦「再拿凭据来试」的请求,不拦已经登录的会话:Activity 的人都从 Discord 代理的同一个 IP 来,
# 封禁要是拦住整个 IP,一个人乱试就能把所有人锁在外面。封禁到期自动解除(不再是永久)。

BAN_SECONDS = 15 * 60


def ban_seconds():
    config = var.config
    if config is None:
        return BAN_SECONDS
    return max(0, config.getint('webinterface', 'ban_minutes', fallback=BAN_SECONDS // 60)) * 60
