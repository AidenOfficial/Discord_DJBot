import { computed, reactive, ref, watch } from 'vue'
import { fetchStatus, postControls, type BotStatus, type ControlAction } from '../api'
import { selectedGuild } from '../guild'

const POLL_MS = 3000

// Module-level singleton: every component shares the same status stream and
// the same smoothly advancing playhead clock.
const status = ref<BotStatus | null>(null)
const error = ref<string | null>(null)
const clock = reactive({ playhead: 0 })

let started = false
let lastSync = 0 // performance.now() at the time of the last poll
const syncedAt = ref(0) // 同上,给需要本地推算的组件(准备面板)用

function applyStatus(s: BotStatus) {
  status.value = s
  lastSync = performance.now()
  syncedAt.value = lastSync
  clock.playhead = quantize(s.playhead)
  error.value = null
}

async function poll() {
  const guild = selectedGuild.value
  try {
    const s = await fetchStatus()
    if (guild === selectedGuild.value) applyStatus(s)  // 请求途中换了服务器:丢掉旧服务器的状态
  } catch (e) {
    if (guild === selectedGuild.value) error.value = e instanceof Error ? e.message : String(e)
  }
}

// 换服务器:旧服务器的状态立刻清掉,马上拉新的(不等下一轮)
watch(selectedGuild, () => {
  status.value = null
  error.value = null
  clock.playhead = 0
  if (started) poll()
})

// 播放头按 0.25 秒一档写进响应式状态:进度条用 CSS 过渡补齐中间的动画,歌词换行也够准,
// 而不是每一帧(120Hz 屏上每秒 120 次)让正在播放页整页重渲染。
const PLAYHEAD_STEP = 0.25
let raf = 0
function quantize(seconds: number) {
  return Math.floor(seconds / PLAYHEAD_STEP) * PLAYHEAD_STEP
}

function isAdvancing() {
  const s = status.value
  return !!s && s.play && !s.empty && !s.prep  // 还在准备(没出声)时进度不走
}

function tick() {
  raf = 0
  const s = status.value
  if (!s || !isAdvancing()) return  // 暂停 / 没歌:停掉循环,状态变了 ensureTicking() 再开
  const elapsed = (performance.now() - lastSync) / 1000
  const duration = s.current?.duration || 0
  const pos = s.playhead + elapsed
  const next = quantize(duration > 0 ? Math.min(pos, duration) : pos)
  if (next !== clock.playhead) clock.playhead = next
  raf = requestAnimationFrame(tick)
}

function ensureTicking() {
  if (!raf && isAdvancing()) raf = requestAnimationFrame(tick)
}

watch(() => isAdvancing(), ensureTicking)

// 等待开播 / 后台下载时每秒刷新,平时 3 秒一次
function nextDelay() {
  const s = status.value
  return s?.prep || s?.current?.download ? 1000 : POLL_MS
}

// 页面隐藏(切走标签页、Discord 最小化;Electron 常常不节流后台定时器)时不轮询,
// 回到前台立刻拉一次,让进度马上对齐。
let pollTimer: ReturnType<typeof setTimeout> | undefined
let polling = false

async function pollLoop() {
  clearTimeout(pollTimer)
  pollTimer = undefined
  if (polling) return
  polling = true
  try {
    await poll()
  } finally {
    polling = false
  }
  if (document.visibilityState !== 'hidden') pollTimer = setTimeout(pollLoop, nextDelay())
}

function onVisibility() {
  if (document.visibilityState === 'hidden') {
    clearTimeout(pollTimer)
    pollTimer = undefined
  } else if (!pollTimer) {
    void pollLoop()
  }
}

function ensureStarted() {
  if (started) return
  started = true
  document.addEventListener('visibilitychange', onVisibility)
  void pollLoop()
}

/** Fire a control action; the response is a fresh status, applied at once. */
async function control(body: ControlAction) {
  const guild = selectedGuild.value
  try {
    const s = await postControls(body)
    if (guild === selectedGuild.value) applyStatus(s)
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}

export function useStatus() {
  ensureStarted()
  const progress = computed(() => {
    const duration = status.value?.current?.duration || 0
    if (!duration) return 0
    return Math.min(1, clock.playhead / duration)
  })
  return { status, error, clock, progress, syncedAt, refresh: poll, control, applyStatus }
}

export function formatTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) seconds = 0
  const s = Math.floor(seconds)
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const mm = h > 0 ? String(m).padStart(2, '0') : String(m)
  const ss = String(sec).padStart(2, '0')
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`
}
