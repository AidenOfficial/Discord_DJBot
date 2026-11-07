// Discord Activity 模式:页面在 Discord 的 iframe 里(Embedded App SDK)。
//
// 登录:SDK authorize() → POST /api/activity/token(服务端换令牌并核对服务器 / 语音频道)
// → SDK authenticate()。拿到的是我们自己的短期令牌:只放在这个模块的变量里,
// 不写 localStorage / sessionStorage,也不用 Cookie(iframe 里第三方 Cookie 不可靠)。
// api.ts 的 apiFetch 给每个请求加 Authorization: Bearer;令牌快到期前后台续期,
// 续不了(离开了语音频道)就提示重新打开。
//
// 服务器固定是打开 Activity 的那个(SDK 给的,服务端核对过),不显示服务器切换。
import { reactive } from 'vue'
import { selectedGuild } from './guild'

const BASE = '..'

/** Discord 打开 Activity 时 iframe 地址里一定带这两个参数 */
function detectEmbedded(): boolean {
  try {
    const q = new URLSearchParams(location.search)
    return !!(q.get('frame_id') && q.get('instance_id'))
  } catch {
    return false
  }
}

export const embedded = detectEmbedded()

export type ActivityPhase = 'idle' | 'connecting' | 'ready' | 'error'

export const activity = reactive({
  phase: 'idle' as ActivityPhase,
  /** 服务端的错误码(not_in_voice_channel、not_a_member……)或 sdk / network */
  error: '',
  guildId: '',
  channelId: '',
})

let token = ''
let expiresAt = 0
let refreshTimer: ReturnType<typeof setTimeout> | undefined
let pending: Promise<boolean> | null = null
// SDK 只在 Activity 模式下加载(单独的 chunk,普通网页不下载)
let sdk: import('@discord/embedded-app-sdk').DiscordSDK | null = null
let clientId = ''
// 和服务端 web_activity.ACTIVITY_SCOPES 一致
const SCOPES: ('identify' | 'guilds')[] = ['identify', 'guilds']

/** 当前的 Bearer 令牌;不是 Activity 模式 / 还没登录是 '' */
export function activityToken(): string {
  return embedded ? token : ''
}

class ActivityError extends Error {}

async function readError(rv: Response): Promise<string> {
  const body = await rv.json().catch(() => ({}))
  return typeof body?.error === 'string' ? body.error : `http_${rv.status}`
}

function accept(data: { token: string; expires_in: number; guild_id: string; channel_id: string }) {
  token = data.token
  expiresAt = Date.now() + data.expires_in * 1000
  activity.guildId = data.guild_id
  activity.channelId = data.channel_id
  selectedGuild.value = data.guild_id
  clearTimeout(refreshTimer)
  // 剩下四分之一时续期,最少提前 30 秒
  const lead = Math.max(30_000, data.expires_in * 250)
  refreshTimer = setTimeout(() => { void refresh() }, Math.max(5_000, expiresAt - Date.now() - lead))
}

async function login(): Promise<void> {
  if (!sdk) {
    const cfg = await fetch(`${BASE}/api/activity/config`, { headers: { Accept: 'application/json' } })
    if (!cfg.ok) throw new ActivityError(`http_${cfg.status}`)
    const data = await cfg.json()
    if (!data.enabled) throw new ActivityError('activity_disabled')
    clientId = data.client_id
    const { DiscordSDK } = await import('@discord/embedded-app-sdk')
    sdk = new DiscordSDK(clientId)
    await sdk.ready()
  }
  if (!sdk.guildId || !sdk.channelId) throw new ActivityError('guild_required')
  let code: string
  try {
    ({ code } = await sdk.commands.authorize({
      client_id: clientId,
      response_type: 'code',
      prompt: 'none',
      scope: SCOPES,
    }))
  } catch {
    throw new ActivityError('authorize_cancelled')
  }
  const rv = await fetch(`${BASE}/api/activity/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ code, guild_id: sdk.guildId, channel_id: sdk.channelId }),
  })
  if (!rv.ok) throw new ActivityError(await readError(rv))
  const data = await rv.json()
  await sdk.commands.authenticate({ access_token: data.access_token })
  accept(data)
}

async function refresh(): Promise<boolean> {
  if (!token) return renew()
  try {
    const rv = await fetch(`${BASE}/api/activity/refresh`, {
      method: 'POST',
      headers: { Accept: 'application/json', Authorization: `Bearer ${token}` },
    })
    if (rv.ok) {
      accept(await rv.json())
      return true
    }
    const error = await readError(rv)
    if (rv.status === 403) {
      // 不在语音频道里了:旧令牌服务端已经作废
      token = ''
      activity.phase = 'error'
      activity.error = error
      return false
    }
  } catch { /* 网络问题:走完整登录再试一次 */ }
  token = ''
  return renew()
}

/** 登录 / 令牌失效后重新登录。同时多处调用只跑一次。 */
export function renew(): Promise<boolean> {
  if (!embedded) return Promise.resolve(false)
  if (!pending) {
    if (activity.phase !== 'ready') activity.phase = 'connecting'
    pending = login()
      .then(() => {
        activity.phase = 'ready'
        activity.error = ''
        return true
      })
      .catch((e) => {
        token = ''
        activity.phase = 'error'
        activity.error = e instanceof ActivityError ? e.message : 'network'
        return false
      })
      .finally(() => { pending = null })
  }
  return pending
}

/** 关闭 / 离开时作废令牌(尽力而为) */
export function revokeOnExit() {
  if (!token) return
  void fetch(`${BASE}/api/activity/logout`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    keepalive: true,
  }).catch(() => {})
  token = ''
}

const EXTERNAL = /^https?:\/\//i

/** Activity 的 iframe 只能访问自己的域名:外部图片(搜索结果封面、头像、服务器图标)走 /api/thumbnail/external */
export function imageSrc(url: string | null | undefined): string {
  if (!url) return ''
  if (!embedded || !EXTERNAL.test(url)) return url
  return `${BASE}/api/thumbnail/external?url=${encodeURIComponent(url)}`
}
