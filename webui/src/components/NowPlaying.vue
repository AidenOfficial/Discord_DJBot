<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { formatBytes, postControls, thumbnailUrl } from '../api'
import Controls from './Controls.vue'
import AuthImg from './AuthImg.vue'
import AddToPlaylist from './AddToPlaylist.vue'
import FavButton from './FavButton.vue'
import PrepPanel from './PrepPanel.vue'
import LyricsPanel from './LyricsPanel.vue'
import { formatTime, useStatus } from '../composables/useStatus'
import { announce } from '../composables/useAnnounce'
import { modeLabel, t, typeLabel } from '../i18n'

const { status, error, clock, syncedAt, applyStatus } = useStatus()

const current = computed(() => status.value?.current ?? null)

// Only swap the artwork when the song (or its artwork source) actually changes,
// so the <img> does not flicker on every poll. 来源从 '' 变成 album/video 时
// 地址跟着变,浏览器就会换上高清图。
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

// ---- 进度条拖动 ----
const duration = computed(() => current.value?.duration || 0)
const canSeek = computed(() => duration.value > 0)
const bar = ref<HTMLElement | null>(null)
const dragAt = ref<number | null>(null)   // 拖动 / 键盘调整中的目标位置(秒)
const hoverAt = ref<number | null>(null)
const seekingSince = ref(0)                // 刚跳转:ffmpeg 重启的那一下不闪准备面板
const shownPlayhead = computed(() => dragAt.value ?? clock.playhead)
const shownProgress = computed(() =>
  duration.value ? Math.min(1, Math.max(0, shownPlayhead.value / duration.value)) : 0)

function secondsAt(e: PointerEvent) {
  const r = bar.value!.getBoundingClientRect()
  return Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)) * duration.value
}
function onPointerDown(e: PointerEvent) {
  if (!canSeek.value || e.button !== 0) return
  bar.value!.setPointerCapture(e.pointerId)
  dragAt.value = secondsAt(e)
  e.preventDefault()
}
function onPointerMove(e: PointerEvent) {
  if (!canSeek.value) return
  if (dragAt.value !== null && bar.value!.hasPointerCapture(e.pointerId)) dragAt.value = secondsAt(e)
  else hoverAt.value = secondsAt(e)
}
function onPointerUp(e: PointerEvent) {
  if (dragAt.value === null || !bar.value!.hasPointerCapture(e.pointerId)) return
  const target = dragAt.value
  seek(target)
}
function onPointerCancel() {
  dragAt.value = null
}

function clampSeek(seconds: number) {
  return Math.min(Math.max(0, duration.value - 1), Math.max(0, seconds))
}

// 键盘和读屏手势都只更新 dragAt,停下来 0.4 秒再真正跳转(每次跳转都要重启 ffmpeg)
let keyTimer: ReturnType<typeof setTimeout> | undefined
function scheduleSeek(target: number) {
  dragAt.value = target
  clearTimeout(keyTimer)
  keyTimer = setTimeout(() => dragAt.value !== null && seek(dragAt.value), 400)
}

function onKey(e: KeyboardEvent) {
  if (!canSeek.value) return
  const step = { ArrowLeft: -5, ArrowDown: -5, ArrowRight: 5, ArrowUp: 5, PageDown: -30, PageUp: 30 }[e.key]
  let target: number
  if (e.key === 'Home') target = 0
  else if (e.key === 'End') target = duration.value - 1
  else if (step !== undefined) target = (dragAt.value ?? clock.playhead) + step
  else return
  e.preventDefault()  // 自己按 5 / 30 秒一步,不用原生 range 的 1 秒
  scheduleSeek(clampSeek(target))
}

// 原生 range 只负责键盘焦点和读屏(指针由外层 div 处理):聚焦期间它的值不再每秒跟着
// 播放头变,否则读屏会每秒播报一次。读屏的增减手势按 ±5 秒算,以实际播放位置为基准。
const seekFocused = ref(false)
const frozenAt = ref(0)
const sliderValue = computed(() =>
  Math.round(dragAt.value ?? (seekFocused.value ? frozenAt.value : clock.playhead)))
function onSeekFocus() {
  frozenAt.value = clock.playhead
  seekFocused.value = true
}
function onSeekInput(e: Event) {
  const el = e.target as HTMLInputElement
  const delta = Number(el.value) - sliderValue.value
  if (!delta) return
  const base = dragAt.value ?? clock.playhead
  const target = clampSeek(base + (Math.abs(delta) < 5 ? Math.sign(delta) * 5 : delta))
  scheduleSeek(target)
  // 夹到两端时 sliderValue 可能没变,Vue 不会改写 DOM:手动对齐,下一次的增量才算得对
  el.value = String(Math.round(target))
}

async function seek(position: number) {
  clearTimeout(keyTimer)
  seekingSince.value = performance.now()
  clock.playhead = position
  frozenAt.value = position
  try {
    applyStatus(await postControls({ action: 'seek', position }))
  } catch {
    // 直播 / 已经切歌:下一次轮询会带回真实位置
  } finally {
    dragAt.value = null
  }
}

const showPrep = computed(() => {
  if (!current.value || !status.value?.prep) return false
  // 跳转后几秒内的"准备中"只是 ffmpeg 在重新打开文件,别把进度条换成准备面板
  return !seekingSince.value || performance.now() - seekingSince.value > 4000
})
watch(() => status.value?.prep, (prep) => {
  if (!prep) seekingSince.value = 0
})
watch(() => current.value?.id, () => {
  dragAt.value = null
  seekingSince.value = 0
})

const titlePending = computed(() =>
  !!status.value?.prep && /^https?:\/\//.test(current.value?.title ?? ''))

const skipBlocks = computed(() => {
  const d = current.value?.duration || 0
  if (!d) return []
  return (current.value?.skip_segments ?? []).map(([start, end]) => ({
    start, end, left: (start / d) * 100, width: (Math.min(end, d) - start) / d * 100,
  }))
})

// 匹配到专辑时标题用曲库的正式歌名,完整的视频标题放到悬停提示里
const displayTitle = computed(() => current.value?.track || current.value?.title || '')
// 单曲的专辑名常常就是歌名:和标题重复时不再显示
const showAlbum = computed(() => {
  const album = current.value?.album?.trim().toLowerCase()
  return !!album && album !== displayTitle.value.trim().toLowerCase()
})

const sourceLabel = computed(() => typeLabel(current.value?.type ?? ''))

const notInVoice = computed(() => !!status.value && !status.value.voice_channel)
watch(notInVoice, (now) => {
  if (now) announce(t('np.notInVoice'))
})
watch(error, (e) => {
  if (e) announce(t('np.unreachable', { error: e }), { assertive: true })
})
</script>

<template>
  <section class="mx-auto flex w-full max-w-3xl flex-col items-center gap-6 px-4 py-8 sm:py-14">
    <!-- bot 不在语音频道里:播放进度照走,但没人听得到 -->
    <p
      v-if="notInVoice"
      class="w-full rounded-xl px-3 py-2 text-sm"
      :style="{ background: 'var(--c-accent-soft)', color: 'var(--c-text)' }"
    ><Icon icon="triangle-exclamation" class="mr-1.5" :style="{ color: 'var(--c-accent)' }" />{{ t('np.notInVoice') }}</p>
    <!-- artwork -->
    <div
      class="relative aspect-square w-56 overflow-hidden sm:w-72"
      :style="{ borderRadius: 'var(--radius-l)', boxShadow: 'var(--shadow-2)' }"
    >
      <template v-if="artSrc">
        <!-- 视频封面是 16:9:整张放进方框,后面垫一层同图的模糊放大版 -->
        <AuthImg
          v-if="artKind === 'video'"
          :src="artSrc"
          alt=""
          aria-hidden="true"
          class="absolute inset-0 h-full w-full scale-125 object-cover opacity-80 blur-2xl"
        />
        <!-- 高清图还没准备好时服务器先给 100px 小图:模糊着显示,别拉伸出马赛克 -->
        <AuthImg
          :src="artSrc"
          alt=""
          fetchpriority="high"
          class="relative h-full w-full transition-[filter] duration-500"
          :class="[artKind === 'video' ? 'object-contain' : 'object-cover', artKind ? '' : 'scale-110 blur-xl']"
        />
      </template>
      <div
        v-else
        class="flex h-full w-full items-center justify-center"
        :style="{ background: 'linear-gradient(135deg, var(--c-accent-soft), var(--c-surface-2))' }"
      >
        <Icon icon="music" class="text-7xl opacity-40" aria-hidden="true" />
      </div>
    </div>

    <!-- title / source -->
    <div class="flex w-full flex-col items-center gap-1 text-center">
      <template v-if="current">
        <!-- 还在读取信息时标题就是链接本身:先显示占位,链接用小字 -->
        <template v-if="titlePending">
          <h1 class="max-w-full text-xl font-semibold text-balance sm:text-2xl" :style="{ color: 'var(--c-text-muted)' }">
            {{ t('np.loadingTitle') }}
          </h1>
          <p class="max-w-full truncate text-xs" :style="{ color: 'var(--c-text-faint)' }">{{ current.title }}</p>
        </template>
        <!-- 标题最多两行,不截成一行省略号:触屏上看不到 title 提示 -->
        <h1 v-else class="line-clamp-2 max-w-full text-xl font-semibold text-balance [overflow-wrap:anywhere] sm:text-2xl" :title="current.title">
          {{ displayTitle || t('common.untitled') }}
        </h1>
        <p class="flex items-center gap-2 text-sm" :style="{ color: 'var(--c-text-muted)' }">
          <span
            class="rounded-full px-2 py-0.5 text-xs font-medium"
            :style="{ background: 'var(--c-accent-soft)', color: 'var(--c-accent)' }"
          >{{ sourceLabel }}</span>
          <span v-if="current.artist && current.artist !== '??'">{{ current.artist }}</span>
          <span v-if="showAlbum" class="hidden max-w-48 truncate sm:inline" :title="current.album">· {{ current.album }}</span>
          <span
            v-if="current.requester"
            class="max-w-40 truncate text-xs"
            :style="{ color: 'var(--c-text-faint)' }"
            :title="t('queue.requestedBy', { name: current.requester })"
          ><Icon icon="user" class="mr-1" />{{ current.requester }}</span>
          <FavButton :item-id="current.id" :source="{ source: 'library', item_id: current.id }" :label="t('np.save')" />
          <AddToPlaylist :source="{ source: 'current' }" :label="t('atp.header')" />
        </p>
      </template>
      <template v-else>
        <h1 class="text-xl font-semibold sm:text-2xl" :style="{ color: 'var(--c-text-muted)' }">
          {{ t('np.nothing') }}
        </h1>
        <p class="text-sm" :style="{ color: 'var(--c-text-faint)' }">
          {{ t('np.emptyHint') }}
        </p>
      </template>
    </div>

    <!-- 还没出声:显示在等什么、还要多久 -->
    <PrepPanel v-if="showPrep && status?.prep" :prep="status.prep" :synced-at="syncedAt" />

    <!-- progress:点击或拖动跳转,键盘 ←/→/↑/↓ 5 秒、PgUp/PgDn 30 秒、Home/End -->
    <div v-else-if="current" class="w-full max-w-xl">
      <!-- 外层 div 处理指针(iOS 上原生 range 只能按住滑块本身拖)。命中区域 24px,
           触屏 44px,用负外边距抵消多出的高度,版面不变 -->
      <div
        ref="bar"
        class="seek-bar group relative flex h-6 w-full items-center pointer-coarse:-my-2.5 pointer-coarse:h-11"
        :class="canSeek ? 'cursor-pointer touch-pan-y' : ''"
        @pointerdown="onPointerDown"
        @pointermove="onPointerMove"
        @pointerup="onPointerUp"
        @pointercancel="onPointerCancel"
        @pointerleave="hoverAt = null"
      >
        <div
          class="relative h-1.5 w-full overflow-hidden rounded-full transition-[height] duration-150 group-has-[:focus-visible]:h-2"
          :class="canSeek ? 'group-hover:h-2' : ''"
          :style="{ background: 'var(--c-surface-2)' }"
        >
          <!-- 边下边播时已经下载到的位置(像视频网站的缓冲条) -->
          <div
            v-if="current.download"
            class="absolute inset-y-0 left-0 rounded-full"
            :style="{ width: `${current.download.progress * 100}%`, background: 'var(--c-accent-soft)', transition: 'width 800ms linear' }"
          />
          <!-- 播放头每 0.25 秒更新一次:用 transform 过渡补齐中间,不触发 layout -->
          <div
            class="absolute inset-0 rounded-full"
            :style="{
              transform: `translateX(${(shownProgress - 1) * 100}%)`,
              background: 'var(--c-accent)',
              transition: dragAt === null ? 'transform 250ms linear' : 'none',
            }"
          />
          <!-- SponsorBlock 会跳过的片段 -->
          <div
            v-for="(b, i) in skipBlocks"
            :key="i"
            class="absolute inset-y-0"
            :style="{ left: `${b.left}%`, width: `${b.width}%`, background: 'repeating-linear-gradient(135deg, var(--c-decor) 0 3px, transparent 3px 6px)', opacity: 0.7 }"
            :title="t('np.skipped', { from: formatTime(b.start), to: formatTime(b.end) })"
          />
        </div>
        <!-- 拖动手柄:悬停 / 拖动 / 键盘聚焦时出现;100cqi 是整条进度条的宽度 -->
        <div
          v-if="canSeek"
          class="pointer-events-none absolute top-1/2 left-0 h-3.5 w-3.5 rounded-full opacity-0 group-hover:opacity-100 group-has-[:focus-visible]:opacity-100"
          :class="dragAt !== null ? 'opacity-100' : ''"
          :style="{
            transform: `translate(calc(${shownProgress} * 100cqi - 50%), -50%)`,
            transition: dragAt === null ? 'opacity 150ms, transform 250ms linear' : 'opacity 150ms',
            background: 'var(--c-accent)',
            boxShadow: 'var(--shadow-2)',
          }"
        />
        <input
          v-if="canSeek"
          type="range"
          class="seek-input"
          min="0"
          :max="Math.max(1, Math.round(duration))"
          step="1"
          :value="sliderValue"
          :aria-label="t('np.seek')"
          :aria-valuetext="t('np.seekValue', { at: formatTime(sliderValue), total: formatTime(duration) })"
          @focus="onSeekFocus"
          @blur="seekFocused = false"
          @keydown="onKey"
          @input="onSeekInput"
        />
        <!-- 悬停 / 拖动时显示目标时间 -->
        <div
          v-if="canSeek && (dragAt ?? hoverAt) !== null"
          class="pointer-events-none absolute -top-6 -translate-x-1/2 rounded px-1.5 py-0.5 text-[11px] tabular-nums"
          :style="{ left: `${((dragAt ?? hoverAt)! / duration) * 100}%`, background: 'var(--c-surface-2)', color: 'var(--c-text)', boxShadow: 'var(--shadow-2)' }"
          aria-hidden="true"
        >{{ formatTime((dragAt ?? hoverAt)!) }}</div>
      </div>
      <div class="mt-1.5 flex justify-between text-xs tabular-nums" :style="{ color: 'var(--c-text-muted)' }">
        <span>{{ formatTime(shownPlayhead) }}</span>
        <span>{{ current.duration ? formatTime(current.duration) : '--:--' }}</span>
      </div>
      <p v-if="current.download" class="mt-1 text-center text-[11px] tabular-nums" :style="{ color: 'var(--c-text-faint)' }">
        <Icon icon="download" class="mr-1" />{{ t('np.bgDownload', { pct: Math.round(current.download.progress * 100) }) }}<template
          v-if="current.download.speed"> · {{ formatBytes(current.download.speed) }}/s</template><template
          v-if="current.download.eta"> · {{ t('np.bgDone', { eta: formatTime(current.download.eta) }) }}</template>
      </p>
      <p v-if="skipBlocks.length" class="mt-1 text-center text-[11px]" :style="{ color: 'var(--c-text-faint)' }">
        <Icon icon="forward-step" class="mr-1" />{{ t('np.skipping', { n: skipBlocks.length }) }}
      </p>
    </div>

    <!-- controls -->
    <Controls />

    <!-- 歌词(lyrics_lookup 打开时才有) -->
    <LyricsPanel v-if="current" :current="current" :preview-at="dragAt" :can-seek="canSeek" @seek="seek" />

    <!-- queue summary -->
    <p v-if="status && !status.empty" class="text-sm" :style="{ color: 'var(--c-text-muted)' }">
      {{ t('np.summary', { n: status.queue_length, mode: modeLabel(status.mode) }) }}
      <span v-if="!status.play" :style="{ color: 'var(--c-accent)' }"> · {{ t('np.paused') }}</span>
    </p>

    <p v-if="error" class="rounded-md px-3 py-2 text-sm" :style="{ background: 'var(--c-accent-soft)', color: 'var(--c-danger)' }">
      {{ t('np.unreachable', { error }) }}
    </p>
  </section>
</template>

<style scoped>
/* 进度条是尺寸容器:手柄用 100cqi(整条的宽度)换算位置 */
.seek-bar { container-type: inline-size; }
/* 透明的原生 range 盖满命中区域:只给键盘和读屏用,外观和指针交给上面几层 */
.seek-input {
  position: absolute;
  inset: 0;
  inline-size: 100%;
  block-size: 100%;
  margin: 0;
  padding: 0;
  border: 0;
  border-radius: 9999px;
  appearance: none;
  background: transparent;
  pointer-events: none;
}
.seek-input::-webkit-slider-runnable-track { background: transparent; border: 0; }
.seek-input::-webkit-slider-thumb { appearance: none; inline-size: 0; block-size: 0; border: 0; }
.seek-input::-moz-range-track { background: transparent; border: 0; }
.seek-input::-moz-range-thumb { inline-size: 0; block-size: 0; border: 0; background: transparent; }
.seek-input:focus-visible { outline: 2px solid var(--c-accent); outline-offset: 2px; }
</style>
