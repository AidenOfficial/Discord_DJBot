# Web UI 发布指引(NAS + Cloudflare Tunnel/Access)

> 本文档只描述接入步骤,**不代表已执行部署**。所有命令在 NAS 上手动执行。

## 架构

```
浏览器 ──HTTPS──> Cloudflare edge ──Tunnel──> cloudflared(NAS)──HTTP──> bot:8181
                       │
                 Cloudflare Access(登录鉴权在这一层)
```

- 应用层不做登录:`[webinterface] auth_method = none` 保持现状,鉴权完全交给
  Cloudflare Access。**因此绝不能把 8181 端口直接暴露公网**——只有 cloudflared
  出站隧道能访问它。
- Web UI 在 `/`,JSON API 在 `/api/*`。所有接口走同一套 `requires_auth` 约定,
  auth_method 换成 password/token 时 UI 无需改动。

## 配置项(configuration.ini)

```ini
[webinterface]
enabled = True
listening_addr = 127.0.0.1   ; 容器内用 0.0.0.0,由 compose 网络隔离
listening_port = 8181
is_web_proxified = True      ; 让 Flask 信任 X-Real-IP(经由 ReverseProxied)
```

## docker compose(已内置,tunnel profile)

cloudflared 服务**已经写在仓库根目录的 `docker-compose.yml` 里**,挂在
`tunnel` profile 下,平时不启动。启用步骤:

```bash
cd <部署目录>
echo 'CLOUDFLARE_TUNNEL_TOKEN=eyJh...' > .env    # token 来自 Cloudflare 控制台
docker compose --profile tunnel up -d            # bot + cloudflared 一起拉起
docker compose logs -f cloudflared               # 看到 "Registered tunnel connection" 即通
```

- 不加 `--profile tunnel` 时行为与从前完全一致(只起 bot)。
- 不要给 bot 服务开 `ports`:两个容器在同一 compose 默认网络里,
  cloudflared 用服务名直接回源,8181 不暴露给宿主机/公网。
- `.env` 已被 gitignore,token 不会入库。

## Cloudflare 侧步骤(Zero Trust 控制台)

1. **Tunnel**:Networks → Tunnels → Create tunnel(Cloudflared 类型),
   复制 token 写进 `.env`;Public hostname 的回源 Service 填
   `http://botamusique:8181`(compose 服务名)。
2. **Access 应用**:Access → Applications → Self-hosted,域名同上;
   策略按邮箱/组放行;Session 时长按需(如 24h)。
3. (可选)Access → Service Auth 为自动化脚本发 Service Token。

## 用户身份、别名与个人歌单

Cloudflare Access 回源时会带上登录者邮箱(`Cf-Access-Authenticated-User-Email`),
Web UI 据此识别"是谁":

- 右上角头像 → 设置**别名**(显示名)。在 Web 上点的歌,队列、公告和统计页都显示别名;
  不设则用邮箱 @ 前面的部分。别名全站唯一(不分大小写),不能含 `< > & "`。
- **我喜欢的音乐**:正在播放、队列、搜索、曲库、歌单里每首歌旁的心形按钮一键收藏 / 取消,
  收进名为 `Favorites` 的歌单(和 Discord 里的 `/fav` 是同一张,没有就自动建),歌单页置顶显示。
- **Playlists** 页:每个人自己的歌单。任意页面歌曲旁的"加入歌单"按钮可加入任意歌单,也可以
  把当前整个队列存成歌单;歌单可"立即播放 / 随机 / 追加到队列 / 单曲插播"。
  整张歌单入队后(网页播放、`/mylist`、`/playlist <链接>`),队列里折叠成一行歌单,
  显示正在播第几首;点开才列出歌曲(大歌单一次只渲染 100 首),也可以整组移出队列。
  还没读到信息的链接先用歌单里存的标题占位,不再显示成一串 https://…
- **公开 / 私人**:歌单默认私人。歌单标题下的"私人 / 公开"按钮切换。公开的歌单
  出现在其他人歌单页左栏的"大家的歌单"里(显示主人的别名,不显示邮箱;空歌单不列出)。
  别人看到的是只读视图:可以立即播放 / 随机 / 全部加入队列、单曲插播,单曲收藏或收进
  自己的歌单,或"复制到我的歌单"整份复制(副本默认私人,之后与原歌单互不影响)。
  改回私人后立刻从别人那里消失。
- 没有经过 Access(例如局域网直连 8181)时是"Guest":能点歌,没有自己的歌单,
  但能浏览和播放大家公开的歌单。

**可选加固:校验 Access JWT。** 只读请求头的前提是 8181 不对外暴露(只能经 Tunnel 访问)。
想彻底防伪造,在 `configuration.ini` 加:

```ini
[webinterface]
access_team_domain = <你的团队名>.cloudflareaccess.com
access_aud = <Access 应用 Overview 页的 Application Audience (AUD) Tag>
```

开启后每个请求都校验 `Cf-Access-Jwt-Assertion`,没有合法 JWT 的一律 403
(局域网直连也会被拒,这是预期行为)。

## 用 Discord 登录(可选)

不想依赖 Cloudflare Access 识别身份时,可以让用户用 Discord 账号登录:

1. Developer Portal → 你的应用 → **OAuth2** → Redirects 加上
   `<public_url>/auth/discord/callback`,必须和下面的 `public_url` 拼出来的完全一致。
2. `configuration.ini`:

   ```ini
   [webinterface]
   auth_method = discord          ; 当门禁用;保持 none/token 时则是可选登录方式
   discord_client_id = <Client ID>
   public_url = https://music.example.com
   ```

   Client Secret 放进 `.env` 的 `DISCORD_CLIENT_SECRET`(优先于 ini 里的
   `discord_client_secret`),**不要提交进仓库**。
3. 路由:`/auth/discord/login` → Discord 授权 → `/auth/discord/callback`;
   `/auth/logout` 退出(GET 显示页面,POST 返回 JSON)。

- `auth_method = discord`:没登录的网页跳去登录,`/api/*` 返回 401 JSON;
  只放行和 bot 在同一个服务器里的账号,其他人 403。
- `auth_method = token`:令牌页多一个"用 Discord 登录"按钮,同服务器的账号可以代替令牌。
- 身份:用 `/bind` 绑定过的 Discord 账号登录后就是绑定的那个 Web 身份(歌单、收藏都在);
  没绑定过的身份是 `discord:<用户 ID>`,并自动记一条绑定,不需要再 `/bind`。
  用 Discord 登录后,身份优先于 Access 邮箱头(JWT 校验仍然照常要求)。
- 会话 Cookie 由 `flask_secret` 签名;不配置时随机生成一次存进 settings 库,重启不掉登录。

## 不用 Access 直接上公网(用 Discord 登录)

整站不套 Cloudflare Access、让用户在应用里用 Discord 登录时,Tunnel 后面就是公网,下面这些要确认:

- `auth_method = discord`(见上一节)。`none` 等于谁都能控制 bot。
- **不要信任 Access 的邮箱头**:没有 Access 时,请求头 `Cf-Access-Authenticated-User-Email` 是访问者
  自己可以随便写的,令牌 / 密码登录时会被当成身份。把它关掉:

  ```ini
  [webinterface]
  access_email_header =
  ```

  (`auth_method = discord` 时 Discord 身份优先,这个头不起作用,但关掉更稳妥。)
- 内置的防护(默认开着,一般不用改):
  - **安全响应头**:CSP 只允许本站脚本;`frame-ancestors` 只允许本站和 Discord
    (`[webinterface] frame_ancestors`,Activity 要嵌在 discord.com 里),别的网站嵌不进来(点击劫持);
    `X-Content-Type-Options: nosniff`、`Referrer-Policy: no-referrer`。
  - **限流**(`[webinterface] rate_limit`):搜索、点歌入队、歌单导入、Discord 登录、令牌校验
    按登录身份和选中的服务器计数,没有身份才按 IP。Activity 的请求都从 Discord 代理的 IP 来,
    只按 IP 会把所有人一起限住。超限返回 429(带 `Retry-After`)。
  - **输错令牌 / 密码**:同一 IP 超过 `max_attempts` 次后 `ban_minutes`(默认 15)分钟内不能再试;
    已经登录的会话、用 Discord 登录的人不受影响。令牌现在是 22 个字符(以前 7 个)。
  - **不让 bot 访问内网**:用户给的链接、跳转、DNS 重绑定都到不了局域网和 NAS 本身。
    bot 进程里由 `[bot] block_private_network` 拦,容器里的 ffmpeg 等子进程由
    `BAM_EGRESS_FILTER` 拦(见 `deploy/DOCKER.md`「禁止访问内网」)。
  - Web 服务用 waitress(生产 WSGI 服务器),不再是 Flask 的开发服务器。
- 管理接口(日志、缓存)想再加一层,看下一节。

## 管理接口再套一层 Cloudflare Access(按路径)

普通入口只用 Discord 登录,**只给管理路径**套 Access:Cloudflare 在边缘先要求 Access 登录,
通过后请求才到 bot,bot 照常再检查是不是 bot 主人(`[bot] admin` 里的 Discord ID)。
两层都过才能用,Access 这层不改变应用里的身份(身份仍然是 Discord 登录的账号)。

管理路径(都只有 bot 主人 / `log_viewers` 能用):

| 路径 | 内容 |
|---|---|
| `/api/logs`(含 `/api/logs/debug`、`/api/logs/download`) | 日志面板、调试日志开关、导出 |
| `/api/cache` | 下载缓存:固定、删除、清理 |

**例外**:`/api/logs/client` 是**所有人**的浏览器上报前端 JS 报错用的,不能被 Access 拦住。

Zero Trust 控制台 → Access → Applications:

1. **Add an application → Self-hosted**,名字如 `DJBot admin`。
   - Public hostname:`music.example.com`,Path:`api/logs`;
     再 **Add public hostname** 一条同域名、Path `api/cache`。
     (Access 的路径匹配它本身和下面的所有路径。)
   - Policy:Action **Allow**,Include → Emails → 主人的邮箱(或 Emails ending in / GitHub 组织等)。
   - Session duration 按需(如 24h)。
2. **再建一个 Self-hosted 应用**,名字如 `DJBot client logs`:
   - Public hostname:`music.example.com`,Path:`api/logs/client`;
   - Policy:Action **Bypass**,Include → **Everyone**。
   Access 按最具体的路径生效,所以这条覆盖上一条里的 `/api/logs`。
3. **不要**给整站(`music.example.com` 不带路径)建 Access 应用,否则普通用户也会被拦。
4. **不要**在 `configuration.ini` 里填 `access_aud` / `access_team_domain`:那会要求**每个**请求都带
   Access JWT,没套 Access 的普通路径全部 403。这里 Access 只做边缘的门,应用不用读它。

使用:主人先在浏览器里直接打开一次 `https://music.example.com/api/logs`,完成 Access 登录
(`CF_Authorization` cookie 是整个域名的),之后 Web UI 设置页里的日志、缓存页就能正常用。
其他人打开日志 / 缓存接口会被 Access 拦在 Cloudflare,请求到不了 NAS。

验证:

- [ ] 无痕窗口打开 `https://music.example.com/api/logs` → 跳到 Access 登录页。
- [ ] 无痕窗口打开首页 → 是 Discord 登录,不是 Access。
- [ ] `curl -X POST https://music.example.com/api/logs/client -d '{}' -H 'Content-Type: application/json'`
      返回的是 bot 的 401 / 400 JSON,不是 Access 的跳转。

**为什么不用单独的管理主机名**(比如 `admin.music.example.com` 整站套 Access):Discord 登录的回调地址
只有一个(`public_url`),登录后会话 cookie 落在主域名上,管理主机名上没有登录状态,
`auth_method = discord` 时那边打不开。要用管理主机名得先让 Discord 登录支持多个回调地址(还没做)。
如果只是不想让管理接口暴露在公网,也可以在 Cloudflare 用 WAF 自定义规则直接拦掉
`/api/logs`、`/api/cache`(放过 `/api/logs/client`),只在局域网里管理。

## Discord Activity(在 Discord 里打开控制面板,可选)

在语音频道里点 **Activities(火箭图标)** 就能打开 bot 的控制面板:队列、搜索、播放控制,
和网页版是同一个界面。声音照旧由 bot 推进语音频道,Activity 只是遥控器;面板固定操作
**打开它的那个服务器**,不显示服务器切换。

下文的 `<PUBLIC_HOST>` 是以后对外的 HTTPS 主机名(例如 `music.example.com`,还没定)。

### 工作方式

1. Discord 在 iframe 里打开 `https://<应用 ID>.discordsays.com/?frame_id=…&instance_id=…`,
   经 Discord 的代理转到 `https://<PUBLIC_HOST>/`。带着这两个启动参数时,首页和打包的静态资源
   不需要登录(里面没有数据)。
2. 前端用 Embedded App SDK 的 `authorize()` 拿到 code(scope `identify guilds`),
   `POST /api/activity/token {code, guild_id, channel_id}`。
3. 服务端用 Client Secret 换 Discord access token,读 `/users/@me` 和 `/users/@me/guilds`,然后
   **不信 SDK 给的上下文**,逐项核对:bot 在这个服务器;用户是成员(OAuth 服务器列表,或 bot 查成员);
   按 bot 网关的语音状态,用户此刻就在这个语音频道里。都对了才签发我们自己的短期令牌
   (`activity_token_ttl` 秒,默认 15 分钟,用 `flask_secret` 签名,可撤销)。
4. 前端调 SDK 的 `authenticate()`,之后所有 API 请求带 `Authorization: Bearer <令牌>`。
   令牌只在内存里,不写 localStorage,不用 Cookie。快到期时 `POST /api/activity/refresh`
   换新令牌(会再核对一次语音频道,人已经离开就不续);关闭时 `POST /api/activity/logout` 作废。
5. 权限和用 Discord 登录网页版一样(`web_context` 的规则:bot 主人、管理服务器权限……),
   打开 Activity 的服务器是默认服务器。`auth_method` 是什么都不影响 Activity。
6. 外部图片(搜索结果封面、头像)经 `/api/thumbnail/external` 转发(只代理 YouTube / Bilibili /
   Discord CDN 等图床),所以 **不需要** 给图床另外登记 URL Mapping,也用不着 `patchUrlMappings`。

### Developer Portal 配置(应用 ID `1568438278825181214`)

1. **Activities → Settings**:打开 **Enable Activities**。Discord 会自动建一条入口命令
   (Entry Point,`PRIMARY_ENTRY_POINT`,默认叫 `Launch`)。Supported Platforms 勾上
   Web / Desktop / iOS / Android;手机的方向锁定选 Unlocked(竖屏横屏都适配了)。
2. **Activities → URL Mappings**:Root Mapping 设成 `/` → `<PUBLIC_HOST>`(只填主机名,
   不带 `https://`、不带路径)。不需要别的映射。
3. **OAuth2**:
   - 记下 Client ID 和 Client Secret(和"用 Discord 登录"是同一对)。
   - Redirects 至少要有一条(SDK 授权本身不用跳转):已经配了 `<public_url>/auth/discord/callback`
     就够了,没有的话加一条 `https://127.0.0.1` 当占位。
   - scope 不用在 Portal 里设:前端请求 `identify` 和 `guilds`,用户第一次打开时 Discord 弹窗确认。
4. **入口命令**:Portal 里自动建的那条可以改名字和描述。bot 同步全局斜杠命令时会读出现有的入口命令
   原样一起提交(Discord 的全局同步是整体覆盖,不带上会被拒:错误码 50240);如果 Discord 上一条都没有、
   而 `activity_enabled = True`,bot 会登记一条 `/launch`(由 Discord 直接打开 Activity)。
5. **Installation**:保持 Guild Install(bot 本来就要装进服务器)。

### bot 配置

```ini
[webinterface]
activity_enabled = True
activity_token_ttl = 900
discord_client_id = 1568438278825181214
public_url = https://<PUBLIC_HOST>
; Client Secret 放 .env 的 DISCORD_CLIENT_SECRET
```

改完重启 bot:日志里会看到全局斜杠命令重新同步一次(开关 Activity 也算命令变了)。

### 网络 / 安全响应头

- `<PUBLIC_HOST>` 要能从公网直接访问:Discord 的代理在它自己的服务器上取页面,
  **不能挡在 Cloudflare Access 的交互登录后面**(Tunnel 本身没问题)。
- 响应头(加固那边负责):CSP 的 `frame-ancestors` 要放行 `https://discord.com`、
  `https://*.discord.com`、`https://*.discordsays.com`;`img-src` 要允许 `blob:`(Activity 里的图片
  是带令牌取回来再用 blob URL 显示的);`connect-src 'self'` 就够。不能发 `X-Frame-Options: DENY`。

### 上线前检查清单

- [ ] 公网域名定了,`<PUBLIC_HOST>` 已替换进 URL Mapping 和 `public_url`,`https://<PUBLIC_HOST>/api/activity/config` 返回 `enabled: true`。
- [ ] Portal 里 Activities 已开启,入口命令存在;bot 重启后日志显示全局命令同步成功,入口命令还在(客户端的 App Launcher 里能看到)。
- [ ] Client Secret 只在 `.env`,没进 git;`flask_secret` 不是默认值(令牌用它签名,换了就全部失效)。
- [ ] 桌面客户端:进语音频道 → 火箭图标 → 打开 → 第一次弹授权 → 看到当前服务器的队列,能播放 / 暂停 / 跳过 / 搜索点歌,声音从 bot 出来。
- [ ] 手机客户端(竖屏):布局不溢出,刘海和底部手势条不挡按钮;缩成画中画时只剩迷你播放条。
- [ ] 不在语音频道的人打开(或从别的频道转发的邀请)被拒,提示"先进入语音频道"。
- [ ] 离开语音频道后,最多一个 `activity_token_ttl` 内面板提示需要重新打开。
- [ ] 搜索结果封面、队列封面在 Activity 里都显示(外部图片走代理)。
- [ ] 浏览器开发者工具里没有 CSP / frame-ancestors 报错。
- [ ] 应用要对外公开前:按 Discord 的要求完成应用验证(未验证的应用,Activity 的可用范围有限制)。

## 语音频道与跟随(Settings 页)

- 实时显示服务器的语音频道(按分类分组,和 Discord 里的顺序一致)和每个频道里的人
  (bot 自己高亮,其他 bot 置灰并带机器人图标)。
- **☆ Default**:设为默认频道,bot 启动时进这里;优先于 `[discord] channel`。
  **不设默认频道**则启动时不进任何频道,等有人 `/play` 或 `/join`。
- **Move here**:让 bot 立刻过去。**离开语音**:暂停并退出语音频道。
- 只有 bot 有「查看频道 / 连接 / 说话」权限的语音频道才能进;没权限的显示锁标记。
  舞台频道不支持;服务器的 AFK 频道标为 AFK,跟随模式不会进去。
- 跟随模式:
  - *Stay put*:不动(默认)。
  - *Follow the crowd*:bot 所在频道没人了(其他 bot、`when_nobody_in_channel_ignore` 里的不算),
    就去最后离开的那个人去的频道;那人下线了就去人最多的频道。
  - *Follow someone*:始终跟着指定的人;对方离线或进了 AFK 频道时按 *Follow the crowd* 处理。
  - 可选"服务器上一个人都没有时回默认频道"。
  - bot 不在语音频道里(还没人叫过、被 `/leave` 了)时,跟随模式不会自己进频道。
- 有人换频道后等 2.5 秒再决定,来回切频道不会把 bot 带着乱跑。
- 开着跟随时,`when_nobody_in_channel = pause/stop` 不会在 bot 即将跟过去时误暂停/清空队列。
- 有人把 bot 从语音里断开(右键 → 断开连接)时,bot 会暂停播放。

## 没人时自动暂停(Settings 页)

- bot 所在频道连续没人(其他 bot 不算)达到设定分钟数就暂停,默认 5 分钟,0 = 关闭。
- 默认有人回到频道就自动继续;只恢复它自己暂停的,不会替人恢复手动暂停。
- 开着跟随模式时优先跟过去,不会暂停。
- 与 ini 里的 `when_nobody_in_channel`(立即暂停/停止)相互独立,一般保持那个为 `nothing` 即可。

## 长视频开播与等待进度

- 点歌后 Now Playing 显示准备面板:当前阶段(读取视频信息 → 连接 → 缓冲 → 播放)、
  已等待时间、预计还要几秒开播、下载速度。读取信息阶段没有速度数据,按最近几次的耗时估算。
- 开播后如果还在后台下载,进度条上浅色部分是已下载的位置,下方显示下载进度和剩余时间;
  队列里正在预下载的歌显示下载百分比。
- Discord 里只有在大家真的在等(当前曲还没出声)超过 6 秒时才播报一次在等什么、还要多久;
  后台预下载、已经边下边播的都不再刷屏。
- 实测(B 站 50 分钟视频,2026-10-08):点歌到出声 9.7 秒 → 5.6–6.0 秒。剩下的主要是
  yt-dlp 读取视频信息(B 站约 4.5 秒,会请求网页/合集/签名/格式/章节好几个接口)。
  放过的歌在缓存里,秒开;排在后面的歌在前一首播放时已经预下载好。

## 跳过非音乐片段(SponsorBlock)

- YouTube / B 站视频播放时自动跳过社区标注的片段:MV 片头片尾的说话、赞助口播、求三连等。
- Now Playing 的进度条上用斜纹标出会被跳过的位置。
- 配置见 `configuration.example.ini` 的 `sponsorblock` / `sponsorblock_categories`。
- B 站多 P 视频的片段对应不到具体是哪一 P,这种情况不跳。

## 导入歌单(Playlists 页 → Import a playlist)

- 支持 YouTube 播放列表、网易云音乐 / QQ 音乐歌单、Spotify 歌单/专辑,可以导入成新歌单或追加到当前歌单。
  QQ 音乐的分享链接(i2.y.qq.com/...playlist.html?id=)、网页版链接和 c6.y.qq.com 短链都可以。
- 网易云 / QQ 音乐在海外基本没有音源,Spotify 本身不提供音频,所以这几个只读歌名/歌手/时长,
  再去 YouTube 按"时长接近 + 官方频道优先 + 排除翻唱/现场/AMV"挑最像的一个。
  找不到的会列出来。导入几百首大约要一两分钟,页面上有进度。
- Spotify 歌单 100 首以内不需要任何凭据(读公开嵌入页);超过 100 首时,配置了
  `[spotify] client_id / client_secret`(和 `/spotify` 命令同一套)才能读完整列表,否则只导入前 100 首。
- 实测(2026-10-08):网易云 262/265、Spotify 78/79、YouTube 9/9、QQ 音乐 270/398;
  每 100 首匹配约 30–40 秒。QQ 那个歌单以抖音/独立音乐人的中文歌和片段版为主,
  很多在 YouTube 上本来就没有,没匹配上的会列出来。
- 简体歌单会同时用简体和繁体搜索、比较时统一转简体(YouTube 上中文歌多为繁体标题)。

## 绑定 Discord 账号

- 网页右上角头像 → **绑定 Discord 账号**,生成 6 位绑定码(10 分钟有效),
  在服务器里输入 `/bind code:123456`(回复只有你自己看得到)。
- 绑定后在 Discord 里:
  - `/mylist`:列出我的歌单;
  - `/mylist playlist:<名字或序号> [shuffle:True]`:把歌单加入播放队列(歌单名可以自动补全);
  - `/fav [playlist]`:把当前这首加入歌单(默认 Favorites,没有就自动建);
  - `/unbind`:解除绑定。
- 还没设别名的话,绑定时自动用 Discord 显示名当别名;统计页会把同一个人在 Discord 和网页上的点歌合并成一行。
- 按 Discord 用户 ID 识别,改昵称不影响绑定。
- 绑定码输错 5 次锁 10 分钟。

## 缓存与上传

- **Cache** 页:下载缓存占用、每首的大小/播放次数/最后使用时间。📌 固定 = 自动清理永不删除;
  💾 = 复制进本地曲库(`music_folder/saved/`);超过 `tmp_folder_max_size`(默认 4GB)时
  按"最久没用"淘汰,播放 ≥3 次的歌最后才淘汰。
- **上传**(Library 页 Upload):分片上传(每片 32MB),不受 Cloudflare 单请求 100MB 限制,
  断网会自动续传;单文件上限 `max_upload_file_size`(默认 4G)。视频默认只保留音轨
  (`upload_extract_audio`),上传完直接进曲库,不用 rescan。

## 界面语言(i18n)

右上角下拉可切换 English / 简体中文 / 日本語,选择存在浏览器 localStorage(`lang`)。
没选过时按浏览器语言自动匹配(zh-* → 简体中文,ja-* → 日本語,其余 English)。
只影响 Web UI;bot 在 Discord 里的回复由 `[bot] language` 决定。斜杠命令的说明则按每个人自己的 Discord 语言显示(英文 / 简体中文 / 日文)。

文案在 `webui/src/i18n/`:`en.ts` 是基准,`zh-CN.ts`、`ja.ts` 必须有同样的 key
(缺 key 时 `npm run build` 的类型检查直接报错)。加新语言:复制一份语言包,在
`i18n/index.ts` 的 `LOCALES` / `MESSAGES` / `detect()` 里登记即可。

## 日志(Settings 页 → 日志)

遇到 bug 时不用再翻 `docker compose logs`:

- 实时滚动显示 bot 日志,可按级别(全部 / 信息 / 警告 / 错误)筛选、搜索;
  带异常的行点开看完整调用栈。第三方库(discord.py、Flask 路由异常)的警告和错误也会收进来。
- **跨重启保留**:日志同时写进 settings 库旁边的 `logs/bot-log.jsonl`(Docker 里是
  `data/logs/`,2MB 滚动、保留 3 份)。bot 崩溃 / 被 watchdog 杀掉重启后,面板里
  "bot 已重启"分隔线上方就是崩溃前的日志。
- **调试日志**开关:临时把日志级别调到 DEBUG,30 分钟后自动关;复现 bug 时打开。
- 浏览器里的前端 JS 报错也会上报,记为 `bot.webui`(同一条 10 秒内只报一次,全局每分钟最多 30 条)。
- **下载**:导出为文本文件,开头带版本、Python / yt-dlp 版本、播放状态,直接贴给别人(或 Claude)排查。
- 谁能看:`[webinterface] log_viewers` 留空 = 所有能打开 Web UI 的人;填逗号分隔的
  Access 邮箱就只有这些人能看(其他人看不到"日志"标签)。日志里会有其他用户的别名 /
  邮箱和点歌记录,朋友圈子以外的人能访问时建议填上。

## 验证清单(部署后手动)

- [ ] 域名打开即 Web UI,未登录时被 Access 拦截。
- [ ] 直连 NAS IP:8181 从公网不可达(仅 Tunnel 出站)。
- [ ] `/api/status` 轮询正常、控件/队列/搜索/统计各页可用。
- [ ] 上传大小上限 `max_upload_file_size` 符合预期;上传一个 >100MB 的视频能成功并只剩音轨。
- [ ] 右上角显示的是自己的 Access 邮箱;设置别名后点一首歌,队列里显示别名。
- [ ] bot 不在语音频道时,Now Playing 顶部有提示;Settings 里能让 bot 进出频道。
- [ ] 开了 Discord Activity 的话:按上面"Discord Activity → 上线前检查清单"逐项过一遍。
