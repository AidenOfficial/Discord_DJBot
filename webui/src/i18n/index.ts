// 轻量 i18n:不引第三方库。locale 是全局 ref,模板/computed 里调用 t() 时会自动
// 追踪它,切语言即时重渲染。en 是基准语言包,其他语言缺 key 时 TS 直接报错。
// en 打包在主包里;zh-CN / ja 按需加载,切语言时先等包到了再换(换之前一直显示旧语言)。
import { computed, ref, watch } from 'vue'
import { en, type Key, type Msg } from './en'
import { getItem, setItem } from '../storage'

export type Locale = 'en' | 'zh-CN' | 'ja'

export const LOCALES: { code: Locale; label: string }[] = [
  { code: 'en', label: 'English' },
  { code: 'zh-CN', label: '简体中文' },
  { code: 'ja', label: '日本語' },
]

type Pack = Record<Key, Msg>
const MESSAGES: Partial<Record<Locale, Pack>> = { en }
const LOADERS: Record<Exclude<Locale, 'en'>, () => Promise<Pack>> = {
  'zh-CN': () => import('./zh-CN').then((m) => m.zhCN),
  ja: () => import('./ja').then((m) => m.ja),
}
const STORAGE_KEY = 'lang'

const isLocale = (v: string | null): v is Locale => LOCALES.some((l) => l.code === v)

function detect(): Locale {
  const saved = getItem(STORAGE_KEY)
  if (isLocale(saved)) return saved
  for (const tag of navigator.languages ?? [navigator.language]) {
    const l = tag.toLowerCase()
    if (l.startsWith('zh')) return 'zh-CN'
    if (l.startsWith('ja')) return 'ja'
    if (l.startsWith('en')) return 'en'
  }
  return 'en'
}

/** The language on screen. Only changes once its pack is loaded. */
const active = ref<Locale>('en')

const pending = new Map<Locale, Promise<Pack>>()
function loadPack(l: Locale): Promise<Pack> {
  const have = MESSAGES[l]
  if (have) return Promise.resolve(have)
  let p = pending.get(l)
  if (!p) {
    p = LOADERS[l as Exclude<Locale, 'en'>]().then((pack) => {
      MESSAGES[l] = pack
      return pack
    })
    // 失败(离线、刚重新部署)就忘掉这次,下次再试
    p.catch(() => pending.delete(l))
    pending.set(l, p)
  }
  return p
}

let wanted: Locale = 'en'
/** Switch language: waits for the pack, then re-renders. A later call wins over an earlier one still loading. */
export async function setLocale(l: Locale): Promise<boolean> {
  wanted = l
  try {
    await loadPack(l)
  } catch {
    return false // 包没加载到:留在当前语言
  }
  if (wanted !== l) return false
  active.value = l
  return true
}

/**
 * Current language. Writable so `<select v-model="locale">` works: setting it starts
 * loading the pack and the value changes when the pack is there.
 */
export const locale = computed<Locale>({
  get: () => active.value,
  set: (l) => { void setLocale(l) },
})

/** Resolves when the first language is ready (falls back to English if its pack fails). Mount after it. */
export const ready: Promise<void> = setLocale(detect()).then(() => undefined)

watch(active, (l) => {
  document.documentElement.lang = l
  setItem(STORAGE_KEY, l)
})
document.documentElement.lang = active.value

type Params = Record<string, string | number>

const pluralRules = new Map<Locale, Intl.PluralRules>()
function pick(msg: Msg, n: unknown): string {
  if (typeof msg === 'string') return msg
  const l = active.value
  let rules = pluralRules.get(l)
  if (!rules) pluralRules.set(l, (rules = new Intl.PluralRules(l)))
  const cat = rules.select(Number(n) || 0)
  return cat === 'one' ? msg.one : msg.other
}

function raw(key: Key, params?: Params): string {
  const msg = MESSAGES[active.value]?.[key] ?? en[key]
  return pick(msg, params?.n)
}

/** 取文案;`{name}` 换成 params.name,复数形式按 params.n 选择 */
export function t(key: Key, params?: Params): string {
  const s = raw(key, params)
  return params ? s.replace(/\{(\w+)\}/g, (m, k) => (k in params ? String(params[k]) : m)) : s
}

/** 同 t(),但把插值和普通文字拆开返回,方便模板里把参数单独加粗(避免 v-html) */
export function tParts(key: Key, params: Params): { text: string; param: boolean }[] {
  return raw(key, params)
    .split(/(\{\w+\})/)
    .filter(Boolean)
    .map((seg) => {
      const m = /^\{(\w+)\}$/.exec(seg)
      return m && m[1]! in params ? { text: String(params[m[1]!]), param: true } : { text: seg, param: false }
    })
}

/** "5 分钟前" 这类相对时间,交给 Intl 按当前语言格式化 */
export function timeAgo(ts: number): string {
  if (!ts) return t('time.never')
  const s = Date.now() / 1000 - ts
  const rtf = new Intl.RelativeTimeFormat(active.value, { numeric: 'always', style: 'short' })
  if (s < 3600) return rtf.format(-Math.max(1, Math.round(s / 60)), 'minute')
  if (s < 86400) return rtf.format(-Math.round(s / 3600), 'hour')
  if (s < 86400 * 60) return rtf.format(-Math.round(s / 86400), 'day')
  return rtf.format(-Math.round(s / 86400 / 30), 'month')
}

/** 播放模式 / 来源类型这些后端枚举值的显示名 */
const MODE_KEYS: Record<string, Key> = {
  'one-shot': 'mode.oneShot', repeat: 'mode.repeat', single: 'mode.single', random: 'mode.random', autoplay: 'mode.autoplay',
}
export const modeLabel = (m: string) => (MODE_KEYS[m] ? t(MODE_KEYS[m]!) : m)

const TYPE_KEYS: Record<string, Key> = {
  url: 'type.url', file: 'type.file', radio: 'type.radio', playlist: 'type.playlist', livestream: 'type.livestream',
}
export const typeLabel = (type: string) => (TYPE_KEYS[type] ? t(TYPE_KEYS[type]!) : type || t('type.other'))
