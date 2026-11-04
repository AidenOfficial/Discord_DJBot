# Discord 音乐机器人 — Linux(裸机)部署文档

本文档是把这个机器人直接部署到一台 Ubuntu / Debian Linux 机器(ARM 或 x86)上的完整步骤。
按顺序做即可。命令块都可以直接复制粘贴(尖括号 `<...>` 的部分替换成你自己的值)。

> **要部署到绿联 NAS,或其他不方便直接用 `apt` 装系统依赖的设备?**
> 请改用 Docker 方案,见 [`DOCKER.md`](DOCKER.md)。Docker 把全部依赖装在容器内,
> 与宿主机系统完全隔离,不会影响 NAS 本身。

---

## 一、开始前的准备清单

动手前先把下面这些准备好:

- [ ] 一台 **ARM 架构的 Ubuntu Linux** 机器,你有 `sudo` 权限,能 SSH 登录。
- [ ] **Discord bot token** 和**服务器 ID**:按 README 的「Setting up the Discord application / 创建 Discord 应用」一节创建应用、把 bot 邀请进服务器。
- [ ] **Spotify API 凭据**(`/spotify` 命令需要)—— 见下方「获取 Spotify API 凭据」。
- [ ] 你自己的 **Discord 用户 ID**(开发者模式下右键自己 → 复制用户 ID),设为 bot 管理员,用于 `/update`、`/kill` 等管理命令。
      服务器的管理员默认也是 bot 管理员。
- [ ] (可选)**B 站 cookies 文件** —— 只有要播放大会员专享/番剧时才需要,见第九节。

### 获取 Spotify API 凭据

1. 打开 <https://developer.spotify.com/dashboard>,用**任意 Spotify 账号**登录(免费账号即可,**不需要 Premium**)。
2. 点 **Create app**。App name / description 随便填;**Redirect URI** 填 `http://localhost:8888/callback`(spotdl 用不到回调,但表单必填);API 勾选 **Web API**。
3. 创建后进入该 App 的 **Settings**,记下 **Client ID**;点 **View client secret** 记下 **Client Secret**。
4. 这两个值稍后填进配置文件。

---

## 二、第 1 步:把代码放到服务器上

```bash
sudo git clone https://github.com/AidenOfficial/Discord_DJBot.git /opt/botamusique
cd /opt/botamusique
```

> 安装路径用 `/opt/botamusique` 是因为 `deploy/` 里的 systemd 文件都按这个路径写死。
> 如果你坚持用别的路径,需要同步改 `deploy/` 下三个 `.service` / `.timer` 文件里的路径。

---

## 三、第 2 步:运行安装脚本

```bash
cd /opt/botamusique
bash deploy/install.sh
```

这个脚本会:用 `apt` 安装系统依赖(Python、ffmpeg、libopus 等)、创建 Python 虚拟环境 `venv/`、安装全部 Python 依赖(含 `yt-dlp`、`spotdl`)、做安装后验证、并生成一份初始 `configuration.ini`。

ARM 上首次安装可能较慢(部分依赖需要本地编译),耐心等待。结束时若看到 spotdl / yt-dlp / ffmpeg 三个版本号正常打印,说明依赖就绪。

---

## 四、第 3 步:编辑配置文件

用编辑器打开配置文件:

```bash
nano /opt/botamusique/configuration.ini
```

最省事的做法:**把整个文件内容替换成下面这份最小配置**(其余所有选项都会自动从 `configuration.default.ini` 取默认值):

```ini
[discord]
; bot token。也可以不写在这里,改用环境变量 DISCORD_TOKEN(见第六步)
token = <你的 bot token>
; 服务器 ID
guild_id = <服务器 ID>
; 启动时进入的语音频道:频道名、"分类名/频道名" 或频道 ID;不填就等有人 /play 或 /join
;channel = <语音频道>

[bot]
; 管理员的 Discord 用户 ID 或身份组 ID,多个用逗号隔开
admin = <你的 Discord 用户 ID>
language = zh_CN

[spotify]
client_id = <你的 Spotify Client ID>
client_secret = <你的 Spotify Client Secret>
```

保存退出(nano 里按 `Ctrl+O`、回车、`Ctrl+X`)。

**说明:**
- 不填 `[spotify]` 也能启动,只是 `/spotify` 命令会提示未配置;`/bili` 不受影响。
- token 等同于密码:`configuration.ini` 的权限建议设成只有运行 bot 的用户能读(第五步之后 `sudo chmod 600 /opt/botamusique/configuration.ini`)。
- 想播本地音乐文件的话,把文件放进 `/opt/botamusique/music_folder/` 即可。
- 长视频默认**不限时长**(`max_track_duration = 0`),超过 5 分钟的视频会边下边播。以前按旧说明在 `[bot]` 段加过 `max_track_duration = 180` 的,删掉那一行即可解除限制。
- 响度均衡(让大小声不一的歌音量趋于一致)默认已开启;如想关闭,在 `[bot]` 段加 `normalize_volume = False`。

---

## 五、第 4 步:手动测试

先在前台手动跑一次,确认能连上 Discord:

```bash
cd /opt/botamusique
venv/bin/python3 djbot.py --config configuration.ini
```

日志里出现 `logged in as ...` 和 `synced NN slash commands` 就说明连上了。然后:

1. 自己进服务器里的一个语音频道。
2. 在任意文字频道输入 `/help` —— bot 应回复命令列表(只有你看得到)。
3. 测试 `/bili video:<B站视频链接>` —— bot 会进入你所在的语音频道,应能听到声音。
4. 测试 `/play query:<歌名>` 或 `/spotify query:<Spotify链接>`。
5. 测试 `/queue`、`/skip`、`/volume percent:80` 等队列与播放控制。

确认正常后,在终端按 `Ctrl+C` 停止。如果有问题,见第九节「故障排查」。

---

## 六、第 5 步:设置开机自启(systemd)

让机器人作为系统服务后台常驻、崩溃自动重启、开机自启。

```bash
# 1. 创建一个专用的非特权用户来运行机器人
sudo useradd --system --home /opt/botamusique --shell /usr/sbin/nologin botamusique

# 2. 把整个目录的属主改成该用户
sudo chown -R botamusique:botamusique /opt/botamusique

# 3. 安装 service 文件并启动
sudo cp /opt/botamusique/deploy/botamusique.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now botamusique

# 4. 查看运行状态与实时日志
sudo systemctl status botamusique
sudo journalctl -u botamusique -f
```

> 之后如果还要再改 `configuration.ini`,因为文件属主已是 `botamusique`,需要用 `sudo nano /opt/botamusique/configuration.ini`,改完执行 `sudo systemctl restart botamusique` 重启生效。

---

## 七、第 6 步:启用 yt-dlp 每日自动更新

Bilibili / YouTube 经常改版,旧版 yt-dlp 会失效。这一步让系统每天自动把 `yt-dlp` 和 `spotdl` 升级到最新版并重启机器人。

```bash
sudo cp /opt/botamusique/deploy/botamusique-ytdlp-update.service /etc/systemd/system/
sudo cp /opt/botamusique/deploy/botamusique-ytdlp-update.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now botamusique-ytdlp-update.timer

# 确认定时器已生效、查看下次触发时间
sudo systemctl list-timers botamusique-ytdlp-update.timer
```

部署到此结束。机器人已在后台运行,并会每天自动更新。

---

## 八、命令速查(发给小队成员)

在服务器里输入 `/` 就能看到全部命令和参数说明(按每个人的 Discord 语言显示中文 / 日文 / 英文),
`/help` 列出全部命令。常用的:

| 命令 | 作用 |
|---|---|
| `/play <歌名 / 链接>` | 点歌;bot 不在语音里会先进你所在的频道。填数字则播放队列里的第几首 |
| `/bili <链接 / BV号>` | 播放 Bilibili 视频音频(`b23.tv` 短链、裸 BV/av 号都行;`BV1xx... p3` 是第 3 个分 P) |
| `/spotify <链接 / 关键词>` | Spotify 单曲 / 专辑 / 歌单,或按关键词搜索 |
| `/ysearch <关键词>` → `/pick <序号>` | 搜 YouTube 列出结果,再挑 |
| `/queue` / `/np` / `/skip` / `/remove <N>` / `/clear` | 队列 |
| `/volume <0-100>` / `/mode <模式>` | 音量 / 播放模式 |
| `/join` / `/leave` | 进入你所在的语音频道 / 停止并离开 |

## 九、故障排查

**机器人连不上 Discord / 日志报 `Improper token has been passed`**
- token 填错或已被重置:到 Developer Portal → Bot → Reset Token 重新生成,更新配置后重启。
- `journalctl -u botamusique -e` 看具体错误。

**输入 `/` 看不到 bot 的命令**
- 邀请 bot 时没勾 `applications.commands` scope:用 README 里的邀请链接重新邀请一次(不用先踢掉)。
- `guild_id` 填的不是这个服务器;日志里 `synced NN slash commands to <服务器名>` 会写同步到了哪。

**命令能用,但 bot 进不了语音频道 / 回复 "进不了你所在的语音频道"**
- bot 在那个频道没有「连接」「说话」权限。在频道设置 → 权限里给 bot 的身份组加上。
- 舞台频道不支持。

**机器人在频道里但没声音**
- 编辑配置,在 `[debug]` 段加 `ffmpeg = True` 和 `youtube_dl = True`,重启后看 `journalctl` 里的 ffmpeg / 下载日志。
- 报 `libopus` 相关错误:`sudo apt install --reinstall libopus0`。
- `scripts/smoke_test.py --only imports` 会检查 libopus、DAVE(davey)、PyNaCl 是否都装好了。

**`/bili` 报下载失败**
- 多半是 Bilibili 改版导致 yt-dlp 暂时失效。手动更新:`sudo /opt/botamusique/venv/bin/pip install --upgrade yt-dlp`,再 `sudo systemctl restart botamusique`(第六步的定时器平时会自动做这件事)。
- 大会员专享 / 番剧内容:需要 B 站登录 cookies。用浏览器扩展(如 "Get cookies.txt")导出 `bilibili.com` 的 Netscape 格式 cookies 文件,放到服务器上,在配置文件 `[youtube_dl]` 段加一行 `cookie_file = /opt/botamusique/bili_cookies.txt`。

**`/spotify` 失败**
- 提示「未配置」:检查 `[spotify]` 的 `client_id` / `client_secret` 是否填对。
- 提示「没找到匹配曲目」、或 spotdl 输出含 `require Deno`:spotdl 需要 Deno 来下载 YouTube 音频。`install.sh` 会自动装;手动补装:`apt install -y unzip && curl -fsSL https://deno.land/install.sh | DENO_INSTALL=/usr/local sh`。
- 仍失败且报 YouTube 要求登录验证:云服务器 IP 被 YouTube 风控,需给 yt-dlp 配置 cookies。

**`install.sh` 报 `bad interpreter` 或带 `\r` 的奇怪错误**
- 说明文件换行符被改成了 Windows 的 CRLF。修复:`sudo apt install -y dos2unix && dos2unix /opt/botamusique/deploy/*`。

---

## 十、后续维护

- **看日志**:`sudo journalctl -u botamusique -f`
- **重启 / 停止**:`sudo systemctl restart botamusique` / `sudo systemctl stop botamusique`
- **yt-dlp / spotdl 更新**:第六步的定时器每天自动做;也可手动触发 `sudo systemctl start botamusique-ytdlp-update.service`。
- **磁盘**:Spotify 下载缓存在 `/opt/botamusique/spotdl_cache/`,会按 `[spotify] max_cache_size`(默认 2048 MB)自动清理旧文件,一般无需手动管理。
- **升级**:`cd /opt/botamusique && sudo -u botamusique git pull && sudo systemctl restart botamusique`。
