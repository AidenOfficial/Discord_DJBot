#!/usr/bin/env bash
# 容器网络层的出站过滤:不让容器里的任何进程(bot、ffmpeg、deno、spotdl、curl_cffi)连内网。
# bot 进程里还有一层(bot/egress.py),但它管不到子进程和 C 库自己发的连接,所以在这里再拦一次。
#
# 由 entrypoint.sh 在 BAM_EGRESS_FILTER=1 时调用,需要容器有 NET_ADMIN 能力
# (docker-compose.yml 里的 cap_add: [NET_ADMIN])。规则装在容器自己的网络命名空间里,
# 不影响宿主机和别的容器;entrypoint 装完规则就去掉 NET_ADMIN,bot 进程改不了规则。
#
# 放行:回环(Docker 的内置 DNS 127.0.0.11)、已建立连接的回包(cloudflared 连进来的 Web 请求)、
# /etc/resolv.conf 里的 DNS 服务器(只放 53 端口)、BAM_EGRESS_ALLOW 里的网段(逗号或空格分隔,
# 比如局域网里的 HTTP 代理 192.168.1.10/32)。
# 拦截:10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 169.254.0.0/16 100.64.0.0/10 等内网 / 保留网段。
set -euo pipefail

CHAIN=BAM_EGRESS
BLOCK_V4="0.0.0.0/8 10.0.0.0/8 100.64.0.0/10 127.0.0.0/8 169.254.0.0/16 172.16.0.0/12 192.0.0.0/24 192.168.0.0/16 198.18.0.0/15 224.0.0.0/4 240.0.0.0/4"
BLOCK_V6="::1/128 fc00::/7 fe80::/10"

pick() {
    # nf_tables 后端不行(老内核)就退回 legacy
    local base=$1
    if "$base" -w -L OUTPUT -n >/dev/null 2>&1; then
        echo "$base"
    elif command -v "$base-legacy" >/dev/null 2>&1 && "$base-legacy" -w -L OUTPUT -n >/dev/null 2>&1; then
        echo "$base-legacy"
    else
        return 1
    fi
}

apply() {
    local ipt=$1 family=$2 block=$3
    "$ipt" -w -N "$CHAIN" 2>/dev/null || "$ipt" -w -F "$CHAIN"
    "$ipt" -w -A "$CHAIN" -o lo -j RETURN
    "$ipt" -w -A "$CHAIN" -m conntrack --ctstate ESTABLISHED,RELATED -j RETURN
    # IPv6 的邻居发现走 ICMPv6(链路本地 / 组播地址),拦了 IPv6 就整个不通
    if [ "$family" = 6 ]; then
        "$ipt" -w -A "$CHAIN" -p ipv6-icmp -j RETURN
    fi
    # DNS 服务器(默认 bridge 网络上 resolv.conf 可能直接是路由器的地址)
    local ns
    for ns in $(awk '/^nameserver/ {print $2}' /etc/resolv.conf 2>/dev/null); do
        case "$ns" in
            *:*) [ "$family" = 6 ] || continue ;;
            *) [ "$family" = 4 ] || continue ;;
        esac
        "$ipt" -w -A "$CHAIN" -d "$ns" -p udp --dport 53 -j RETURN
        "$ipt" -w -A "$CHAIN" -d "$ns" -p tcp --dport 53 -j RETURN
    done
    local net
    allow="${BAM_EGRESS_ALLOW:-}"
    for net in ${allow//,/ }; do
        case "$net" in
            *:*) [ "$family" = 6 ] || continue ;;
            *) [ "$family" = 4 ] || continue ;;
        esac
        "$ipt" -w -A "$CHAIN" -d "$net" -j RETURN
    done
    for net in $block; do
        "$ipt" -w -A "$CHAIN" -d "$net" -j REJECT
    done
    "$ipt" -w -C OUTPUT -j "$CHAIN" 2>/dev/null || "$ipt" -w -I OUTPUT 1 -j "$CHAIN"
}

if ! command -v iptables >/dev/null 2>&1; then
    echo "[egress-filter] iptables is not installed in this image" >&2
    exit 1
fi
if ! IPT=$(pick iptables); then
    echo "[egress-filter] cannot use iptables: the container needs the NET_ADMIN capability (cap_add: [NET_ADMIN])" >&2
    exit 1
fi
apply "$IPT" 4 "$BLOCK_V4"
echo "[egress-filter] IPv4 private networks blocked ($IPT)${BAM_EGRESS_ALLOW:+, allowed: $BAM_EGRESS_ALLOW}"

# IPv6:容器多半没开 IPv6,装不上不算失败
if IP6T=$(pick ip6tables 2>/dev/null) && apply "$IP6T" 6 "$BLOCK_V6" 2>/dev/null; then
    echo "[egress-filter] IPv6 private networks blocked ($IP6T)"
fi
