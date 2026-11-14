<script setup lang="ts">
// Activity 里的"正在播放":平铺磁贴,按容器大小换版面(都是 CSS 容器查询,不判断设备):
//   宽而矮  → 横向全景:各组并排,磁贴边长由可用高度算出,横向滚动并吸附到组,露出下一组的一角
//   窄 / 高 → 4 列磁贴,竖向滚动
//   手机宽  → 控制磁贴只留图标,"接下来"变成大字列表
// 画中画(高度 <= 300px)由 App.vue 换成 ActivityMini。
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'
import { fetchQueue, postQueue, thumbnailUrl, type QueueAction, type QueueGroup, type QueueItem } from '../api'
import AuthImg from '../components/AuthImg.vue'
import AddToPlaylist from '../components/AddToPlaylist.vue'
import FavButton from '../components/FavButton.vue'
import LyricsPanel from '../components/LyricsPanel.vue'
import PrepPanel from '../components/PrepPanel.vue'
import { formatTime, useStatus } from '../composables/useStatus'
import { announce } from '../composables/useAnnounce'
import { usePolling } from '../composables/usePolling'
import { selectedGuild } from '../guild'
import { modeLabel, t, typeLabel } from '../i18n'
import MetroSeek from './MetroSeek.vue'
import { useSeek } from './seek'

const emit = defineEmits<{ go: [view: 'search' | 'queue'] }>()

const { status, error, syncedAt, control, applyStatus } = useStatus()
const { dragAt, canSeek, seek, showPrep } = useSeek()
const current = computed(() => status.value?.current ?? null)
const uid = useId()

// ---- 封面:只在换歌 / 换图源时换地址,轮询时 <img> 不闪 ----
const artSrc = ref<string | null>(null)
const artKind = ref('')
watch(
  () => [current.value?.id, current.value?.has_thumbnail, current.value?.artwork] as const,
  ([id, hasThumb, art]) => {
    artSrc.value = id && hasThumb ? thumbnailUrl(id, { version: art || 'pending' }) : null
    artKind.value = art || ''
  },
  { immediate: true },
)

// ---- 标题 ----
const titlePending = computed(() => !!status.value?.prep && /^https?:\/\//.test(current.value?.title ?? ''))
const displayTitle = computed(() => current.value?.track || current.value?.title || '')
const artistLine = computed(() => {
  const c = current.value
  if (!c) return ''
  const artist = c.artist && c.artist !== '??' ? c.artist : ''
  const album = c.album?.trim()
  const parts = [artist]
  // 单曲的专辑名常常就是歌名:重复时不显示
  if (album && album.toLowerCase() !== displayTitle.value.trim().toLowerCase()) parts.push(album)
  return parts.filter(Boolean).join(' · ')
})
// 长标题按长度缩小一档(CJK 字宽约是拉丁字母的两倍),换行而不是截成一行省略号
function lengthScale(text: string) {
  const n = [...text].length * (/[぀-ヿ㐀-鿿가-힯＀-￯]/.test(text) ? 1.8 : 1)
  return n <= 22 ? 1 : n <= 40 ? 0.8 : n <= 70 ? 0.66 : 0.56
}
const titleScale = computed(() => lengthScale(displayTitle.value))
const sourceLabel = computed(() => typeLabel(current.value?.type ?? ''))

// ---- 提示(NowPlaying 在 Activity 里不挂载,播报在这里做) ----
const notInVoice = computed(() => !!status.value && !status.value.voice_channel)
watch(notInVoice, (now) => {
  if (now) announce(t('np.notInVoice'))
})
watch(error, (e) => {
  if (e) announce(t('np.unreachable', { error: e }), { assertive: true })
})

// ---- 控制 ----
function togglePlay() {
  if (!status.value) return
  void control({ action: status.value.play ? 'pause' : 'resume' })
}

/** 队列里的上一首;单次播放模式下播过的歌已经删掉了,没有上一首 */
const prevIndex = computed(() => {
  const s = status.value
  if (!s || s.empty) return null
  if (s.current_index > 0) return s.current_index - 1
  if (s.mode === 'repeat' && s.queue_length > 1) return s.queue_length - 1
  return null
})
async function playPrevious() {
  if (prevIndex.value === null) return
  try {
    applyStatus(await postQueue({ action: 'play', index: prevIndex.value }))
  } catch { /* 下一次轮询会带回真实状态 */ }
}

const MODES = ['one-shot', 'repeat', 'single', 'random', 'autoplay']
const MODE_ICON: Record<string, string> = {
  'one-shot': 'arrow-right', repeat: 'repeat', single: 'rotate-right', random: 'shuffle', autoplay: 'infinity',
}
const mode = computed(() => status.value?.mode ?? 'one-shot')
async function cycleMode() {
  const next = MODES[(MODES.indexOf(mode.value) + 1) % MODES.length]!
  await control({ action: 'mode', mode: next })
  announce(t('ctl.modeNow', { mode: modeLabel(status.value?.mode ?? next) }))
}

// 音量:拖动时先不跟着轮询改,停手 150ms 再发送(和 Controls.vue 一样)
const volPct = ref(50)
let volDragging = false
let volTimer: ReturnType<typeof setTimeout> | undefined
watch(() => status.value?.volume, (v) => {
  if (v !== undefined && !volDragging) volPct.value = Math.round(v * 100)
}, { immediate: true })
function onVolumeInput() {
  volDragging = true
  clearTimeout(volTimer)
  volTimer = setTimeout(() => {
    void control({ action: 'volume', volume: volPct.value / 100 })
    volDragging = false
  }, 150)
}
onBeforeUnmount(() => clearTimeout(volTimer))

// ---- 歌词 ----
const hasLyrics = computed(() => {
  const s = current.value?.lyrics
  return !!s && s !== 'off'
})

// ---- 接下来 ----
const items = ref<QueueItem[]>([])
async function reloadQueue(background = false) {
  const guild = selectedGuild.value
  try {
    const q = await fetchQueue({ background })
    if (guild === selectedGuild.value) items.value = q.items
  } catch { /* 连接问题由状态轮询提示 */ }
}
// 两个源分开写:getter 返回新数组的话,每次状态轮询都会被当成"变了"
watch([selectedGuild, () => status.value?.version], () => reloadQueue(), { immediate: true })
usePolling(() => reloadQueue(true), () => (items.value.some((it) => it.download) ? 3000 : 10000)).start()

type UpRow =
  | { kind: 'item'; key: string; item: QueueItem; index: number }
  | { kind: 'group'; key: string; group: QueueGroup; first: number; count: number; duration: number; requester: string }

const UP_LIMIT = 24
const upStart = computed(() => {
  const i = status.value?.current_index ?? -1
  return current.value && i >= 0 ? i + 1 : 0
})
const upCount = computed(() => Math.max(0, items.value.length - upStart.value))
/** 当前曲之后的条目;连续的同一张歌单合成一块磁贴(和 QueueList 的分组一致) */
const upRows = computed<UpRow[]>(() => {
  const list = items.value
  const seen = new Map<string, number>()
  const keyOf = (it: QueueItem) => {
    const n = seen.get(it.id) ?? 0
    seen.set(it.id, n + 1)
    return `${it.id}#${n}`
  }
  for (let k = 0; k < upStart.value && k < list.length; k++) keyOf(list[k]!)
  const out: UpRow[] = []
  let i = upStart.value
  while (i < list.length && out.length < UP_LIMIT) {
    const it = list[i]!
    const gk = it.group?.key
    let j = i + 1
    if (gk) while (j < list.length && list[j]!.group?.key === gk) j++
    if (gk && j - i > 1) {
      let duration = 0
      for (let k = i; k < j; k++) duration += list[k]!.duration || 0
      out.push({ kind: 'group', key: `g-${keyOf(it)}`, group: it.group!, first: i, count: j - i, duration, requester: it.requester })
      for (let k = i + 1; k < j; k++) keyOf(list[k]!)
      i = j
    } else {
      out.push({ kind: 'item', key: keyOf(it), item: it, index: i })
      i++
    }
  }
  return out
})

const listEl = ref<HTMLElement | null>(null)
const manageBtn = ref<HTMLButtonElement | null>(null)
const busy = ref(false)
const named = (action: string, title: string) => t('common.itemAction', { action, title })

/** 队列操作;操作的磁贴消失(移除、立即播放)后把焦点交给同一位置的下一块磁贴 */
async function act(body: QueueAction, pos: number, title: string) {
  if (busy.value) return
  busy.value = true
  try {
    applyStatus(await postQueue(body))
    await reloadQueue()
    if (body.action === 'remove' || body.action === 'remove_group') announce(t('metro.removed', { title }))
  } catch {
    await reloadQueue()
  } finally {
    busy.value = false
  }
  await nextTick()
  const active = document.activeElement
  if (active && active !== document.body) return
  const tiles = listEl.value?.querySelectorAll<HTMLElement>('.q-item')
  const target = tiles?.length ? tiles[Math.min(pos, tiles.length - 1)]?.querySelector<HTMLElement>('.q-btn') : null
  ;(target ?? manageBtn.value)?.focus()
}

// ---- 全景:竖向滚轮横着滚 ----
// 桌面版 Discord 多数人用竖向滚轮;容器竖向已经到头、指针下面也没有能竖着滚的区域(歌词)时,
// 把滚轮换成横向滚动。scrollBy 是"按方向"的滚动,吸附会往滚动方向找组,不会被拉回原组。

// 滚轮 / 触控板驱动的全景滚动:一个带惯性的弹簧(临界阻尼,在范围内不来回晃)。
// - 段落式:鼠标滚轮一格推进到下一列磁贴(至少约 1/5 个可视宽度),连续几格就跨几段;
// - 惯性:快速连拨几格后停手、触控板松手,按当时的速度多滑出去一点,再落到最近的一列;
// - 触底回弹:到头还往外推,内容像橡皮筋一样被拉出去一点(越拉越吃力),然后弹回。
// 越界的那一段 scrollLeft 表达不了,用滚动层自己的 translate 画(平移内容会改变可滚动宽度,
// 右端回弹时浏览器会把 scrollLeft 钳回去;平移滚动层本身不会)。滑动期间关掉 scroll-snap,
// 否则每帧写入的位置都会被吸附拉走;触屏(原生滑动)不经过这里。减少动效:一格一段,直接跳。
const scroller = ref<HTMLElement | null>(null)
const reduceMotion = typeof matchMedia === 'function' ? matchMedia('(prefers-reduced-motion: reduce)') : null

/** 弹簧刚度(1/s²)和阻尼:阻尼 = 2√k 是临界阻尼,最快回到目标又不过冲 */
const SPRING_K = 150
const SPRING_W = Math.sqrt(SPRING_K)
const SPRING_C = 2 * SPRING_W
/** 鼠标滚轮一格至少推进可视宽度的这个比例 */
const STEP_MIN = 0.2
/** 停手多久算"停下"(之后才算惯性、落位) */
const IDLE_MS = 110
/** 触控板松手后按速度多滑的时间(秒):位移 = 速度 × 这个数 */
const FLING_S = 0.22
/** 到头还拨滚轮时给的向外速度(px/s),弹簧把它拉回来就是回弹 */
const BOUNCE_V = 2600
/** 触控板推过头时的阻力:越界部分只跟手这个比例 */
const EDGE_RESIST = 0.35

let phys = { x: 0, v: 0, target: 0 }
let physRaf = 0
let physLast = 0
let written = -1
let rubber = 0
let lastInputAt = 0
let pendingIdle = false
let continuous = false
const notches: number[] = []
const recent: { t: number, d: number }[] = []

function maxScroll(el: HTMLElement) {
  return Math.max(0, el.scrollWidth - el.clientWidth)
}
function clamp(n: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, n))
}
/** 越界距离 → 画出来的位移:越拉越吃力,最多约四分之一个可视宽度(iOS 的橡皮筋公式) */
function rubberBand(d: number, w: number) {
  const dim = w * 0.25
  return Math.sign(d) * (1 - 1 / (Math.abs(d) * 0.55 / dim + 1)) * dim
}

/** 落位点:每组的开头、每一列磁贴的开头、两头。扣掉 scroll-padding,和吸附对齐的位置一致 */
function segments(el: HTMLElement) {
  const max = maxScroll(el)
  const box = el.getBoundingClientRect()
  const pad = parseFloat(getComputedStyle(el).scrollPaddingInlineStart) || 0
  const base = el.scrollLeft
  const pts = [0, max]
  for (const n of el.querySelectorAll<HTMLElement>('.g, .now-grid > *, .q-list > *, .q-more > *')) {
    pts.push(clamp(Math.round(base + n.getBoundingClientRect().left - box.left - pad), 0, max))
  }
  pts.sort((a, b) => a - b)
  return pts.filter((p, i) => i === 0 || p - pts[i - 1] > 12)
}
function nearestSegment(el: HTMLElement, at: number) {
  let best = clamp(at, 0, maxScroll(el))
  let dist = Infinity
  for (const p of segments(el)) {
    if (Math.abs(p - at) < dist) { dist = Math.abs(p - at); best = p }
  }
  return best
}
/** 从 from 往 dir 方向走 count 段,每段至少 STEP_MIN 个可视宽度 */
function nextSegment(el: HTMLElement, from: number, dir: number, count: number) {
  const pts = segments(el)
  const min = el.clientWidth * STEP_MIN
  let at = from
  for (let i = 0; i < count; i++) {
    const next = dir > 0 ? pts.find((p) => p - at >= min) : [...pts].reverse().find((p) => at - p >= min)
    at = next ?? (dir > 0 ? pts[pts.length - 1] : 0)
  }
  return at
}

function render(el: HTMLElement) {
  const max = maxScroll(el)
  const inside = clamp(phys.x, 0, max)
  if (Math.abs(el.scrollLeft - inside) >= 0.5) el.scrollTo({ left: inside, behavior: 'instant' as ScrollBehavior })
  written = el.scrollLeft
  const over = phys.x - inside
  const shift = Math.abs(over) < 0.5 ? 0 : rubberBand(over, el.clientWidth)
  if (shift !== rubber) {
    rubber = shift
    el.style.translate = shift ? `${-shift}px 0` : ''
  }
}

function stopPhysics() {
  if (physRaf) cancelAnimationFrame(physRaf)
  physRaf = 0
  written = -1
  pendingIdle = false
  if (scroller.value) scroller.value.style.translate = ''
  rubber = 0
}

/** 停手了:算惯性,落到最近的一列;推过头的部分由弹簧拉回来(回弹) */
function onIdle(el: HTMLElement) {
  const max = maxScroll(el)
  const now = performance.now()
  let projected = phys.target
  if (continuous) {
    const span = recent.filter((r) => now - r.t < 120)
    const vel = span.length > 1 ? span.reduce((s, r) => s + r.d, 0) / Math.max(16, now - span[0].t) * 1000 : 0
    projected = clamp(phys.target, 0, max) + vel * FLING_S
  } else {
    const quick = notches.filter((t) => now - t < 320).length
    if (quick >= 3) {
      const dir = Math.sign(phys.target - phys.x) || Math.sign(phys.v)
      if (dir) projected = nextSegment(el, phys.target, dir, Math.min(2, quick - 2))
    }
  }
  phys.target = nearestSegment(el, clamp(projected, 0, max))
  notches.length = 0
  recent.length = 0
}

function tick(now: number) {
  const el = scroller.value
  if (!el) { stopPhysics(); return }
  // 期间有人拖了滚动条、按了方向键、用触屏滑了:让给他们
  if (written >= 0 && Math.abs(el.scrollLeft - written) > 2) { stopPhysics(); return }
  const dt = Math.min(physLast ? (now - physLast) / 1000 : 1 / 60, 0.05)
  physLast = now
  if (pendingIdle && now - lastInputAt >= IDLE_MS) { pendingIdle = false; onIdle(el) }
  // 半隐式欧拉,4ms 一小步,刚度再大也稳
  const steps = Math.ceil(dt / 0.004)
  const h = dt / steps
  for (let i = 0; i < steps; i++) {
    phys.v += (SPRING_K * (phys.target - phys.x) - SPRING_C * phys.v) * h
    phys.x += phys.v * h
  }
  const resting = !pendingIdle && Math.abs(phys.target - phys.x) < 0.4 && Math.abs(phys.v) < 6
  if (resting) phys.x = phys.target
  render(el)
  if (resting) { stopPhysics(); return }
  physRaf = requestAnimationFrame(tick)
}

function startPhysics(el: HTMLElement) {
  el.classList.add('mn-scroll--gliding')
  if (physRaf) return
  phys = { x: el.scrollLeft, v: 0, target: el.scrollLeft }
  physLast = 0
  written = -1
  physRaf = requestAnimationFrame(tick)
}

function onWheel(e: WheelEvent) {
  const el = scroller.value
  if (!el || e.ctrlKey) return
  const max = maxScroll(el)
  if (max < 2) return
  const horizontal = Math.abs(e.deltaX) > Math.abs(e.deltaY)
  const raw = horizontal ? e.deltaX : e.deltaY
  const d = raw * (e.deltaMode === 1 ? 16 : e.deltaMode === 2 ? el.clientWidth : 1)
  if (!d) return
  if (!horizontal) {
    // 指针下面有能竖着滚的区域(歌词)且还没到头:让它自己滚
    for (let n = e.target instanceof Element ? e.target : null; n && n !== el.parentElement; n = n.parentElement) {
      if (n.scrollHeight - n.clientHeight < 2) continue
      const oy = getComputedStyle(n).overflowY
      if (oy !== 'auto' && oy !== 'scroll') continue
      if (d < 0 ? n.scrollTop > 0 : n.scrollTop + n.clientHeight < n.scrollHeight - 1) return
    }
  }
  const dir = Math.sign(d)
  const now = performance.now()
  // 鼠标滚轮:一格一段(行模式,或者一下就是 50px 以上的整数);触控板:连续的小增量
  const notch = !horizontal && (e.deltaMode !== 0 || (Math.abs(raw) >= 50 && Number.isInteger(raw)))
    && !(continuous && now - lastInputAt < 200)

  if (reduceMotion?.matches) {
    const from = el.scrollLeft
    const to = notch ? nextSegment(el, from, dir, 1) : clamp(from + d, 0, max)
    if (to === from) return
    e.preventDefault()
    el.scrollTo({ left: to, behavior: 'instant' as ScrollBehavior })
    return
  }

  e.preventDefault()
  startPhysics(el)
  lastInputAt = now
  pendingIdle = true
  continuous = !notch
  if (notch) {
    notches.push(now)
    const from = clamp(phys.target, 0, max)
    const to = nextSegment(el, from, dir, 1)
    if (to === from) phys.v += dir * BOUNCE_V
    // 一拨就走:按这一段的距离给初速度 ω·Δ。临界阻尼弹簧从这个速度出发正好是指数式的 ease-out
    // (起步最快、越靠近越慢),连拨几格速度叠加,越滚越快
    else phys.v += SPRING_W * (to - from)
    phys.target = to
  } else {
    recent.push({ t: now, d })
    if (recent.length > 12) recent.shift()
    const outside = phys.target < 0 || phys.target > max
    phys.target += d * (outside ? EDGE_RESIST : 1)
    // 触控板要跟手:位置直接跟过去一半,不全等弹簧
    phys.x += (phys.target - phys.x) * 0.5
  }
}

/** 触屏用户:交还给原生滑动和吸附 */
function onTouchStart() {
  stopPhysics()
  scroller.value?.classList.remove('mn-scroll--gliding')
}

// ---- 位置指示条 ----
// 支持滚动驱动动画时全在 CSS 里;不支持时(旧版 iOS WKWebView)用 scroll 监听补上,
// 每帧最多写一次 transform,不进响应式状态。减少动态效果时不显示,改留原生滚动条。
const cssTimeline = typeof CSS !== 'undefined'
  && CSS.supports('animation-timeline', 'scroll()') && CSS.supports('timeline-scope', '--a')
const jsPos = !cssTimeline && typeof matchMedia === 'function'
  && matchMedia('(prefers-reduced-motion: no-preference)').matches
const posThumb = ref<HTMLElement | null>(null)
let posRaf = 0
function syncPos() {
  if (!jsPos || posRaf) return
  posRaf = requestAnimationFrame(() => {
    posRaf = 0
    const el = scroller.value
    const thumb = posThumb.value
    if (!el || !thumb) return
    const max = el.scrollWidth - el.clientWidth
    thumb.style.transform = `scaleX(${max > 0 ? el.scrollLeft / max : 0})`
  })
}

// ---- 手机版面:进度 + 收藏挪到信息磁贴下面单独一行 ----
// 只挂一份进度条(两份都挂的话,隐藏的那份也每 0.25 秒重绘一次)。阈值和样式里的
// @container nowbox (width < 30rem) 相同;只在跨过阈值时写一次,不是每帧
const root = ref<HTMLElement | null>(null)
const phone = ref(false)
function measurePhone(width: number) {
  const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16
  const next = width < 30 * rem
  if (next !== phone.value) phone.value = next
}

let resizeObs: ResizeObserver | null = null
onMounted(() => {
  if (root.value) measurePhone(root.value.getBoundingClientRect().width)
  if (jsPos) syncPos()
  if (typeof ResizeObserver === 'undefined') return
  resizeObs = new ResizeObserver((entries) => {
    for (const e of entries) {
      if (e.target === root.value) measurePhone(e.contentRect.width)
      else syncPos()
    }
  })
  if (root.value) resizeObs.observe(root.value)
  // 滚动层自己的框不变时,内容变宽(队列载入、歌词组出现)也要重算位置条
  if (jsPos && scroller.value) {
    resizeObs.observe(scroller.value)
    if (scroller.value.firstElementChild) resizeObs.observe(scroller.value.firstElementChild)
  }
})
onBeforeUnmount(() => {
  resizeObs?.disconnect()
  cancelAnimationFrame(posRaf)
  stopPhysics()
})
</script>

<template>
  <div ref="root" class="mn" :class="{ 'mn--pos-js': jsPos }">
    <p v-if="notInVoice" class="mn-alert">
      <Icon icon="triangle-exclamation" class="mn-alert-icon" aria-hidden="true" />{{ t('np.notInVoice') }}
    </p>
    <p v-if="error" class="mn-alert mn-alert--error">
      <Icon icon="triangle-exclamation" class="mn-alert-icon" aria-hidden="true" />{{ t('np.unreachable', { error }) }}
    </p>

    <!-- 磁贴里有按钮,Tab 过去会自己滚进来;容器本身也可聚焦,方向键能直接滚动 -->
    <div
      ref="scroller"
      class="mn-scroll"
      role="region"
      :aria-label="t('nav.home')"
      tabindex="0"
      @wheel="onWheel"
      @touchstart.passive="onTouchStart"
      @scroll.passive="syncPos"
    >
      <div class="mn-groups">
        <!-- ===== 此刻 ===== -->
        <div class="g g-now">
          <h2 class="g-head">{{ t('metro.now') }}</h2>
          <div class="now-grid">
            <!-- 封面:有图用图,没有就用标题排一块文字磁贴(装饰,标题在旁边的 h1 里) -->
            <div class="t t-cover" :class="{ 't-cover--type': !artSrc }" aria-hidden="true">
              <AuthImg
                v-if="artSrc"
                :src="artSrc"
                alt=""
                fetchpriority="high"
                class="cover-img"
                :class="{ 'cover-img--pending': !artKind }"
              />
              <template v-else>
                <Icon icon="music" class="t-icon" />
                <!-- 标题还是链接时不排字(大写会改掉链接的意思),只留图标 -->
                <span v-if="!titlePending" class="cover-word" :style="{ '--len-scale': titleScale }">{{ displayTitle || t('np.nothing') }}</span>
              </template>
            </div>

            <div class="t t-info">
              <template v-if="current">
                <p class="info-meta">
                  <span class="badge">{{ sourceLabel }}</span>
                  <span v-if="current.requester" class="info-req info-req--top">{{ t('queue.requestedBy', { name: current.requester }) }}</span>
                </p>
                <template v-if="titlePending">
                  <h1 class="info-title info-title--muted">{{ t('np.loadingTitle') }}</h1>
                  <p class="info-url">{{ current.title }}</p>
                </template>
                <h1 v-else class="info-title" :title="current.title" :style="{ '--len-scale': titleScale }">
                  {{ displayTitle || t('common.untitled') }}
                </h1>
                <p v-if="artistLine" class="info-artist">{{ artistLine }}</p>
                <p v-if="current.requester" class="info-req info-req--bottom">{{ t('queue.requestedBy', { name: current.requester }) }}</p>
                <!-- 进度 + 收藏:宽、窄版面在信息磁贴里,手机版在下面单独一行(只挂一份) -->
                <div v-if="!phone" class="info-foot">
                  <MetroSeek v-if="!showPrep" />
                  <div class="np-actions">
                    <FavButton :item-id="current.id" :source="{ source: 'library', item_id: current.id }" :label="t('np.save')" />
                    <AddToPlaylist :source="{ source: 'current' }" :label="t('atp.header')" layer />
                  </div>
                </div>
              </template>
              <template v-else>
                <h1 class="info-title info-title--muted">{{ t('np.nothing') }}</h1>
                <p class="info-hint">{{ t('np.emptyHint') }}</p>
              </template>
            </div>

            <div v-if="current && phone" class="now-foot">
              <MetroSeek v-if="!showPrep" />
              <div class="np-actions">
                <FavButton :item-id="current.id" :source="{ source: 'library', item_id: current.id }" :label="t('np.save')" />
                <AddToPlaylist :source="{ source: 'current' }" :label="t('atp.header')" layer />
              </div>
            </div>

            <button type="button" class="t t-ctl" :disabled="prevIndex === null" @click="playPrevious">
              <Icon icon="backward-step" class="t-icon" aria-hidden="true" />
              <span class="t-text"><span class="t-label">{{ t('ctl.previous') }}</span></span>
            </button>
            <button type="button" class="t t-ctl t-accent" :disabled="!status || status.empty" @click="togglePlay">
              <Icon :icon="status?.play ? 'pause' : 'play'" class="t-icon" aria-hidden="true" />
              <span class="t-text"><span class="t-label">{{ status?.play ? t('ctl.pause') : t('ctl.play') }}</span></span>
            </button>
            <button type="button" class="t t-ctl" :disabled="!status || status.empty" @click="control({ action: 'skip' })">
              <Icon icon="forward-step" class="t-icon" aria-hidden="true" />
              <span class="t-text"><span class="t-label">{{ t('ctl.skip') }}</span></span>
            </button>
            <div class="t t-vol">
              <div class="vol-top">
                <Icon :icon="volPct === 0 ? 'volume-xmark' : 'volume-low'" class="t-icon" aria-hidden="true" />
                <span class="vol-num" aria-hidden="true">{{ volPct }}</span>
              </div>
              <input
                :id="`${uid}-vol`"
                v-model.number="volPct"
                type="range"
                min="0"
                max="100"
                step="1"
                class="vol"
                :style="{ '--control-value': volPct }"
                :aria-valuetext="`${volPct}%`"
                @input="onVolumeInput"
              />
              <label :for="`${uid}-vol`" class="t-label vol-label">{{ t('ctl.volume') }}</label>
            </div>
            <button type="button" class="t t-ctl" @click="cycleMode">
              <Icon :icon="MODE_ICON[mode] ?? 'arrow-right'" class="t-icon" aria-hidden="true" />
              <span class="t-text"><span class="t-cap">{{ t('ctl.mode') }}</span> <span class="t-label">{{ modeLabel(mode) }}</span></span>
            </button>
          </div>
        </div>

        <!-- ===== 准备中(还没出声) ===== -->
        <div v-if="showPrep && status?.prep" class="g g-prep">
          <h2 class="g-head">{{ t('metro.preparing') }}</h2>
          <PrepPanel :prep="status.prep" :synced-at="syncedAt" />
        </div>

        <!-- ===== 接下来(紧跟"此刻":全景里露出一角的是它,手机上第一屏也能看到) ===== -->
        <div class="g g-queue">
          <h2 class="g-head">
            {{ t('metro.upNext') }}
            <span v-if="upCount" class="g-count">{{ t('common.songs', { n: upCount }) }}</span>
          </h2>
          <div class="q-body">
            <ol v-if="upRows.length" ref="listEl" class="q-list" role="list">
              <li v-for="(row, pos) in upRows" :key="row.key" class="q-item" :class="{ 'q-item--group': row.kind === 'group' }">
                <template v-if="row.kind === 'item'">
                  <span class="q-idx">{{ row.index + 1 }}</span>
                  <span class="q-main">
                    <span class="q-title" :title="row.item.title">{{ row.item.title || t('common.untitled') }}</span>
                    <span class="q-sub">
                      <span v-if="row.item.artist && row.item.artist !== '??'">{{ row.item.artist }}</span>
                      <span v-else>{{ typeLabel(row.item.type) }}</span>
                      <span v-if="row.item.duration"> · {{ formatTime(row.item.duration) }}</span>
                      <span v-if="row.item.requester"> · {{ row.item.requester }}</span>
                    </span>
                  </span>
                  <span class="q-acts">
                    <button
                      type="button"
                      class="q-btn"
                      :title="t('common.playNow')"
                      :aria-label="named(t('common.playNow'), row.item.title || t('common.untitled'))"
                      @click="act({ action: 'play', index: row.index }, pos, row.item.title)"
                    ><Icon icon="play" aria-hidden="true" /></button>
                    <button
                      type="button"
                      class="q-btn q-btn--danger"
                      :title="t('common.remove')"
                      :aria-label="named(t('common.remove'), row.item.title || t('common.untitled'))"
                      @click="act({ action: 'remove', index: row.index }, pos, row.item.title || t('common.untitled'))"
                    ><Icon icon="xmark" aria-hidden="true" /></button>
                  </span>
                </template>
                <template v-else>
                  <span class="q-idx"><Icon :icon="row.group.kind === 'url_playlist' ? 'globe' : 'list-ul'" aria-hidden="true" /></span>
                  <span class="q-main">
                    <span class="q-kind">{{ t(row.group.kind === 'url_playlist' ? 'queue.groupKindOnline' : 'queue.groupKindPlaylist') }}</span>
                    <span class="q-title" :title="row.group.name">{{ row.group.name || t('common.untitled') }}</span>
                    <span class="q-sub">
                      {{ t('queue.groupSongs', { n: row.count, time: formatTime(row.duration) }) }}<span v-if="row.requester"> · {{ row.requester }}</span>
                    </span>
                  </span>
                  <span class="q-acts">
                    <button
                      type="button"
                      class="q-btn"
                      :title="t('queue.groupPlay')"
                      :aria-label="named(t('queue.groupPlay'), row.group.name || t('common.untitled'))"
                      @click="act({ action: 'play', index: row.first }, pos, row.group.name)"
                    ><Icon icon="play" aria-hidden="true" /></button>
                    <button
                      type="button"
                      class="q-btn q-btn--danger"
                      :title="t('queue.groupRemove')"
                      :aria-label="named(t('queue.groupRemove'), row.group.name || t('common.untitled'))"
                      @click="act({ action: 'remove_group', group: row.group.key }, pos, row.group.name || t('common.untitled'))"
                    ><Icon icon="xmark" aria-hidden="true" /></button>
                  </span>
                </template>
              </li>
            </ol>
            <div class="q-more">
              <p v-if="!upRows.length" class="q-note">{{ t('metro.nothingNext') }}</p>
              <button type="button" class="t t-ctl t-dashed" @click="emit('go', 'search')">
                <Icon icon="magnifying-glass" class="t-icon" aria-hidden="true" />
                <span class="t-label">{{ t('metro.searchAdd') }}</span>
              </button>
              <button ref="manageBtn" type="button" class="t t-ctl" @click="emit('go', 'queue')">
                <Icon icon="list-ul" class="t-icon" aria-hidden="true" />
                <span class="t-text-keep">
                  <span class="t-label">{{ t('metro.manageQueue') }}</span>
                  <span v-if="items.length" class="t-cap">{{ t('common.songs', { n: items.length }) }}</span>
                </span>
              </button>
            </div>
          </div>
        </div>

        <!-- ===== 歌词:LyricsPanel 自己的折叠按钮当组标题 ===== -->
        <div v-if="current && hasLyrics" class="g g-lyrics">
          <LyricsPanel :current="current" :preview-at="dragAt" :can-seek="canSeek" @seek="seek" />
        </div>
      </div>
    </div>

    <!-- 横向全景的位置:装饰,读屏跳过 -->
    <div class="mn-pos" aria-hidden="true"><div ref="posThumb" class="mn-pos-thumb" /></div>
  </div>
</template>

<style scoped>
/* ======================================================================
   外层 .mn 决定版面(nowbox),滚动层 .mn-scroll 提供磁贴尺寸用的 cqi / cqb(now)。
   --tile 写在 .mn-groups 上(滚动层里面),所以"框很矮"这几档可以直接查 now ——
   也就是磁贴边长本身算的那个框,而不是外面多了内边距和提示条的 nowbox。
   默认(没有命中任何容器查询,或不支持容器查询)就是竖向的 4 列版面。
   ====================================================================== */
.mn {
  position: absolute;
  inset: 0;
  /* 触底回弹时滚动层整个平移出去一点:裁在这里,不撑出外面的滚动条 */
  overflow: clip;
  display: flex;
  flex-direction: column;
  container: nowbox / size;
  font-family: var(--m-font);
}

.mn-alert {
  flex: none;
  margin: 0 var(--m-pad) var(--m-gap);
  padding: 0.5rem 0.75rem;
  background: var(--c-accent-soft);
  color: var(--c-text);
  font-size: 0.875rem;
  text-wrap: pretty;
}
.mn-alert--error { color: var(--c-danger); }
.mn-alert-icon { margin-inline-end: 0.5rem; color: var(--c-accent); }
.mn-alert--error .mn-alert-icon { color: var(--c-danger); }

.mn-scroll {
  flex: 1;
  min-block-size: 0;
  overflow: auto;
  /* 竖向版面只竖着滚:进场动画里磁贴临时往右偏,不该闪出横向滚动条(全景里再打开) */
  overflow-x: hidden;
  overscroll-behavior: contain;
  container: now / size;
  padding: 0.75rem var(--m-pad) 1.5rem;
  scrollbar-width: thin;
  scrollbar-color: var(--c-text-muted) transparent;
  /* 方向键滚动时,聚焦的磁贴不要贴着边 */
  scroll-padding-inline: var(--m-pad);
}
/* 焦点框画在里面:外面一圈会被裁掉 */
.mn-scroll:focus-visible { outline-offset: -2px; }

.mn-groups {
  /* 竖向 4 列:边长由宽度算出(320 宽约 66px,640 宽约 140px),最大 10rem。
     下限不超过 320px 宽时一列的实际宽度,否则会横向溢出(WCAG 1.4.10);56px 仍大于 44px 触控 */
  --tile: clamp(3.5rem, calc((100cqi - 3 * var(--m-gap)) / 4), 10rem);
  --cols: 4;
  --title-base: calc(var(--tile) * 0.22);
  /* 组标题占的高度(字号 x 行高 + 下边距),全景里从可用高度里减掉 */
  --g-head: 2.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.75rem;
  max-inline-size: calc(var(--cols) * var(--tile) + (var(--cols) - 1) * var(--m-gap));
}

.g { min-inline-size: 0; }
.g-head {
  margin: 0 0 0.75rem;
  font-family: var(--m-font-display);
  font-size: 1.375rem;
  font-weight: 300;
  line-height: 1.25;
  color: var(--c-text);
  text-wrap: balance;
}
.g-count {
  margin-inline-start: 0.375rem;
  font-family: var(--m-font);
  font-size: 0.875rem;
  color: var(--c-text-muted);
}

/* ---------------- 磁贴 ---------------- */
.t {
  position: relative;
  box-sizing: border-box;
  margin: 0;
  border: 0;
  border-radius: 0;
  padding: 0.75rem;
  background: var(--m-tile);
  color: var(--c-text);
  font: inherit;
  text-align: start;
  min-inline-size: 0;
}
button.t {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: flex-start;
  gap: 0.25rem;
  cursor: pointer;
  /* 底色变化不算动态效果,一直保留 */
  transition: background-color 120ms ease-out;
}
button.t:hover:not(:disabled) { background: var(--m-tile-hover); }
button.t:disabled { cursor: default; color: var(--c-text-muted); }
/* 按下时轻微缩小(Metro 的按压反馈),只在允许动态效果时 */
@media (prefers-reduced-motion: no-preference) {
  button.t { transition: background-color 120ms ease-out, scale 120ms ease-out; }
  button.t:active:not(:disabled) { scale: 0.96; }
}
.t-accent { background: var(--c-accent); color: var(--c-on-accent); }
button.t-accent:hover:not(:disabled) { background: var(--c-accent-strong); }
button.t-accent:disabled { background: var(--m-tile); color: var(--c-text-muted); }
.t-dashed { background: transparent; border: 1px dashed var(--c-text-muted); }
.t-icon { font-size: 1.5rem; }
.t-text, .t-text-keep { display: flex; flex-direction: column; gap: 0.125rem; }
.t-label { font-size: 0.875rem; line-height: 1.3; text-wrap: balance; }
.t-cap { font-size: 0.75rem; color: var(--c-text-muted); }
.t-accent .t-cap { color: inherit; }

/* ---------------- 此刻 ---------------- */
/* 竖向版面:第三行 上一首 / 播放 / 下一首 / 模式,音量是第四行的宽磁贴(矮一些)。
   第二行可以长高:竖着滚动的版面里,长标题完整换行,不用截断 */
.now-grid {
  display: grid;
  grid-template-columns: repeat(4, var(--tile));
  grid-template-rows: var(--tile) minmax(var(--tile), auto) var(--tile) auto;
  grid-auto-rows: var(--tile);
  gap: var(--m-gap);
}
.t-cover { grid-column: 1 / span 2; grid-row: 1 / span 2; overflow: hidden; padding: 0; }
.t-cover--type {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 1rem;
  /* 反色磁贴:深色主题下是浅底深字,浅色主题下是深底浅字 */
  background: var(--c-text);
  color: var(--c-bg);
}
.cover-img {
  position: absolute;
  inset: 0;
  inline-size: 100%;
  block-size: 100%;
  object-fit: cover;
}
/* 高清图还没准备好时服务器先给 100px 小图:模糊一点,别拉伸出马赛克 */
.cover-img--pending { filter: blur(12px); scale: 1.1; }
/* 装饰(标题在旁边的 h1 里),所以这里可以截 */
.cover-word {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 5;
  line-clamp: 5;
  overflow: hidden;
  font-family: var(--m-font-display);
  font-size: clamp(1rem, calc(var(--tile) * 0.24 * var(--len-scale, 1)), 2.5rem);
  font-weight: 300;
  line-height: 1.08;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  overflow-wrap: anywhere;
}

.t-info {
  grid-column: 3 / span 2;
  grid-row: 1 / span 2;
  display: flex;
  flex-direction: column;
  padding: 1rem 1.125rem;
}
.info-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.25rem 0.625rem;
  margin: 0;
  font-size: 0.75rem;
  color: var(--c-text-muted);
}
.badge {
  padding: 0.125rem 0.5rem;
  background: var(--c-accent);
  color: var(--c-on-accent);
  letter-spacing: 0.06em;
}
/* 标题不参与收缩:磁贴放不下时让歌手 / 点歌人那几行让位,标题的行框始终完整 */
.info-title {
  flex: none;
  margin: 0.5rem 0 0;
  font-family: var(--m-font-display);
  font-size: clamp(1.1rem, calc(var(--title-base) * var(--len-scale, 1)), 2.75rem);
  font-weight: 300;
  line-height: 1.15;
  text-wrap: balance;
  overflow-wrap: anywhere;
}
.info-title--muted { color: var(--c-text-muted); }
.info-url, .info-hint, .info-artist, .info-req {
  margin: 0.25rem 0 0;
  overflow-wrap: anywhere;
}
.info-artist, .info-req--bottom { min-block-size: 0; overflow: clip; }
.info-artist { font-size: 1rem; color: var(--c-text-muted); }
.info-url { font-size: 0.75rem; color: var(--c-text-muted); }
.info-hint { font-size: 0.875rem; color: var(--c-text-muted); text-wrap: pretty; }
.info-req--bottom { display: none; margin-block-start: auto; font-size: 0.75rem; color: var(--c-text-muted); }
.info-foot { flex: none; margin-block-start: auto; padding-block-start: 0.75rem; }

.np-actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--m-gap);
  margin-block-start: 0.625rem;
}
/* FavButton / AddToPlaylist 的触发按钮换成平铺描边按钮(弹出面板里的按钮不动) */
.np-actions > :deep(button),
.np-actions > :deep(div > button) {
  min-block-size: 2.25rem;
  padding-inline: 0.75rem;
  border: 1px solid var(--c-text-muted);
  border-radius: 0;
  font-size: 0.875rem;
}
@media (pointer: coarse) {
  .np-actions > :deep(button),
  .np-actions > :deep(div > button) { min-block-size: 2.75rem; }
}

.t-vol {
  grid-column: 1 / -1;
  grid-row: 4;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 0.5rem;
  min-block-size: calc(var(--tile) * 0.6);
}
.vol-top { display: flex; align-items: center; justify-content: space-between; }
.vol-num {
  font-family: var(--m-font-display);
  font-size: 1.75rem;
  font-weight: 300;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}
.vol-label { display: block; }
/* 原生 range,只换外观(轨道 / 填充 / 滑块),命中区域 24px,触屏 44px */
.vol {
  --slider-track-size: 4px;
  --slider-thumb-size: 14px;
  --slider-progress: calc(var(--control-value, 50) * 1%);
  appearance: none;
  inline-size: 100%;
  block-size: 24px;
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
}
@media (pointer: coarse) {
  .vol { block-size: 44px; margin-block: -10px; }
}
.vol:focus-visible { outline: 2px solid var(--c-accent); outline-offset: 2px; }
.vol::-webkit-slider-runnable-track {
  block-size: var(--slider-track-size);
  border: 0;
  background: linear-gradient(to right, var(--c-text) var(--slider-progress), var(--m-track) var(--slider-progress));
}
.vol::-webkit-slider-thumb {
  appearance: none;
  inline-size: var(--slider-thumb-size);
  block-size: var(--slider-thumb-size);
  margin-block-start: calc((var(--slider-track-size) - var(--slider-thumb-size)) / 2);
  border: 0;
  border-radius: 0;
  background: var(--c-text);
}
.vol::-moz-range-track {
  block-size: var(--slider-track-size);
  border: 0;
  background: var(--m-track);
}
.vol::-moz-range-progress {
  block-size: var(--slider-track-size);
  background: var(--c-text);
}
.vol::-moz-range-thumb {
  inline-size: var(--slider-thumb-size);
  block-size: var(--slider-thumb-size);
  border: 0;
  border-radius: 0;
  background: var(--c-text);
}

/* ---------------- 准备中 / 歌词 ---------------- */
/* PrepPanel 自带圆角卡片和阴影:换成平铺磁贴(阴影是行内样式,只能 !important 覆盖) */
.g-prep > :deep(div) {
  max-inline-size: none;
  border-radius: 0;
  background: var(--m-tile) !important;
  box-shadow: none !important;
}
.g-lyrics :deep(section) { max-inline-size: none; }
.g-lyrics :deep(.lyr-toggle) {
  min-block-size: 1.75rem;
  padding-inline: 0;
  font-family: var(--m-font-display);
  font-size: 1.375rem;
  font-weight: 300;
  line-height: 1.25;
}
.g-lyrics :deep(.lyr-wrap),
.g-lyrics :deep(.lyr-box),
.g-lyrics :deep(.lyr-btn),
.g-lyrics :deep(.lyr-toggle) { border-radius: 0; }

/* ---------------- 接下来 ---------------- */
.q-body { display: flex; flex-direction: column; gap: var(--m-gap); }
.q-list {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-auto-rows: minmax(calc(var(--tile) * 0.8), auto);
  gap: var(--m-gap);
  margin: 0;
  padding: 0;
  list-style: none;
}
.q-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  grid-template-rows: auto 1fr;
  grid-template-areas: "idx acts" "main main";
  gap: 0.25rem 0.5rem;
  min-inline-size: 0;
  padding: 0.625rem 0.75rem 0.75rem;
  background: var(--m-tile);
}
.q-idx { grid-area: idx; align-self: center; font-size: 0.8125rem; color: var(--c-text-muted); font-variant-numeric: tabular-nums; }
.q-main { grid-area: main; display: flex; flex-direction: column; min-inline-size: 0; }
.q-kind { font-size: 0.75rem; color: var(--c-text-muted); }
.q-title {
  font-size: clamp(0.9375rem, calc(var(--tile) * 0.13), 1.125rem);
  line-height: 1.3;
  overflow-wrap: anywhere;
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  overflow: hidden;
}
.q-sub {
  margin-block-start: auto;
  padding-block-start: 0.25rem;
  font-size: 0.8125rem;
  color: var(--c-text-muted);
  overflow-wrap: anywhere;
}
.q-acts { grid-area: acts; display: flex; gap: 0.25rem; margin-inline-end: -0.375rem; margin-block-start: -0.25rem; }
.q-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  inline-size: 2rem;
  block-size: 2rem;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--c-text);
  cursor: pointer;
  transition: background-color 120ms ease-out;
}
.q-btn:hover { background: var(--m-tile-hover); }
.q-btn--danger { color: var(--c-danger); }
@media (pointer: coarse) {
  .q-btn { inline-size: 2.75rem; block-size: 2.75rem; }
}
.q-more {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  grid-auto-rows: calc(var(--tile) * 0.8);
  gap: var(--m-gap);
}
.q-note {
  grid-column: 1 / -1;
  margin: 0;
  align-self: center;
  font-size: 0.875rem;
  color: var(--c-text-muted);
}

/* ---------------- 位置指示条(只在全景版面) ---------------- */
.mn-pos { display: none; }
.mn-pos-thumb {
  block-size: 100%;
  background: var(--c-text-muted);
  transform-origin: left center;
  transform: scaleX(0);
}

/* ======================================================================
   手机宽度:图标磁贴,进度单独一行,"接下来"是大字列表。
   竖着滚动,所以信息磁贴和标题都按内容长高,不截断
   ====================================================================== */
@container nowbox (width < 30rem) {
  .mn-groups { --title-base: calc(var(--tile) * 0.29); }
  .t-info { padding: 0.75rem; }
  .info-meta { font-size: 0.6875rem; }
  .info-req--top { display: none; }
  .info-req--bottom { display: block; }
  .info-artist { font-size: 0.875rem; }
  .now-foot {
    grid-column: 1 / -1;
    grid-row: 3;
    align-self: center;
    padding-block: 0.75rem 0;
  }
  .now-grid { grid-template-rows: var(--tile) minmax(var(--tile), auto) auto var(--tile) auto; }
  /* 图标磁贴:文字留给读屏 */
  .now-grid .t-ctl { align-items: center; justify-content: center; }
  .now-grid .t-ctl .t-text {
    position: absolute;
    inline-size: 1px;
    block-size: 1px;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
  }
  .t-icon { font-size: 1.625rem; }
  .t-vol { grid-row: 5; flex-direction: row; align-items: center; gap: 0.75rem; min-block-size: 3.5rem; }
  .vol { flex: 1; min-inline-size: 0; }
  .vol-top { flex: none; gap: 0.75rem; }
  .vol-num { font-size: 1.25rem; }
  .vol-label { position: absolute; inline-size: 1px; block-size: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }

  .q-list { display: flex; flex-direction: column; gap: 0; }
  .q-item {
    grid-template-columns: 1.75rem minmax(0, 1fr) auto;
    grid-template-rows: auto;
    grid-template-areas: "idx main acts";
    align-items: start;
    padding: 0.5rem 0;
    background: transparent;
  }
  .q-idx { align-self: baseline; padding-block-start: 0.25rem; }
  /* 列表竖着长,不需要截成两行 */
  .q-title {
    display: block;
    -webkit-line-clamp: unset;
    line-clamp: none;
    overflow: visible;
    font-family: var(--m-font-display);
    font-size: 1.25rem;
    font-weight: 300;
  }
  .q-sub { margin-block-start: 0; }
  .q-acts { margin: 0; }
  .q-more { grid-auto-rows: var(--tile); }
}

/* ======================================================================
   宽而矮:横向全景。磁贴边长 = (可用高度 - 组标题 - 两道间隙) / 3。
   高度固定,所以这里的文字才需要按行数截(完整标题在 title 提示和读屏里)
   ====================================================================== */
@container nowbox (aspect-ratio >= 5 / 4) and (width >= 37.5rem) {
  .mn-scroll {
    padding-block: 0.5rem 1.25rem;
    padding-inline-end: 0;
    overflow-x: auto;
    scroll-snap-type: x proximity;
    overscroll-behavior: contain;
  }
  .mn-groups {
    --tile: clamp(4.5rem, calc((100cqb - var(--g-head) - 2 * var(--m-gap)) / 3), 11rem);
    --title-base: calc(var(--tile) * 0.3);
    flex-direction: row;
    align-items: flex-start;
    gap: 3rem;
    inline-size: max-content;
    max-inline-size: none;
    /* 最后一组右边留出一个边距,能滚到头 */
    padding-inline-end: var(--m-pad);
  }
  .g { flex: none; scroll-snap-align: start; }
  .now-grid {
    grid-template-columns: repeat(6, var(--tile));
    grid-template-rows: repeat(3, var(--tile));
  }
  .t-vol { min-block-size: 0; gap: 0.25rem; grid-column: span 2; grid-row: auto; }
  .t-info { grid-column: 3 / span 4; padding: 1.25rem 1.375rem; }
  .info-meta { font-size: 0.8125rem; }
  /* 信息磁贴有 4 块宽:长标题也保持大字(约 26–30px),最多 3 行 */
  .info-title {
    font-size: clamp(1.375rem, calc(var(--title-base) * max(var(--len-scale, 1), 0.66)), 2.75rem);
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 3;
    line-clamp: 3;
    overflow: hidden;
  }
  .info-artist { font-size: 1.125rem; }
  .t-icon { font-size: 1.75rem; }

  .g-prep, .g-lyrics { inline-size: calc(3 * var(--tile) + 2 * var(--m-gap)); }
  /* 整组和"此刻"一样高:标题行(折叠按钮、偏移按钮)多高都行,剩下的给歌词框 */
  .g-lyrics :deep(section) {
    display: flex;
    flex-direction: column;
    block-size: calc(3 * var(--tile) + 2 * var(--m-gap) + var(--g-head));
  }
  .g-lyrics :deep(section > *) { flex: none; }
  .g-lyrics :deep(.lyr-wrap) { display: flex; flex: 1 1 0; flex-direction: column; min-block-size: 0; }
  .g-lyrics :deep(.lyr-box) { flex: 1 1 0; block-size: auto; min-block-size: 0; }

  .q-body { flex-direction: row; align-items: flex-start; }
  /* 行高至少一块磁贴,内容多时长高(宁可多出一点,也不叠到下一块上)。
     磁贴高度固定在一块边长,所以序号、标题、操作按钮排成一行,省下单独一行按钮的高度;
     按钮在标题右边后两块磁贴宽(矮框里约 2 x 6rem)放不下标题:列宽至少 17rem */
  .q-list {
    grid-auto-flow: column;
    grid-template-columns: none;
    grid-template-rows: repeat(3, minmax(var(--tile), auto));
    grid-auto-columns: max(calc(2 * var(--tile) + var(--m-gap)), 17rem);
    grid-auto-rows: auto;
  }
  .q-more {
    grid-auto-flow: column;
    grid-template-columns: none;
    grid-template-rows: repeat(3, var(--tile));
    grid-auto-columns: max(calc(2 * var(--tile) + var(--m-gap)), 17rem);
    grid-auto-rows: auto;
  }
  .q-item {
    grid-template-columns: auto minmax(0, 1fr) auto;
    grid-template-rows: auto;
    grid-template-areas: "idx main acts";
    align-items: start;
  }
  .q-idx { align-self: start; padding-block-start: 0.125rem; }
  .q-note { grid-column: auto; }

  .mn-pos {
    position: absolute;
    inset-inline: var(--m-pad);
    inset-block-end: 0.5rem;
    block-size: 2px;
    background: var(--m-track);
  }
  .mn--pos-js .mn-pos { display: block; }
  .mn--pos-js .mn-scroll { scrollbar-width: none; }
  .mn--pos-js .mn-scroll::-webkit-scrollbar { display: none; }

  /* ---- 矮全景:磁贴约 6–8rem。查的是 now(磁贴边长算的那个框) ----
     收藏 / 加入歌单缩成图标,和进度条并排在信息磁贴底部;
     "接下来"改成两行更高的磁贴 */
  @container now (height < 28rem) {
    .t-info { padding: 0.75rem 1rem; }
    .info-title {
      margin-block-start: 0.25rem;
      font-size: clamp(1rem, calc(var(--tile) * 0.22 * max(var(--len-scale, 1), 0.78)), 1.75rem);
      -webkit-line-clamp: 2;
      line-clamp: 2;
    }
    .info-artist { font-size: 0.9375rem; }
    .info-foot { display: flex; align-items: center; gap: 0.75rem; padding-block-start: 0.5rem; }
    .info-foot > :deep(.ms) { flex: 1; min-inline-size: 0; }
    .np-actions { flex: none; flex-wrap: nowrap; margin: 0; gap: 0.25rem; }
    .np-actions > :deep(button),
    .np-actions > :deep(div > button) { min-block-size: 2rem; min-inline-size: 2rem; padding-inline: 0.5rem; justify-content: center; }
    .np-actions > :deep(button > span),
    .np-actions > :deep(div > button > span),
    .now-grid .t-cap {
      position: absolute;
      inline-size: 1px;
      block-size: 1px;
      overflow: hidden;
      clip-path: inset(50%);
      white-space: nowrap;
    }
    .q-list,
    .q-more { grid-template-rows: repeat(2, minmax(calc((3 * var(--tile) + var(--m-gap)) / 2), auto)); }
  }
  /* 触屏上图标按钮仍是 44px(要放在上面那条规则后面,同样的选择器才能覆盖) */
  @media (pointer: coarse) {
    @container now (height < 28rem) {
      .np-actions > :deep(button),
      .np-actions > :deep(div > button) { min-block-size: 2.75rem; min-inline-size: 2.75rem; }
    }
  }

  /* ---- 很矮的全景(Activity 框约 300–420px 高):磁贴可以小到 44px,
     组标题变小,控制磁贴只留图标,音量变成一行 ---- */
  @container now (height < 21.5rem) {
    .mn-groups {
      --g-head: 1.5rem;
      --tile: clamp(2.75rem, calc((100cqb - var(--g-head) - 2 * var(--m-gap)) / 3), 11rem);
    }
    .g-head { margin-block-end: 0.25rem; font-size: 1rem; }
    .g-count { font-size: 0.75rem; }
    .g-lyrics :deep(.lyr-toggle) { font-size: 1rem; }
    .t { padding: 0.5rem; }
    .t-info { padding: 0.5rem 0.75rem; }
    .info-meta { font-size: 0.6875rem; line-height: 1.2; }
    .badge { padding-block: 0.0625rem; }
    .info-title {
      margin-block-start: 0.125rem;
      font-size: clamp(0.9375rem, calc(var(--tile) * 0.24 * max(var(--len-scale, 1), 0.78)), 1.5rem);
    }
    .info-artist { margin-block-start: 0.125rem; font-size: 0.8125rem; }
    .info-foot { padding-block-start: 0.25rem; }
    .now-grid .t-ctl { align-items: center; justify-content: center; }
    .now-grid .t-ctl .t-text,
    .vol-label {
      position: absolute;
      inline-size: 1px;
      block-size: 1px;
      overflow: hidden;
      clip-path: inset(50%);
      white-space: nowrap;
    }
    .t-icon { font-size: 1.25rem; }
    .t-vol { flex-direction: row; align-items: center; gap: 0.5rem; }
    .vol { flex: 1; min-inline-size: 0; }
    .vol-top { flex: none; gap: 0.5rem; }
    .vol-num { font-size: 1.125rem; }
    .q-item { padding: 0.375rem 0.625rem; }
    .q-sub { font-size: 0.75rem; }
  }
}

/* 全景,框也很矮:滚动层的内边距和提示条收紧(这几条改的是 now 外面的东西,所以查 nowbox) */
@container nowbox (aspect-ratio >= 5 / 4) and (width >= 37.5rem) and (height < 23rem) {
  .mn-scroll { padding-block: 0.25rem 0.75rem; }
  .mn-pos { inset-block-end: 0.25rem; }
  .mn-alert { margin-block-end: 0.25rem; padding-block: 0.25rem; font-size: 0.8125rem; }
}

/* 滚动驱动的位置指示:只在允许动态效果、支持滚动时间线时;否则留原生细滚动条 */
@media (prefers-reduced-motion: no-preference) {
  @supports (animation-timeline: scroll()) and (timeline-scope: --a) {
    .mn { timeline-scope: --pano; }
    .mn-scroll { scroll-timeline: --pano inline; }
    /* 长写法:构建时 animation 简写会被展开成 animation-duration: 0s,滚动时间线要的是 auto */
    .mn-pos-thumb {
      animation-name: mn-pos-grow;
      animation-duration: auto;
      animation-timing-function: linear;
      animation-fill-mode: both;
      animation-timeline: --pano;
    }
    @container nowbox (aspect-ratio >= 5 / 4) and (width >= 37.5rem) {
      .mn-pos { display: block; }
      .mn-scroll { scrollbar-width: none; }
      .mn-scroll::-webkit-scrollbar { display: none; }
    }
  }
}
@keyframes mn-pos-grow {
  from { transform: scaleX(0); }
  to { transform: scaleX(1); }
}

/* Windows 高对比度:底色会被系统色替换,磁贴用边框分开 */
@media (forced-colors: active) {
  .t, .q-item { border: 1px solid CanvasText; }
  .badge { border: 1px solid CanvasText; }
  .mn-pos { border-block-start: 1px solid CanvasText; }
  .mn-pos-thumb { forced-color-adjust: none; background: CanvasText; }
  /* 音量:渐变底会被去掉、背景色换成 Canvas,轨道和滑块就都看不见了。
     音量值本身是信息,用系统色画;两种引擎的伪元素分开写 */
  .vol { forced-color-adjust: none; }
  .vol::-webkit-slider-runnable-track {
    background: linear-gradient(to right, Highlight var(--slider-progress), GrayText var(--slider-progress));
  }
  .vol::-webkit-slider-thumb { background: CanvasText; }
  .vol::-moz-range-track { background: GrayText; }
  .vol::-moz-range-progress { background: Highlight; }
  .vol::-moz-range-thumb { background: CanvasText; }
}

/* ======================================================================
   动效(只在没有要求减少动效时启用;默认就是静态的最终状态)
   ====================================================================== */

/* 滚轮驱动的滑动期间不吸附,否则每帧写入的位置都会被拉回组的开头 */
.mn-scroll.mn-scroll--gliding { scroll-snap-type: none; }

@media (prefers-reduced-motion: no-preference) {
  /* 方向键、Tab 把磁贴滚进来时也是顺滑的(滚轮滑动用的是 instant,不受影响) */
  .mn-scroll { scroll-behavior: smooth; }

  /* 进场:像 Windows 8 开始屏幕,磁贴从侧面依次飞进来。方向跟着导航走(外壳设 --enter-x),
     每组晚一点,组里每块再错开一点。只动 translate 和 opacity,留在合成线程上 */
  .g-head,
  .now-grid > *,
  .q-list > *,
  .q-more > *,
  .g-prep > :not(.g-head),
  .g-lyrics > * {
    animation-name: mn-enter;
    animation-duration: 560ms;
    animation-timing-function: cubic-bezier(0.1, 0.9, 0.2, 1);
    animation-fill-mode: both;
    /* 不认识 sibling-index() 的浏览器用下面 nth-child 给的 --sibling-index;认识的用后一行 */
    animation-delay: calc(var(--g, 0) * 90ms + (var(--sibling-index, 1) - 1) * 28ms);
    animation-delay: calc(var(--g, 0) * 90ms + min(sibling-index() - 1, 7) * 28ms);
  }
}
.g-now { --g: 0; }
.g-prep { --g: 1; }
.g-queue { --g: 1; }
.g-prep ~ .g-queue { --g: 2; }
.g-lyrics { --g: 2; }
.g-prep ~ .g-lyrics { --g: 3; }
.now-grid > :nth-child(2), .q-list > :nth-child(2), .q-more > :nth-child(2) { --sibling-index: 2; }
.now-grid > :nth-child(3), .q-list > :nth-child(3), .q-more > :nth-child(3) { --sibling-index: 3; }
.now-grid > :nth-child(4), .q-list > :nth-child(4) { --sibling-index: 4; }
.now-grid > :nth-child(5), .q-list > :nth-child(5) { --sibling-index: 5; }
.now-grid > :nth-child(6), .q-list > :nth-child(6) { --sibling-index: 6; }
.now-grid > :nth-child(7), .q-list > :nth-child(7) { --sibling-index: 7; }
.now-grid > :nth-child(n + 8), .q-list > :nth-child(n + 8) { --sibling-index: 8; }

@keyframes mn-enter {
  from {
    opacity: 0;
    translate: var(--enter-x, 2.5rem) 0;
  }
}
</style>
