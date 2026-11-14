<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { apiFetch, fetchLogs, logsDownloadUrl, setDebugLogging, type LogEntry, type LogLevel, type LogState } from '../api'
import { embedded } from '../activity'
import { locale, t } from '../i18n'
import type { Key } from '../i18n/en'
import { announce } from '../composables/useAnnounce'

/** A log line plus its display time, formatted once when it arrives instead of on every render. */
type Row = LogEntry & { stamp: string }

const MAX_ENTRIES = 2000
const POLL_MS = 2000

const entries = ref<Row[]>([])
const state = ref<LogState | null>(null)
const level = ref<LogLevel>('INFO')
const query = ref('')
const live = ref(true)
const error = ref('')
const busy = ref(false)
const copied = ref(false)
const scroller = ref<HTMLElement | null>(null)
const expanded = ref<Record<number, boolean>>({})
let lastSeq = 0
let knownRun = '' // 当前 bot 进程的 run id;变了说明 bot 重启过,序号重新编过
let timer: ReturnType<typeof setTimeout> | undefined
let generation = 0 // 筛选条件一变就作废还在路上的请求

const LEVELS: { key: LogLevel; label: Key }[] = [
  { key: 'DEBUG', label: 'logs.lvAll' },
  { key: 'INFO', label: 'logs.lvInfo' },
  { key: 'WARNING', label: 'logs.lvWarn' },
  { key: 'ERROR', label: 'logs.lvError' },
]

function nearBottom() {
  const el = scroller.value
  return !el || el.scrollHeight - el.scrollTop - el.clientHeight < 40
}

function setError(msg: string) {
  // Polling repeats every 2 s: announce only when the message changes
  if (msg !== error.value) announce(msg, { assertive: true })
  error.value = msg
}

async function poll() {
  const gen = generation
  try {
    const rv = await fetchLogs(lastSeq, level.value, query.value.trim())
    if (gen !== generation) return
    state.value = rv.state
    error.value = ''
    if (knownRun && rv.state.run !== knownRun) {
      // bot 重启了,序号从头编过:整体重拉
      knownRun = rv.state.run
      lastSeq = 0
      entries.value = []
      return poll()
    }
    knownRun = rv.state.run
    lastSeq = rv.last_seq
    if (rv.entries.length) {
      const stick = nearBottom()
      entries.value = [...entries.value, ...rv.entries.map(withStamp)].slice(-MAX_ENTRIES)
      if (stick) {
        await nextTick()
        scroller.value?.scrollTo({ top: scroller.value.scrollHeight })
      }
    }
  } catch (e) {
    if (gen === generation) setError(e instanceof Error && e.message.endsWith('403') ? t('logs.forbidden') : t('logs.loadFailed'))
  }
}

function schedule() {
  clearTimeout(timer)
  if (live.value) timer = setTimeout(async () => { await poll(); schedule() }, POLL_MS)
}

async function restart() {
  generation++
  lastSeq = 0
  entries.value = []
  expanded.value = {}
  await poll()
  schedule()
}

let debounce: ReturnType<typeof setTimeout> | undefined
watch(level, restart)
watch(query, () => { clearTimeout(debounce); debounce = setTimeout(restart, 350) })
watch(live, (on) => (on ? poll().then(schedule) : clearTimeout(timer)))

onMounted(restart)
onBeforeUnmount(() => { clearTimeout(timer); clearTimeout(debounce); generation++ })

// The checkbox stays enabled while saving (disabling it would drop keyboard focus);
// a toggle during a save is undone instead.
async function toggleDebug(e: Event) {
  const box = e.target as HTMLInputElement
  if (!state.value || busy.value) {
    box.checked = !!state.value?.debug_until
    return
  }
  busy.value = true
  try {
    state.value = await setDebugLogging(!state.value.debug_until)
    await poll()
  } catch {
    box.checked = !!state.value?.debug_until
    setError(t('common.saveFailed'))
  } finally {
    busy.value = false
  }
}

// ---- 显示 ----------------------------------------------------------------

const today = new Date().toDateString()
// Same fields as toLocaleTimeString(locale, { hour12: false }), built once per locale
const TIME_OPTS: Intl.DateTimeFormatOptions = { hour: 'numeric', minute: 'numeric', second: 'numeric', hour12: false }
let timeFmt = new Intl.DateTimeFormat(locale.value, TIME_OPTS)
function stamp(ts: number) {
  const d = new Date(ts * 1000)
  const time = timeFmt.format(d)
  return d.toDateString() === today ? time : `${d.getMonth() + 1}/${d.getDate()} ${time}`
}
function withStamp(e: LogEntry): Row {
  return { ...e, stamp: stamp(e.ts) }
}
watch(locale, (loc) => {
  timeFmt = new Intl.DateTimeFormat(loc, TIME_OPTS)
  entries.value = entries.value.map(withStamp)
})

const LEVEL_SHORT: Record<string, string> = { WARNING: 'WARN', CRITICAL: 'CRIT' }
const LEVEL_COLOR: Record<string, string> = {
  DEBUG: 'var(--c-text-faint)',
  INFO: 'var(--c-text-muted)',
  WARNING: 'var(--c-warning)',
  ERROR: 'var(--c-danger)',
  CRITICAL: 'var(--c-danger)',
}

/** 列表行:日志条目之间插入"重启"分隔线 */
const rows = computed(() => {
  const out: ({ kind: 'entry'; e: Row } | { kind: 'restart'; key: string; current: boolean })[] = []
  let run: string | null = null
  for (const e of entries.value) {
    if (run !== null && e.run !== run) out.push({ kind: 'restart', key: `r${e.seq}`, current: e.run === state.value?.run })
    run = e.run
    out.push({ kind: 'entry', e })
  }
  return out
})

const errorCount = computed(() =>
  entries.value.filter((e) => (e.level === 'ERROR' || e.level === 'CRITICAL') && e.run === state.value?.run).length)

const debugUntil = computed(() =>
  state.value?.debug_until
    ? new Date(state.value.debug_until * 1000).toLocaleTimeString(locale.value, { hour: '2-digit', minute: '2-digit', hour12: false })
    : '')

function asText(e: LogEntry) {
  const name = e.name === 'bot' ? '' : ` ${e.name}`
  return `${new Date(e.ts * 1000).toISOString()} ${e.level}${name} ${e.msg}${e.exc ? `\n${e.exc}` : ''}`
}

async function copyAll() {
  try {
    await navigator.clipboard.writeText(entries.value.map(asText).join('\n'))
    copied.value = true
    setTimeout(() => (copied.value = false), 1500)
  } catch { /* 不支持剪贴板就用下载 */ }
}

const downloadHref = computed(() => logsDownloadUrl(level.value, query.value.trim()))

// Inside the Discord Activity the token only travels in the Authorization header, so a
// plain link would navigate the iframe to the sign-in page. Fetch it and save a blob.
async function downloadEmbedded() {
  try {
    const rv = await apiFetch(downloadHref.value)
    if (!rv.ok) throw new Error(String(rv.status))
    const name = /filename="([^"]+)"/.exec(rv.headers.get('Content-Disposition') ?? '')?.[1] ?? 'djbot-logs.txt'
    const url = URL.createObjectURL(await rv.blob())
    const a = Object.assign(document.createElement('a'), { href: url, download: name })
    a.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch {
    setError(t('logs.downloadFailed'))
  }
}

// Level picker: one tab stop, arrow keys move the selection (radio group pattern)
const levelButtons = ref<HTMLButtonElement[]>([])
function onLevelKey(e: KeyboardEvent) {
  const step = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1
    : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0
  const edge = e.key === 'Home' ? 0 : e.key === 'End' ? LEVELS.length - 1 : -1
  if (!step && edge < 0) return
  e.preventDefault()
  const cur = LEVELS.findIndex((l) => l.key === level.value)
  const next = edge >= 0 ? edge : (cur + step + LEVELS.length) % LEVELS.length
  level.value = LEVELS[next].key
  levelButtons.value[next]?.focus()
}
</script>

<template>
  <div>
    <!-- 状态 + 调试开关 -->
    <div class="rounded-2xl p-5" :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)' }">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div class="min-w-0">
          <p class="text-sm">
            {{ t('logs.runStarted', { time: state ? stamp(state.started_at) : '…' }) }}
            <span v-if="errorCount" class="ml-1 rounded-full px-2 py-0.5 text-xs font-semibold"
                  :style="{ background: 'var(--c-accent-soft)', color: 'var(--c-danger)' }">
              {{ t('logs.errorCount', { n: errorCount }) }}</span>
          </p>
          <p class="mt-1 text-xs" :style="{ color: 'var(--c-text-faint)' }">
            {{ state?.persistent ? t('logs.persistent') : t('logs.memoryOnly') }}
          </p>
        </div>
        <label class="flex cursor-pointer items-center gap-2 text-sm">
          <input type="checkbox" class="h-4 w-4" :style="{ accentColor: 'var(--c-accent)' }"
                 aria-describedby="logs-debug-hint"
                 :checked="!!state?.debug_until" :disabled="!state" @change="toggleDebug" />
          <span>{{ t('logs.debug') }}</span>
        </label>
      </div>
      <p id="logs-debug-hint" class="mt-2 text-xs" :style="{ color: 'var(--c-text-muted)' }">
        <template v-if="state?.debug_until">{{ t('logs.debugOn', { time: debugUntil }) }}</template>
        <template v-else>{{ t('logs.debugHint') }}</template>
      </p>
    </div>

    <!-- 工具栏 -->
    <div class="mt-4 flex flex-wrap items-center gap-2">
      <div class="flex gap-1 rounded-full p-1" :style="{ background: 'var(--c-surface-2)' }" role="radiogroup" :aria-label="t('logs.level')"
           @keydown="onLevelKey">
        <button v-for="l in LEVELS" :key="l.key" ref="levelButtons" type="button" role="radio" :aria-checked="level === l.key"
                :tabindex="level === l.key ? 0 : -1"
                class="cursor-pointer rounded-full border-0 px-3 py-1 text-xs font-medium whitespace-nowrap"
                :style="level === l.key ? { background: 'var(--c-accent)', color: 'var(--c-on-accent)' } : { background: 'transparent', color: 'var(--c-text-muted)' }"
                @click="level = l.key">{{ t(l.label) }}</button>
      </div>
      <input v-model="query" type="search" :placeholder="t('logs.search')" :aria-label="t('logs.searchLabel')"
             autocomplete="off" autocorrect="off" autocapitalize="none" spellcheck="false" enterkeyhint="search"
             class="min-w-0 flex-1 rounded-full border px-4 py-1.5 text-xs sm:max-w-56"
             :style="{ background: 'var(--c-surface)', borderColor: 'var(--c-border)', color: 'var(--c-text)' }" />
      <div class="ml-auto flex gap-1.5">
        <button class="cursor-pointer rounded-full border-0 px-3 py-1.5 text-xs font-medium whitespace-nowrap"
                :style="live ? { background: 'var(--c-accent-soft)', color: 'var(--c-accent)' } : { background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
                :title="t(live ? 'logs.pauseHint' : 'logs.resumeHint')"
                @click="live = !live"><Icon :icon="live ? 'circle' : 'pause'" class="mr-1" :class="live ? 'motion-safe:animate-pulse text-[8px]' : ''" aria-hidden="true" />{{ live ? t('logs.live') : t('logs.paused') }}</button>
        <button class="cursor-pointer rounded-full border-0 px-3 py-1.5 text-xs whitespace-nowrap"
                :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
                :disabled="!entries.length" @click="copyAll"><Icon :icon="copied ? 'check' : 'copy'" class="mr-1" />{{ t(copied ? 'me.copied' : 'logs.copy') }}</button>
        <button v-if="embedded" type="button" class="cursor-pointer rounded-full border-0 px-3 py-1.5 text-xs whitespace-nowrap"
                :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
                :title="t('logs.downloadHint')" @click="downloadEmbedded"><Icon icon="download" class="mr-1" aria-hidden="true" />{{ t('logs.download') }}</button>
        <a v-else class="rounded-full px-3 py-1.5 text-xs whitespace-nowrap no-underline"
           :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
           :href="downloadHref" download :title="t('logs.downloadHint')"><Icon icon="download" class="mr-1" aria-hidden="true" />{{ t('logs.download') }}</a>
      </div>
    </div>

    <p v-if="error" class="mt-3 rounded-lg px-3 py-2 text-sm"
       :style="{ background: 'var(--c-accent-soft)', color: 'var(--c-danger)' }"><Icon icon="triangle-exclamation" class="mr-1.5" aria-hidden="true" />{{ error }}</p>

    <!-- 日志 -->
    <div ref="scroller" class="mt-3 max-h-[65vh] overflow-y-auto overscroll-contain rounded-2xl py-2 font-mono text-[11.5px] leading-relaxed"
         :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)' }">
      <p v-if="!entries.length" class="px-4 py-6 text-center font-sans text-sm" :style="{ color: 'var(--c-text-muted)' }">
        {{ query.trim() ? t('logs.noMatch') : t('logs.empty') }}
      </p>
      <!-- v-memo: a poll appends lines, so earlier rows skip re-rendering -->
      <div v-for="row in rows" :key="row.kind === 'entry' ? row.e.seq : row.key" class="log-row"
           v-memo="row.kind === 'entry' ? [row.e, !!expanded[row.e.seq], locale] : [row.key, row.current, locale]">
        <div v-if="row.kind === 'restart'" class="my-1.5 flex items-center gap-2 px-4 font-sans text-[11px] font-semibold"
             :style="{ color: 'var(--c-accent)' }">
          <span class="h-px flex-1" :style="{ background: 'var(--c-border)' }" />
          {{ t('logs.restarted') }}
          <span class="h-px flex-1" :style="{ background: 'var(--c-border)' }" />
        </div>
        <div v-else class="flex gap-2 px-4 py-0.5"
             :class="row.e.exc ? 'cursor-pointer' : ''"
             :style="row.e.level === 'ERROR' || row.e.level === 'CRITICAL' ? { background: 'color-mix(in srgb, var(--c-danger) 8%, transparent)' }
               : row.e.level === 'WARNING' ? { background: 'color-mix(in srgb, var(--c-warning) 7%, transparent)' } : {}"
             :title="`${row.e.src} · ${row.e.thread}`"
             @click="row.e.exc && (expanded[row.e.seq] = !expanded[row.e.seq])">
          <span class="shrink-0 tabular-nums" :style="{ color: 'var(--c-text-faint)' }">{{ row.e.stamp }}</span>
          <span class="w-12 shrink-0 font-semibold" :style="{ color: LEVEL_COLOR[row.e.level] }">{{ LEVEL_SHORT[row.e.level] ?? row.e.level }}</span>
          <div class="min-w-0 flex-1">
            <p class="break-words whitespace-pre-wrap" :style="{ color: row.e.level === 'DEBUG' ? 'var(--c-text-muted)' : 'var(--c-text)' }">
              <span v-if="row.e.name !== 'bot'" class="mr-1 rounded px-1" :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text-muted)' }">{{ row.e.name }}</span>{{ row.e.msg }}<span
                v-if="row.e.exc && !expanded[row.e.seq]" class="ml-1 font-sans" :style="{ color: 'var(--c-accent)' }"><Icon icon="caret-right" class="mr-0.5" />{{ t('logs.showTrace') }}</span>
            </p>
            <pre v-if="row.e.exc && expanded[row.e.seq]" class="mt-1 mb-1 overflow-x-auto rounded-lg p-2 text-[11px]"
                 :style="{ background: 'var(--c-bg)', color: 'var(--c-danger)' }">{{ row.e.exc }}</pre>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Up to 2000 lines: let the browser skip layout and paint for rows scrolled out of
   view. One line of text plus the row's 2px top and bottom padding. */
.log-row {
  content-visibility: auto;
  contain-intrinsic-block-size: auto calc(1lh + 4px);
}
</style>
