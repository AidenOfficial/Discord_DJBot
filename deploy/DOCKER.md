# Discord 音乐机器人 — 绿联 NAS / Docker 部署文档

本文档把机器人以 **Docker 容器**方式部署到**绿联 NAS(UGOS Pro)**。
同样适用于任何装了 Docker 的机器。命令块可直接复制粘贴(`<...>` 替换成你自己的值)。

---

## 一、为什么用 Docker(而不是直接 apt 装)

绿联 NAS 的系统(UGOS Pro)是一个封闭的定制 Debian,直接在主机上 `apt install`
很容易把系统软件包依赖搞乱(你已经遇到过)。Docker 把机器人需要的一切
(Python、ffmpeg、libopus、yt-dlp、spotdl、Deno)全部装进**容器内部一个干净的
Debian 镜像**里:

- 容器里的 `apt` 和 NAS 主机的 `apt` 是**两套完全独立**的东西,互不影响,
  构建镜像不会动 NAS 主机一根毫毛。
- 删掉容器,机器人就干干净净地消失,不在主机上留任何依赖。
- 镜像是按本机当前代码构建的,**不存在某个文件忘记上传**的问题。
- 机器人从机房服务器搬到家里的 NAS,用的是**住宅宽带 IP**,Spotify(spotdl)
  抓 YouTube 音频不再被当作机器人拦截 —— 这正是这次搬家的主要目的。

所以在你的场景里,Docker 不是"更复杂",而是**最安全、最省心**的方案。

---

## 二、准备清单

- [ ] 一台绿联 NAS,UGOS Pro 系统,在「应用中心」装好 **Docker** 应用
      (这个应用是绿联打包的,安装它不会动主机系统)。
- [ ] 能用 **SSH 以 root 登录** NAS(UGOS「控制面板」里开启 SSH/终端机)。
- [ ] **Discord bot token** 和**服务器 ID**:按 README 的「创建 Discord 应用」一节创建应用、把 bot 邀请进服务器。
- [ ] **Spotify API 凭据**(client_id / client_secret),获取方法见 `DEPLOY.md`
      的「获取 Spotify API 凭据」小节。
- [ ] 你自己的 **Discord 用户 ID**(开发者模式下右键自己 → 复制用户 ID),设为 bot 管理员。服务器管理员默认也是。

> 绿联 DXP 系列基本是 x86_64 架构。Docker 会自动选用匹配架构的基础镜像,
> 本方案的 `Dockerfile` 不分架构,ARM / x86 都能直接构建。

---

## 三、第 1 步:把代码放到 NAS

SSH 登录 NAS 后:

```bash
cd /volume1/docker
git clone https://github.com/AidenOfficial/Discord_DJBot.git
cd Discord_DJBot
```

(NAS 上没有 git 的话,在电脑上下载仓库的 ZIP,用绿联的文件管理 / SMB 共享拷进去也行。
其实只需要 `docker-compose.yml`、`configuration.example.ini` 两个文件,镜像里有其余的一切。)

> 路径按你的实际存放位置调整。下文统一用 `<项目目录>` 指代它。

---

## 四、第 2 步:准备配置文件

**重要:必须在启动容器之前先建好 `configuration.ini` 这个文件。**
否则 Docker 挂载时会把它当成一个**目录**创建,机器人就读不到配置。

```bash
cd <项目目录>
cp configuration.example.ini configuration.ini
nano configuration.ini
```

token 不写进 `configuration.ini`,而是放进同目录的 `.env`(compose 会读它,已在 `.gitignore` 里):

```bash
echo 'DISCORD_TOKEN=<你的 bot token>' > .env
chmod 600 .env
```

最小配置(其余选项会自动从 `configuration.default.ini` 取默认值):

```ini
[discord]
; 服务器 ID
guild_id = <服务器 ID>
; 启动时进入的语音频道:频道名、"分类名/频道名" 或频道 ID;不填就等有人 /play 或 /join
;channel = <语音频道>
; "正在播放" 之类的公告发到哪个文字频道(频道 ID);不填就发到最近有人用命令的频道
;announce_channel = <文字频道 ID>

[bot]
; 管理员的 Discord 用户 ID 或身份组 ID,多个用逗号隔开
admin = <你的 Discord 用户 ID>
language = zh_CN

[spotify]
client_id = <你的 Spotify Client ID>
client_secret = <你的 Spotify Client Secret>
```

保存退出(nano 里按 `Ctrl+O`、回车、`Ctrl+X`)。

---

## 五、第 3 步:拉取镜像并启动

镜像由 GitHub Actions 自动构建并发布到 `ghcr.io/aidenofficial/discord_djbot`
(`main` 每次推送更新 `edge` 标签),NAS 上不用再构建。

```bash
cd <项目目录>
docker compose pull       # 拉取镜像,需联网
docker compose up -d      # 后台启动
docker compose logs -f    # 查看实时日志
```

想固定某个发布版本,在 `<项目目录>/.env` 写 `BAM_IMAGE=ghcr.io/aidenofficial/discord_djbot:1.2.3`。
从本地源码构建见 `docker-compose.build.yml` 开头的说明。

日志里出现 `logged in as ...` 和 `synced NN slash commands` 就说明连上了。然后自己进一个语音频道,
在服务器里试:`/help`、`/play query:<歌名>`、`/bili video:<B站链接>`、`/queue`、`/skip`。

(`Ctrl+C` 只是退出"看日志",不会停掉容器。)

> **想用图形界面也行**:UGOS Pro 的 Docker 应用 →「项目 / Compose」→ 新建项目 →
> 指向 `<项目目录>` 里的 `docker-compose.yml` 导入并启动即可。
> 但首次建议先用上面的命令行,报错信息更直观。

---

## 六、第 4 步:每天自动更新 yt-dlp / spotdl

B 站 / YouTube 经常改版,yt-dlp 必须保持最新。容器已设 `BAM_UPDATE_ON_START=1`
—— **每次启动都会自动升级 yt-dlp 和 spotdl**。只要让容器每天重启一次即可。

SSH 里执行 `crontab -e`,加一行(每天凌晨 5 点重启):

```cron
0 5 * * * docker restart discord-music
```

或用 UGOS「控制面板 → 计划任务」新建一个每天执行 `docker restart discord-music`
的定时任务。

部署到此结束。机器人已在后台常驻,崩溃自动重启,并每天自动更新。

---

## 七、日常运维

| 操作 | 命令 |
|---|---|
| 看实时日志 | `docker compose logs -f` |
| 重启 | `docker compose restart` |
| 停止 | `docker compose stop` |
| 再启动 | `docker compose up -d` |
| 改完 `configuration.ini` 生效 | `docker compose restart` |
| 更新到最新版 | `docker compose pull && docker compose up -d` |
| 用本地源码构建 | `docker compose -f docker-compose.yml -f docker-compose.build.yml up -d --build` |
| 进容器内部排查 | `docker exec -it discord-music bash` |

**数据持久化**:`configuration.ini`、`data/`(状态数据库、Web 用户别名与个人歌单)、
`music_folder/`(本地音乐 + Web 上传)、`cache/`(YouTube / B 站下载缓存)、
`spotdl_cache/`(Spotify 下载缓存)都挂载在 `<项目目录>` 下,容器删除重建都不会丢。

**容器加固与资源上限**(`docker-compose.yml` 已写好):两个容器都带 `security_opt: no-new-privileges:true`;
bot 限 `mem_limit: 1536m`、`pids_limit: 512`,cloudflared 限 `mem_limit: 256m`,ffmpeg / yt-dlp 失控时只影响
这个容器。没有 `cap_drop: ALL`,因为 entrypoint 要用默认能力装出站过滤规则。cloudflared 固定在
`cloudflare/cloudflared:2026.10.0`(不用 `:latest`),升级时改 compose 里的版本号再 `docker compose --profile tunnel up -d`。
内存不够用(日志里反复重启、`docker inspect` 退出码 137)时调大 `mem_limit`。

> 从旧版本升级:`cache/` 是新加的挂载(以前缓存在容器内的 `/tmp`,每次重建都清空)。
> `docker compose up -d` 时 Docker 会自动建好这个目录。缓存上限默认 4GB,
> 在 Web UI 的 **Cache** 页查看占用、固定常听的歌、手动释放空间。

## 七之一、禁止访问内网(出站过滤)

用户点歌给的链接由 bot 去抓。不加限制的话,有人可以给一个指向局域网的链接(或者公网链接跳转到局域网),
让 bot 去访问 NAS 管理页、路由器、`169.254.169.254` 这类内网地址(SSRF)。两层防护:

1. **bot 进程里**(`[bot] block_private_network = True`,默认开):所有 Python 发起的连接在建立时检查目标 IP,
   内网 / 本机 / 链路本地 / CGNAT 地址一律拒绝,跳转和 DNS 重绑定也拦得住。
2. **容器网络层**(`BAM_EGRESS_FILTER=1`,`docker-compose.yml` 默认开):entrypoint 用 iptables 在
   **容器自己的网络命名空间**里拒绝发往
   `10.0.0.0/8`、`172.16.0.0/12`、`192.168.0.0/16`、`169.254.0.0/16`、`100.64.0.0/10` 等网段的连接,
   管住 ffmpeg、deno、spotdl 这些子进程和 yt-dlp 伪装浏览器时用的 curl_cffi(它们不走 Python 的 socket)。
   规则装好后 entrypoint 用 `setpriv` 去掉 `NET_ADMIN` 再启动 bot,bot 自己改不了规则。

放行的:回环(Docker 内置 DNS `127.0.0.11`)、已建立连接的回包(cloudflared 连进来的 Web 请求不受影响)、
`/etc/resolv.conf` 里的 DNS 服务器(只放 53 端口)。Discord、YouTube、B 站等外网照常。

需要的 compose 配置(仓库里的 `docker-compose.yml` 已经写好):

```yaml
services:
  botamusique:
    cap_add:
      - NET_ADMIN
    environment:
      BAM_EGRESS_FILTER: ${BAM_EGRESS_FILTER:-1}
      BAM_EGRESS_ALLOW: ${BAM_EGRESS_ALLOW:-}
```

- 局域网里有 bot 要用的服务(HTTP 代理、Icecast 电台):在 `.env` 写
  `BAM_EGRESS_ALLOW=192.168.1.10/32`(逗号分隔多个),同时在 `configuration.ini` 的
  `[bot] private_network_allow` 写同样的网段(bot 进程那一层)。`HTTP(S)_PROXY` 环境变量里的代理
  bot 进程会自动放行,容器层仍要写进 `BAM_EGRESS_ALLOW`。
- 验证:`docker compose logs botamusique | grep egress` 能看到
  `[egress-filter] IPv4 private networks blocked`;再执行
  `docker exec discord-music curl -m 5 -sS http://192.168.1.1/` 应该立刻报 `Couldn't connect`,
  `docker exec discord-music curl -sS -o /dev/null -w '%{http_code}\n' https://discord.com/api/v10/gateway` 返回 `200`。
- 启动日志报 `出站过滤没装上` 并退出:容器没有 `NET_ADMIN`(检查 `cap_add`),或者内核不支持 iptables。
  临时关掉:`.env` 里 `BAM_EGRESS_FILTER=0`。

**绿联 NAS 上用 Docker 图形界面(不是 compose)建的容器**:在容器设置 → 高级 → 能力(Capabilities)里勾选
`NET_ADMIN`,环境变量加 `BAM_EGRESS_FILTER=1`。界面里没有能力设置时,改在宿主机上过滤
(UGOS 是 Debian,有 iptables;需要 SSH 并 sudo):

```bash
# 查容器的 IP(compose 网络里每次重建可能变,所以按接口过滤更稳:先查网桥名)
sudo docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}} {{.NetworkID}}{{end}}' discord-music
# DOCKER-USER 链是 Docker 留给用户的,Docker 自己不会改。把 <IP> 换成上面查到的地址
for net in 10.0.0.0/8 172.16.0.0/12 192.168.0.0/16 169.254.0.0/16 100.64.0.0/10; do
  sudo iptables -I DOCKER-USER -s <IP> -d "$net" -m conntrack ! --ctstate ESTABLISHED,RELATED -j REJECT
done
```

这样拦不住容器访问 NAS 自己(发往网桥网关的包走 INPUT 链,不经过 DOCKER-USER),也不会开机保留
(要在 UGOS 的计划任务里加一个开机运行的脚本),所以能用 compose 就优先用上面的容器内过滤。

---

## 八、故障排查

**`configuration.ini` 变成了一个目录**
- 启动容器前没先创建该文件。`docker compose down`,删掉那个错误的目录,
  按第四节正确创建文件后重新 `up`。

**容器起不来,日志报 `exec format error` 或 bad interpreter**
- `entrypoint.sh` 换行符问题。`Dockerfile` 已用 `sed` 自动修复,正常不会遇到;
  若仍出现,`docker compose pull` 重新拉取镜像。

**机器人连不上 Discord / 日志报 `Improper token has been passed`**
- `.env` 里的 `DISCORD_TOKEN` 不对或已被重置:到 Developer Portal → Bot → Reset Token 重新生成,
  改好 `.env` 后 `docker compose up -d`(只 restart 不会重新读 `.env`)。

**输入 `/` 看不到 bot 的命令**
- 邀请 bot 时没勾 `applications.commands` scope:用 README 里的邀请链接重新邀请一次。
- `guild_id` 填的不是这个服务器;日志里 `synced NN slash commands to <服务器名>` 会写同步到了哪。

**bot 进不了语音频道**
- bot 在那个频道没有「连接」「说话」权限;舞台频道不支持。

**`/bili` 报下载失败**
- 多半是 B 站改版导致 yt-dlp 暂时失效。`docker restart discord-music`
  会触发自动升级。大会员 / 番剧内容需要 cookies,见下。

**`/spotify` 失败**
- 检查 `[spotify]` 的 client_id / client_secret 是否填对。
- 住宅 IP 下 spotdl 抓 YouTube 一般**不需要 cookies** —— 这正是搬到家里 NAS
  的意义。若极少数情况下仍被 YouTube 要求登录验证,再来加 cookies 支持。

**B 站大会员 / 番剧需要 cookies**
- 用浏览器扩展导出 `bilibili.com` 的 Netscape 格式 cookies 文件,放进
  `<项目目录>/cookies/`;在 `docker-compose.yml` 里取消 `./cookies` 那行挂载的注释;
  在 `configuration.ini` 的 `[youtube_dl]` 段加
  `cookie_file = /botamusique/cookies/bili.txt`;最后 `docker compose up -d`。

**机器人反复重启 / 想查崩溃原因**
- `docker compose logs --since 24h botamusique | grep -E "CRITICAL|Traceback|ERROR" -A 20`
  能看到最近一天的异常栈。`playback loop stalled` 表示主循环被卡住、看门狗主动重启;
  `unhandled exception in thread` 表示某个工作线程出错(新版只记录、不再整个退出)。
- `docker inspect -f '{{.RestartCount}} {{.State.ExitCode}}' discord-music` 看重启次数与上次退出码
  (137 = 被 OOM 或 docker kill,1 = 程序主动退出)。

**机器人在频道里但没声音 / 想看详细日志**
- 在 `configuration.ini` 的 `[debug]` 段加 `ffmpeg = True` 和 `youtube_dl = True`,
  `docker compose restart` 后看 `docker compose logs -f`。

---

## 九、命令速查

在服务器里输入 `/` 就能看到全部命令和参数说明,`/help` 列出全部命令;
常用命令见 `DEPLOY.md` 第八节。
