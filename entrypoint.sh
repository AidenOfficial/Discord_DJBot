#!/usr/bin/env bash
command=( "${@}" )

if [ "$1" == "bash" ] || [ "$1" == "sh" ]; then
    exec "${@}"
fi

# 容器网络层的出站过滤(BAM_EGRESS_FILTER=1,需要 cap_add: [NET_ADMIN]):不让任何进程连内网,
# 见 scripts/egress-filter.sh 和 deploy/DOCKER.md。装好规则后用 setpriv 去掉 NET_ADMIN 再启动 bot,
# bot 和它启动的子进程都改不了规则。装不上就不启动(打开了过滤却静默失效更糟)。
drop_caps=()
if [ -n "$BAM_EGRESS_FILTER" ] && [ "$BAM_EGRESS_FILTER" != "0" ]; then
    if ! /botamusique/scripts/egress-filter.sh; then
        echo "[entrypoint] 错误:BAM_EGRESS_FILTER=1 但出站过滤没装上。" \
             "给容器加 cap_add: [NET_ADMIN],或者设 BAM_EGRESS_FILTER=0 关掉它(见 deploy/DOCKER.md)。" >&2
        exit 1
    fi
    drop_caps=( setpriv --inh-caps=-net_admin --bounding-set=-net_admin -- )
fi

# 容器启动时按需把 yt-dlp / spotdl 升级到最新版。
# B 站 / YouTube 经常改版,旧版本会失效;配合每天定时重启容器即可保持最新。
if [ -n "$BAM_UPDATE_ON_START" ]; then
    echo "[entrypoint] 正在更新 yt-dlp 与 spotdl ..."
    /botamusique/venv/bin/pip install --no-cache-dir --upgrade yt-dlp spotdl \
        || echo "[entrypoint] 警告:yt-dlp/spotdl 更新失败,改用镜像内置版本继续启动。"
fi

if [ -n "$BAM_DB" ]; then
    command+=( "--db" "$BAM_DB" )
fi

if [ -n "$BAM_MUSIC_DB" ]; then
    command+=( "--music-db" "$BAM_MUSIC_DB" )
fi

# Discord token 建议用环境变量 DISCORD_TOKEN 传(bot 直接读取,不出现在进程参数里)
if [ -n "$BAM_GUILD" ]; then
    command+=( "--guild" "$BAM_GUILD" )
fi

if [ -n "$BAM_CHANNEL" ]; then
    command+=( "--channel" "$BAM_CHANNEL" )
fi

if [ -n "$BAM_VERBOSE" ]; then
    command+=( "--verbose" )
fi

if [ -n "$BAM_CONFIG_file" ]; then
    if [ ! -f "$BAM_CONFIG_file" ]; then
        cp "/botamusique/configuration.example.ini" "$BAM_CONFIG_file"
    fi
    command+=( "--config" "$BAM_CONFIG_file" )
else
    if [ ! -f "/botamusique/configuration.ini" ]; then
        cp "/botamusique/configuration.example.ini" "/botamusique/configuration.ini"
    fi
    command+=( "--config" "/botamusique/configuration.ini" )
fi

exec "${drop_caps[@]}" "${command[@]}"
