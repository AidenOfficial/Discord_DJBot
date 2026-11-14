<script lang="ts">
import type { Lyrics as CachedLyrics } from '../api'

// 模块级:切到别的页面再回来时,当前这首的歌词直接显示,不用再等一次请求
let lastLyrics: { id: string; data: CachedLyrics } | null = null
</script>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { fetchLyrics, postLyricsOffset, type CurrentItem, type Lyrics } from '../api'
import { useStatus } from '../composables/useStatus'
import { getItem, setItem } from '../storage'
import { t } from '../i18n'

// previewAt:拖动进度条时预览的位置。平时直接读共享的播放头,
// 这样 prop 不会每 0.25 秒变一次,只有换行时才重渲染。
const props = defineProps<{ current: CurrentItem; previewAt?: number | null; canSeek: boolean }>()
const emit = defineEmits<{ seek: [position: number] }>()
const { clock } = useStatus()

const STORAGE_KEY = 'lyricsHidden'
const hidden = ref(getItem(STORAGE_KEY) === '1')
function toggle() {
  hidden.value = !hidden.value
  setItem(STORAGE_KEY, hidden.value ? '1' : '0')
}

// ---- 取歌词:状态轮询里的 current.lyrics 变成 found / instrumental 才去取 ----
const lyrics = ref<Lyrics | null>(null)
const loadedFor = ref('')
watch(
  () => [props.current.id, props.current.lyrics] as const,
  async ([id, state]) => {
    if (loadedFor.value !== id) {
      lyrics.value = null
      loadedFor.value = ''
    }
    if ((state !== 'found' && state !== 'instrumental') || loadedFor.value === id) return
    // 先显示缓存的,同时照样去取一次(别人可能调过偏移)
    if (lastLyrics?.id === id) {
      lyrics.value = lastLyrics.data
      loadedFor.value = id
    }
    try {
      const data = await fetchLyrics(id)
      if (props.current.id !== id) return
      lyrics.value = data
      loadedFor.value = id
      lastLyrics = { id, data }
    } catch {
      // 下一次轮询再试
    }
  },
  { immediate: true },
)

const lines = computed(() => lyrics.value?.lines ?? [])
const offset = ref(0)
watch(() => lyrics.value?.offset, (o) => { offset.value = o ?? 0 }, { immediate: true })
const follows = computed(() => lines.value.length > 0 && (!!lyrics.value?.aligned || offset.value !== (lyrics.value?.offset ?? 0)))
// 能点歌词跳转时每行是一个按钮(键盘也能用);否则就是普通文字
const seekable = computed(() => props.canSeek && follows.value)

// 当前行:歌词时间 <= 播放位置 - 偏移 的最后一行(提前 0.2 秒亮起,跟听感一致)
const active = computed(() => {
  if (!follows.value) return -1
  const at = (props.previewAt ?? clock.playhead) - offset.value + 0.2
  const ls = lines.value
  let lo = 0
  let hi = ls.length - 1
  let found = -1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    if (ls[mid]![0] <= at) { found = mid; lo = mid + 1 } else hi = mid - 1
  }
  return found
})

// ---- 自动滚动:手动滚过的 4 秒内不抢 ----
const box = ref<HTMLElement | null>(null)
let userScrollAt = 0
function onUserScroll() { userScrollAt = performance.now() }
const reduceMotion = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
function scrollToActive(smooth: boolean) {
  const el = box.value?.querySelector<HTMLElement>(`[data-line="${active.value}"]`)
  if (!box.value || !el) return
  box.value.scrollTo({
    top: el.offsetTop - box.value.clientHeight / 2 + el.clientHeight / 2,
    behavior: smooth && !reduceMotion ? 'smooth' : 'auto',
  })
}
// 键盘焦点在某一行上时也不自动滚:否则聚焦的那行会被滚出框外
function keyboardFocusInside() {
  try {
    return !!box.value?.querySelector(':focus-visible')
  } catch {
    return false  // 不认识 :focus-visible 的旧内核
  }
}
watch(active, () => {
  if (performance.now() - userScrollAt < 4000 || keyboardFocusInside()) return
  nextTick(() => scrollToActive(true))
})
watch([hidden, lyrics], () => nextTick(() => scrollToActive(false)))

function onLineClick(time: number) {
  if (!seekable.value) return
  emit('seek', Math.max(0, time + offset.value))
}

// 每行都是按钮,但只有当前行在 Tab 顺序里(否则要按几十下 Tab 才能离开歌词),
// 行与行之间用 ↑ / ↓ / Home / End 移动焦点
const tabLine = computed(() => Math.max(0, active.value))
function onLineKey(e: KeyboardEvent, i: number) {
  const last = lines.value.length - 1
  let next: number
  if (e.key === 'ArrowDown') next = Math.min(last, i + 1)
  else if (e.key === 'ArrowUp') next = Math.max(0, i - 1)
  else if (e.key === 'Home') next = 0
  else if (e.key === 'End') next = last
  else return
  e.preventDefault()
  box.value?.querySelector<HTMLElement>(`[data-line="${next}"] > .lyr-seek`)?.focus()
}

// ---- 手动调偏移:立即生效,停手 0.6 秒后存到服务器(大家共用) ----
let saveTimer: ReturnType<typeof setTimeout> | undefined
function nudge(delta: number) {
  offset.value = Math.round((offset.value + delta) * 10) / 10
  scheduleSave()
}
function resetOffset() {
  offset.value = 0
  scheduleSave()
}
function scheduleSave() {
  clearTimeout(saveTimer)
  const id = props.current.id
  const value = offset.value
  saveTimer = setTimeout(async () => {
    try {
      const data = await postLyricsOffset(id, value)
      lastLyrics = { id, data }
      if (props.current.id === id) lyrics.value = data
    } catch { /* 保存失败只影响别人,自己这边已经生效 */ }
  }, 600)
}
onBeforeUnmount(() => clearTimeout(saveTimer))

const offsetLabel = computed(() => {
  const o = offset.value
  return t('lyrics.offset', { s: `${o > 0 ? '+' : ''}${o.toFixed(1)}` })
})
const sourceLabel = computed(() => {
  const s = lyrics.value?.source
  return s === 'netease' ? t('lyrics.netease') : s === 'lrclib' ? 'LRCLIB' : s || ''
})
const state = computed(() => props.current.lyrics ?? 'off')
</script>

<template>
  <section
    v-if="state !== 'off' && state !== ''"
    class="w-full max-w-xl"
    :aria-label="t('lyrics.title')"
  >
    <div class="mb-2 flex items-center gap-2 text-xs" :style="{ color: 'var(--c-text-muted)' }">
      <button
        type="button"
        class="lyr-toggle flex min-h-6 cursor-pointer items-center gap-1.5 rounded-md border-0 bg-transparent px-1 py-0.5 text-xs font-medium"
        :style="{ color: 'var(--c-text-muted)' }"
        :aria-expanded="!hidden"
        @click="toggle"
      >
        <Icon icon="chevron-down" class="transition-transform motion-reduce:transition-none" :class="hidden ? '-rotate-90' : ''" />
        {{ t('lyrics.title') }}
      </button>
      <span v-if="sourceLabel && !hidden" class="truncate" :style="{ color: 'var(--c-text-faint)' }">
        {{ t('lyrics.source', { source: sourceLabel }) }}
      </span>
      <div v-if="!hidden && lines.length" class="ml-auto flex items-center gap-1 pointer-coarse:gap-2">
        <span v-if="offset !== 0" class="tabular-nums" :style="{ color: 'var(--c-text-faint)' }">{{ offsetLabel }}</span>
        <!-- name starts with the visible text (label in name, for voice control) and explains it -->
        <button type="button" class="lyr-btn" :title="t('lyrics.earlier')"
                :aria-label="t('common.itemAction', { action: '−0.5s', title: t('lyrics.earlier') })" @click="nudge(-0.5)">−0.5s</button>
        <button type="button" class="lyr-btn" :title="t('lyrics.later')"
                :aria-label="t('common.itemAction', { action: '+0.5s', title: t('lyrics.later') })" @click="nudge(0.5)">+0.5s</button>
        <button v-if="offset !== 0" type="button" class="lyr-btn" @click="resetOffset">{{ t('lyrics.reset') }}</button>
      </div>
    </div>

    <template v-if="!hidden">
      <p v-if="state === 'waiting' || state === 'pending' || (state === 'found' && !lyrics)" class="lyr-note">
        {{ t(state === 'waiting' ? 'lyrics.waiting' : 'lyrics.pending') }}
      </p>
      <p v-else-if="state === 'none'" class="lyr-note">{{ t('lyrics.none') }}</p>
      <p v-else-if="state === 'instrumental'" class="lyr-note">{{ t('lyrics.instrumental') }}</p>

      <template v-else-if="lyrics">
        <p v-if="lines.length && !follows" class="mb-2 text-[11px]" :style="{ color: 'var(--c-text-faint)' }">
          {{ t('lyrics.unaligned') }}
        </p>
        <!-- 渐变遮罩会把滚动框自己的焦点框也盖掉:焦点框画在外层 .lyr-wrap 上 -->
        <div class="lyr-wrap">
          <div
            ref="box"
            class="lyr-box relative h-72 overflow-y-auto px-2 text-center"
            :class="{ 'lyr-box--follow': follows }"
            :tabindex="seekable ? undefined : 0"
            @wheel.passive="onUserScroll"
            @touchmove.passive="onUserScroll"
            @keydown="onUserScroll"
          >
            <div v-if="follows" class="h-28" aria-hidden="true" />
            <template v-if="lines.length">
              <p
                v-for="(line, i) in lines"
                :key="i"
                :data-line="i"
                class="lyr-line"
                :class="{ 'lyr-line--active': i === active, 'lyr-line--past': follows && i < active }"
              >
                <button
                  v-if="seekable"
                  type="button"
                  class="lyr-seek"
                  :tabindex="i === tabLine ? 0 : -1"
                  @click="onLineClick(line[0])"
                  @keydown="onLineKey($event, i)"
                >
                  <span v-if="line[1]">{{ line[1] }}</span>
                  <span v-else aria-hidden="true">♪</span>
                  <span v-if="line[2]" class="lyr-trans">{{ line[2] }}</span>
                </button>
                <template v-else>
                  <span v-if="line[1]">{{ line[1] }}</span>
                  <span v-else aria-hidden="true">♪</span>
                  <span v-if="line[2]" class="lyr-trans">{{ line[2] }}</span>
                </template>
              </p>
            </template>
            <p v-else class="whitespace-pre-line text-sm leading-7" :style="{ color: 'var(--c-text)' }">{{ lyrics.plain }}</p>
            <div v-if="follows" class="h-28" aria-hidden="true" />
          </div>
        </div>
      </template>
    </template>
  </section>
</template>

<style scoped>
.lyr-note {
  margin: 0;
  padding: 0.75rem 0;
  text-align: center;
  font-size: 0.8125rem;
  color: var(--c-text-faint);
}
.lyr-btn {
  position: relative;
  min-block-size: 24px;
  min-inline-size: 24px;
  cursor: pointer;
  border: 0;
  border-radius: var(--radius-s);
  background: var(--c-surface-2);
  color: var(--c-text-muted);
  padding: 0.125rem 0.5rem;
  font-size: 11px;
  font-variant-numeric: tabular-nums;
}
.lyr-btn:hover { color: var(--c-text); }
/* 触屏:按钮外观不变,用伪元素把点击区域上下各扩 10px 到约 44px(左右不扩,避免互相重叠) */
@media (pointer: coarse) {
  .lyr-btn::after, .lyr-toggle::after {
    content: '';
    position: absolute;
    inset: -10px 0;
  }
  .lyr-toggle { position: relative; }
}
.lyr-wrap { border-radius: var(--radius-m); }
.lyr-wrap:has(> .lyr-box:focus-visible) { outline: 2px solid var(--c-accent); outline-offset: 2px; }
/* 不支持 :has() 时退回内描边:两端会被淡出,但中间那段看得见 */
@supports not selector(:has(*)) {
  .lyr-box:focus-visible { outline: 2px solid var(--c-accent); outline-offset: -2px; }
}
.lyr-box {
  scrollbar-width: none;
  overscroll-behavior: contain;
  border-radius: var(--radius-m);
  /* 聚焦的歌词按钮滚进来时别停在两端的淡出带里 */
  scroll-padding-block: 18%;
  -webkit-mask-image: linear-gradient(to bottom, transparent 0, #000 18%, #000 82%, transparent 100%);
  mask-image: linear-gradient(to bottom, transparent 0, #000 18%, #000 82%, transparent 100%);
}
@supports selector(:has(*)) {
  .lyr-box:focus-visible { outline: none; }
}
.lyr-box::-webkit-scrollbar { display: none; }
.lyr-line {
  margin: 0;
  padding: 0.35rem 0;
  font-size: 0.95rem;
  line-height: 1.5;
  color: var(--c-text);
  transition: color 250ms ease, opacity 250ms ease, transform 250ms ease;
}
/* 跟随进度时:当前行最醒目,其余淡一些 */
.lyr-box--follow .lyr-line { color: var(--c-text-muted); opacity: 0.75; }
.lyr-box--follow .lyr-line--past { opacity: 0.5; }
.lyr-box--follow .lyr-line--active {
  color: var(--c-text);
  opacity: 1;
  font-weight: 600;
  transform: scale(1.04);
}
.lyr-box--follow .lyr-line:hover, .lyr-box--follow .lyr-line:has(> .lyr-seek:focus-visible) { opacity: 1; }
/* 整行按钮:去掉按钮外观,样式和普通歌词行一样 */
.lyr-seek {
  display: block;
  inline-size: 100%;
  margin: 0;
  padding: 0;
  border: 0;
  border-radius: var(--radius-s);
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: inherit;
  cursor: pointer;
}
.lyr-seek:focus-visible { outline-offset: -2px; }
.lyr-trans {
  display: block;
  font-size: 0.8rem;
  font-weight: 400;
  color: var(--c-text-muted);
}
@media (prefers-reduced-motion: reduce) {
  .lyr-line { transition: none; }
  .lyr-box--follow .lyr-line--active { transform: none; }
}
</style>
