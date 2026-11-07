<div align="center">
<img src="static/image/logo.png" alt="Discord-DJBot logo" width="160px" />
<h1>Discord-DJBot</h1>
<p>自托管的 <a href="https://discord.com/">Discord</a> 语音频道音乐机器人，支持斜杠命令与 Web 界面控制。</p>

<p>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT" /></a>
<a href="https://github.com/AidenOfficial/Discord_DJBot/actions/workflows/ci.yml"><img src="https://github.com/AidenOfficial/Discord_DJBot/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI" /></a>
<img src="https://img.shields.io/badge/python-3.12-blue.svg" alt="Python 3.12" />
<img src="https://img.shields.io/badge/deploy-Docker-2496ED.svg" alt="Docker" />
</p>

<p><a href="README.md">English</a> · <strong>简体中文</strong></p>
</div>

---

Discord-DJBot 进入 Discord 服务器的语音频道，播放来自 YouTube、Bilibili、Spotify、直播、网络电台及本地曲库的音频。用户用斜杠命令或浏览器控制台点歌；控制台同时提供播放队列管理、个人歌单、缓存管理与播放统计。

本项目是 [Mumble-DJBot](https://github.com/AidenOfficial/Mumble-DJBot) 的 Discord 移植版，后者 fork 自已归档的 [azlux/botamusique](https://github.com/azlux/botamusique)。播放引擎、下载链路和 Web 界面与 Mumble 版相同，只有连接层和命令入口是 Discord 专用的。

> [!NOTE]
> 目前一个 bot 实例只服务**一个 Discord 服务器**，在其他服务器里用命令会被拒绝。多服务器支持在计划中。

## 目录

- [功能](#功能)
- [环境要求](#环境要求)
- [创建 Discord 应用](#创建-discord-应用)
- [安装](#安装)
- [Web 界面与远程访问](#web-界面与远程访问)
- [安全注意事项](#安全注意事项)
- [使用](#使用)
- [配置](#配置)
- [开发](#开发)
- [致谢](#致谢)
- [许可证](#许可证)

## 功能

### 音源

- YouTube、Bilibili（BV 号或链接）、SoundCloud 等 [yt-dlp] 支持的站点及其播放列表。
- Spotify 单曲、歌单及关键词搜索，经 [spotDL] 获取音频。
- 直播、网络电台（支持 [radio-browser.info](https://www.radio-browser.info/) 检索）以及本地音频文件。

### 播放

- **边下边播：** 长视频缓冲约 30 秒音频后即开始播放，其余部分在后台继续下载。
- **跳过非音乐片段：** 自动跳过 [SponsorBlock] 与 [BilibiliSponsorBlock] 社区标注的片段，如片头口播、赞助推广等。
- 支持队列预下载、响度标准化（`loudnorm`）、平滑的音量调节以及立体声 Opus 输出。
- 五种播放模式：顺序、循环、单曲循环、随机、自动（从曲库中随机选曲）。
- 语音连接使用 Discord 强制要求的端到端加密（DAVE）。

### 斜杠命令

- 每条命令都有类型化的参数和英文、简体中文、日文说明（按用户的 Discord 语言显示），队列序号、歌单、曲库文件、预设电台和标签都能自动补全。
- `/play` 可以填歌名、链接或队列序号；bot 不在语音频道时会先进入你所在的频道。
- 报错和私人命令（`/bind`、`/help`、`/web` 等）只有你自己看得到；「正在播放」之类的公告发到你指定的频道。

### 语音频道

- Web 界面按分类显示服务器的语音频道和其中的成员，可以在里面移动 bot 或设置默认频道。
- 跟随模式：频道没人时跟随最后离开的人，或始终跟随指定成员。AFK 频道和其他 bot 不计入。
- 频道持续无人达到设定时长（默认 5 分钟）后自动暂停，有人回来时自动继续；bot 被人踢出语音时也会暂停。

### Web 界面

- **Now Playing：** 高清专辑封面和正式歌名（去网易云 / iTunes / Deezer 匹配，对不上时用 Shazam 识别）、可拖动的播放进度、显示预计开始时间的准备面板。
- **队列：** 支持拖拽排序，并可统一搜索 YouTube 与 Bilibili。
- **曲库：** 支持浏览与分片上传，单文件默认上限 4 GB，可断点续传；视频文件只保留音轨。
- **缓存：** 显示存储占用与播放次数，常听的曲目可固定或转存至曲库。
- **统计：** 最常播放的曲目、点歌最多的用户、最活跃的时段以及最常被跳过的曲目。

### 个人歌单

- 以 Cloudflare Access 传递的登录邮箱识别用户，或在[用 Discord 登录](#用-discord-登录)后以 Discord 账号识别；用户可设置显示别名。
- 每位用户拥有独立歌单，可立即播放、随机播放或追加到队列。
- 可从 YouTube、网易云音乐、QQ 音乐与 Spotify 导入歌单。
- 可通过一次性绑定码（`/bind`）把 Discord 账号与 Web 身份关联，之后在 Discord 里用 `/mylist`、`/fav` 使用个人歌单。

### 可靠性

- 主循环停滞超过 120 秒时，看门狗会让进程退出并重启；心跳文件可用于容器健康检查。
- discord.py 会自动重连网关和语音；下载失败时自动断点续传并重试。

## 环境要求

- 一个你能添加 bot 的 Discord 服务器（需要「管理服务器」权限）。
- **Docker 部署（推荐）：** Docker Engine 与 Docker Compose，所有运行时依赖都已打包进镜像。
- **裸机部署：** Python 3.12、FFmpeg 与 libopus，参见 [`deploy/DEPLOY.md`](deploy/DEPLOY.md)。
- **可选：** Spotify API 凭据，仅 `/spotify` 命令需要（网页上导入 100 首以内的 Spotify 歌单不需要）。
- **可选：** Cloudflare 账号，用于远程访问 Web 界面。

## 创建 Discord 应用

1. 打开 [Discord Developer Portal](https://discord.com/developers/applications)，点 **New Application** 新建应用。
2. 在 **Bot** 页点 **Reset Token** 并复制 token。token 等同于密码，拿到它的人就能控制这个 bot。不需要任何特权 Intent，*Presence*、*Server Members*、*Message Content* 都保持关闭。
3. 在 **OAuth2 → URL Generator** 里勾选 scope `bot` 和 `applications.commands`，权限勾选 *View Channels*、*Send Messages*、*Embed Links*、*Attach Files*、*Read Message History*、*Connect*、*Speak*、*Set Voice Channel Status*，打开生成的链接把 bot 加进服务器。等价的链接是：

   ```text
   https://discord.com/oauth2/authorize?client_id=<应用 ID>&scope=bot+applications.commands&permissions=281474979974144
   ```

   *Embed Links*、*Attach Files*、*Read Message History* 是「正在播放」面板要用的（封面、进度条、按钮）；*Set Voice Channel Status* 用来在语音频道名下面显示正在放的歌。bot 已经在服务器里的话，再打开一次新链接授权即可。

4. 在 Discord 里打开 **设置 → 高级 → 开发者模式**，右键服务器图标选 **复制服务器 ID**，填到 `[discord] guild_id`。

bot 每次启动时都会把斜杠命令注册到这个服务器，命令立即可用。

## 安装

### 1. 克隆仓库

```bash
git clone https://github.com/AidenOfficial/Discord_DJBot.git
cd Discord_DJBot
```

### 2. 创建配置文件和 token 文件

```bash
cp configuration.example.ini configuration.ini
echo 'DISCORD_TOKEN=<你的 bot token>' > .env
```

> [!IMPORTANT]
> 启动容器之前必须先创建 `configuration.ini`，否则 Docker 会以同名目录代替该文件，导致机器人无法读取配置。`.env` 已写在 `.gitignore` 里，不要把 token 提交到 Git。

最小配置如下。未填写的项会回退到 `configuration.default.ini` 中的默认值，该文件不应修改。

```ini
[discord]
guild_id = 123456789012345678     ; 服务器 ID
; channel = Music                 ; 启动时进入的语音频道(频道名、分类/频道名,或频道 ID)
; announce_channel = 234567890123456789  ; "正在播放"等公告发到的文字频道

[bot]
admin = 345678901234567890        ; 管理员的用户 ID 或身份组 ID,逗号分隔;服务器管理员自动算
language = zh_CN                  ; en_US、zh_CN 或 ja_JP

[webinterface]
enabled = True
listening_addr = 0.0.0.0          ; 容器内必须如此设置,由 Compose 网络隔离
```

### 3. 拉取镜像并启动

镜像由 GitHub Actions 构建并发布到 `ghcr.io/aidenofficial/discord_djbot`（`edge` 跟随 `main`）。如需从源码构建，参见 `docker-compose.build.yml`。

```bash
docker compose pull
docker compose up -d
docker compose logs -f
```

bot 主动连出到 Discord，无需映射任何端口。日志里出现 `synced NN slash commands` 后，在服务器里输入 `/` 就能看到命令；进一个语音频道，试试 `/play 歌名`。

### 4. 保持解析器为最新版本

容器每次启动时会自动升级 yt-dlp 与 spotDL（`BAM_UPDATE_ON_START=1`）。YouTube 与 Bilibili 改版频繁，建议每天重启一次容器，例如使用 cron：

```cron
0 5 * * * docker restart discord-music
```

NAS 部署、cookies 配置与日常维护参见 [`deploy/DOCKER.md`](deploy/DOCKER.md)。

## Web 界面与远程访问

推荐通过 Cloudflare Tunnel 配合 Cloudflare Access 发布 Web 界面：由 Cloudflare 负责身份验证，8181 端口无需对外暴露。

1. 在 Cloudflare Zero Trust 控制台中创建 Tunnel，将 Public Hostname 指向 `http://botamusique:8181`。
2. 为同一域名创建 Access Application，并通过策略指定允许访问的邮箱。
3. 把 Tunnel token 加进 `.env`，启动 `tunnel` profile：

   ```bash
   echo 'CLOUDFLARE_TUNNEL_TOKEN=<token>' >> .env
   docker compose --profile tunnel up -d
   ```

详细步骤参见 [`deploy/WEBUI.md`](deploy/WEBUI.md)。

### 用 Discord 登录

Web 界面也可以用 Discord 账号登录（OAuth2，scope 为 `identify guilds`）。已经用 `/bind` 绑定过的人，登录后沿用原来的歌单和收藏；其他人会得到一个挂在 Discord 账号上的新 Web 身份，不再需要 `/bind`。

1. 在 [Developer Portal](https://discord.com/developers/applications) 打开你的应用 → **OAuth2**，添加 Redirect：`<public_url>/auth/discord/callback`（例如 `https://music.example.com/auth/discord/callback`）。
2. 把 **Client ID** 和 **Client Secret** 填进 `configuration.ini`：

   ```ini
   [webinterface]
   auth_method = discord        ; 强制用 Discord 登录（也可以保持 token/none，把它当作可选登录方式）
   discord_client_id = <client id>
   discord_client_secret =      ; 也可以改在 .env 里设置 DISCORD_CLIENT_SECRET
   public_url = https://music.example.com
   ```

3. 重启 bot。`auth_method = discord` 时，未登录的页面会跳转到 Discord，`/api/*` 返回 401，并且只放行和 bot 在同一个服务器里的账号。`auth_method = token` 时，令牌页会多一个“用 Discord 登录”按钮。

> [!CAUTION]
> Client Secret 是凭据，绝不能提交到 git。环境变量 `DISCORD_CLIENT_SECRET` 优先于 ini 里的值。

## 安全注意事项

> [!WARNING]
> 默认的 `auth_method = none` 表示应用本身不进行身份验证，完全依赖 Cloudflare Access。

- **bot token 要保密。** 一旦泄露，立即到 Developer Portal 重置。
- **不要将 8181 端口暴露**到公网或不可信网络。
- **启用 Access JWT 校验**：在 `[webinterface]` 中配置 `access_team_domain` 与 `access_aud`，绕过 Tunnel 的请求就无法冒充用户。
- **`flask_secret` 用于签名会话 Cookie**（`token` 和 `discord` 登录都靠它）。不配置时会随机生成一次并存进 settings 数据库；如果自己配置，请用足够长的随机字符串。
- 管理员和封禁都按 Discord 用户 ID / 身份组 ID 认，改昵称冒充不了。

## 使用

### 斜杠命令

在服务器里输入 `/` 就能浏览所有命令和参数，`/help` 按 bot 的语言列出全部命令。命令名可在 `[commands]` 段中修改。

| 命令 | 说明 |
|---|---|
| `/play [query]` | 按歌名或链接点歌、继续播放，或（填数字）播放队列里的那一首 |
| `/url` / `/bili` / `/spotify` / `/playlist` | 添加链接、B 站视频、Spotify 链接或搜索、整个播放列表 |
| `/ysearch` → `/pick` | 搜索 YouTube，再按序号挑选 |
| `/live` / `/radio` / `/rbquery` / `/rbplay` | 直播与网络电台 |
| `/file` / `/filematch` / `/search` / `/tag` | 本地曲库 |
| `/pause` / `/skip` / `/stop` / `/last` | 播放控制 |
| `/queue` / `/np` / `/remove` / `/shuffle` / `/repeat` / `/clear` | 队列 |
| `/mode` / `/volume` | 播放模式与音量 |
| `/join` / `/leave` | 进入你所在的语音频道 / 停止并离开 |
| `/bind` / `/mylist` / `/fav` | 个人歌单（绑定码在 Web 界面中生成） |
| `/lyrics` / `/web` / `/help` / `/version` | 其他 |

服务器管理员（有「管理员」或「管理服务器」权限的成员，可用 `[discord] admin_by_permission = False` 关掉；以及 `[bot] admin` 里列出的身份组）可以用 `/maxvolume`、`/userban`、`/userunban`、`/urlban`、`/urlunban`、`/banlist` 管理自己的服务器。这些命令默认只有「管理服务器」权限的人看得到，服务器可以在「服务器设置 → 整合」里改。

bot 主人（`[bot] admin` 里的用户 ID）在所有服务器都是管理员，另外还有全局封禁（`/globalban`、`/globalunban`、`/globalbanlist`、`/urlwhitelist`、`/urlunwhitelist`）和运维命令（`/kill`、`/update`、`/rescan`、`/dropdatabase`、Web 用户相关命令）。这些命令只注册在 `[discord] owner_guild_id`（留空则注册成全局命令，默认只有「管理员」看得到），每次执行都会核对主人的用户 ID。

默认只有和 bot 在同一个语音频道的人能控制播放（见 `[bot] allow_other_channel_message`）。

## 配置

[`configuration.example.ini`](configuration.example.ini) 说明了所有配置项。较常调整的有：

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `[discord] guild_id` | （第一个服务器） | bot 服务的服务器 |
| `[discord] channel` | （无） | 启动时进入的语音频道；Web 设置页里设置过的以 Web 为准 |
| `[discord] announce_channel` | （最近发命令的频道） | 公告发到的文字频道 |
| `[discord] bitrate` | `0` | Opus 码率（kbps），`0` 跟随语音频道的码率 |
| `[bot] stream_while_downloading` | `True` | 长曲目下载完成前即开始播放 |
| `[bot] tmp_folder_max_size` | `4096` | 下载缓存上限（MB），超出时优先淘汰最久未使用的条目 |
| `[bot] max_track_duration` | `0` | 单曲时长上限（分钟），`0` 表示不限制 |
| `[bot] sponsorblock` | `True` | 跳过非音乐片段 |
| `[bot] playback_mode` | `one-shot` | 启动时的播放模式 |
| `[youtube_dl] cookie_file` | （空） | Netscape 格式的 cookies，用于 Bilibili 大会员内容或已登录的 YouTube |

token 也可以（推荐）用环境变量 `DISCORD_TOKEN` 传入；命令行的 `--guild` / `--channel` 优先于 INI 文件。

## 开发

### 运行测试

测试不连接 Discord。

```bash
python3.12 -m venv venv
venv/bin/pip install -r requirements.txt pytest
venv/bin/python -m pytest tests
```

Docker 镜像用的是 Python 3.12；在 3.13 及以上，`requirements.txt` 会自动装上 `audioop-lts`。

### 构建 Web 界面

控制台源码位于 `webui/`，使用 Vue 3、TypeScript、Vite 与 Tailwind CSS 4 构建。

```bash
cd webui
npm ci
npm run dev     # 开发服务器，/api 代理到 127.0.0.1:8181
npm run build   # 生产构建输出到 webui/dist
```

`webui/dist` 已提交到仓库，以便没有 Node.js 的环境直接部署。修改前端时，请将更新后的构建产物一并提交。

### 冒烟测试

`scripts/smoke_test.py` 在不连接 Discord 的情况下检查运行环境（FFmpeg、libopus、DAVE、spotDL、Deno）以及 Bilibili 与 Spotify 的下载链路，参见 [`deploy/VERIFY.md`](deploy/VERIFY.md)。

### 持续集成

| Workflow | 触发条件 | 内容 |
|---|---|---|
| `ci.yml` | 推送到 `main`、PR、每周 | Ruff、ShellCheck、Hadolint、actionlint；在 Python 3.12 与 3.13 上运行测试；构建 Web 界面并检查 `webui/dist` 是否最新；构建 Docker 镜像并运行离线冒烟测试。分支保护只需要求 `CI OK`。 |
| `docker-publish.yml` | 推送到 `main`、`v*` tag | 构建 `linux/amd64` 与 `linux/arm64` 镜像，推送到 `ghcr.io/aidenofficial/discord_djbot`，附带 SBOM、构建来源证明和 Trivy 扫描。 |
| `release.yml` | `v*` tag | 创建 GitHub Release，按标签分组生成发布说明。 |
| `codeql.yml`、`dependency-review.yml`、`pr-triage.yml`、`stale.yml` | 各不相同 | 代码扫描、依赖审查、PR 标签与例行清理。 |

### 项目结构

| 路径 | 内容 |
|---|---|
| `djbot.py`、`bot/` | 程序入口；Discord 连接（`discord_link.py`）、HTML 转 Markdown（`discord_format.py`）、命令分发（`core.py`）、播放主循环（`player.py`）、语音频道跟随（`channels.py`）、缓存与清理 |
| `commands/` | 斜杠命令表（`slash.py`）、自动补全和命令处理 |
| `media/` | 各类音源、播放队列、SponsorBlock、封面、歌词 |
| `interface.py`、`web_*.py`、`templates/` | Flask 应用：身份验证与 `/api/*` 接口 |
| `webui/` | Web 界面源码与构建产物 |
| `lang/` | bot 消息（英文、简体中文、日文） |
| `deploy/` | 部署文档与 systemd 单元文件 |
| `tests/` | 单元测试 |

## 致谢

本项目经由 [Mumble-DJBot](https://github.com/AidenOfficial/Mumble-DJBot) 基于 Azlux 及 @TerryGeng、@mertkutay 等贡献者开发的 [botamusique](https://github.com/azlux/botamusique)，并使用了 [discord.py](https://github.com/Rapptz/discord.py)、[yt-dlp]、[spotDL]、[SponsorBlock]、[BilibiliSponsorBlock] 与 [OpenCC](https://github.com/BYVoid/OpenCC)。

## 许可证

本项目以 [MIT 许可证](LICENSE) 发布。

[yt-dlp]: https://github.com/yt-dlp/yt-dlp
[spotDL]: https://github.com/spotDL/spotify-downloader
[SponsorBlock]: https://sponsor.ajay.app/
[BilibiliSponsorBlock]: https://bsbsb.top/
