<script setup lang="ts">
// 平铺风格的进度条:点击 / 拖动跳转,键盘 ←/→/↑/↓ 5 秒、PgUp/PgDn 30 秒、Home/End。
// 和 NowPlaying 的进度条同一套做法:外层 div 处理指针(iOS 上原生 range 只能按住滑块拖),
// 盖在上面的透明原生 range 只给键盘和读屏用。
import { computed, ref } from 'vue'
import { formatTime, useStatus } from '../composables/useStatus'
import { t } from '../i18n'
import { useSeek } from './seek'

const { status, clock } = useStatus()
const { dragAt, duration, canSeek, shownPlayhead, clampSeek, seek, scheduleSeek } = useSeek()
const current = computed(() => status.value?.current ?? null)

const progress = computed(() =>
  duration.value ? Math.min(1, Math.max(0, shownPlayhead.value / duration.value)) : 0)

const bar = ref<HTMLElement | null>(null)
let dragging = false
function secondsAt(e: PointerEvent) {
  const r = bar.value!.getBoundingClientRect()
  return Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)) * duration.value
}
function onPointerDown(e: PointerEvent) {
  if (!canSeek.value || e.button !== 0) return
  bar.value!.setPointerCapture(e.pointerId)
  dragging = true
  dragAt.value = secondsAt(e)
  e.preventDefault()
}
function onPointerMove(e: PointerEvent) {
  if (dragging && bar.value!.hasPointerCapture(e.pointerId)) dragAt.value = secondsAt(e)
}
function onPointerUp(e: PointerEvent) {
  if (!dragging || !bar.value!.hasPointerCapture(e.pointerId)) return
  dragging = false
  if (dragAt.value !== null) void seek(dragAt.value)
}
function onPointerCancel() {
  dragging = false
  dragAt.value = null
}

function onKey(e: KeyboardEvent) {
  if (!canSeek.value) return
  const step = { ArrowLeft: -5, ArrowDown: -5, ArrowRight: 5, ArrowUp: 5, PageDown: -30, PageUp: 30 }[e.key]
  let target: number
  if (e.key === 'Home') target = 0
  else if (e.key === 'End') target = duration.value - 1
  else if (step !== undefined) target = (dragAt.value ?? clock.playhead) + step
  else return
  e.preventDefault()
  scheduleSeek(clampSeek(target))
}

// 聚焦期间原生 range 的值不跟着播放头每秒变,否则读屏会一直播报
const focused = ref(false)
const frozenAt = ref(0)
const sliderValue = computed(() => Math.round(dragAt.value ?? (focused.value ? frozenAt.value : clock.playhead)))
function onFocus() {
  frozenAt.value = clock.playhead
  focused.value = true
}
function onInput(e: Event) {
  const el = e.target as HTMLInputElement
  const delta = Number(el.value) - sliderValue.value
  if (!delta) return
  const base = dragAt.value ?? clock.playhead
  const target = clampSeek(base + (Math.abs(delta) < 5 ? Math.sign(delta) * 5 : delta))
  scheduleSeek(target)
  el.value = String(Math.round(target))
}

const skipBlocks = computed(() => {
  const d = duration.value
  if (!d) return []
  return (current.value?.skip_segments ?? []).map(([start, end]) => ({
    start, end, left: (start / d) * 100, width: (Math.min(end, d) - start) / d * 100,
  }))
})
</script>

<template>
  <div v-if="current" class="ms">
    <div
      ref="bar"
      class="ms-hit"
      :class="{ 'ms-hit--seek': canSeek }"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerCancel"
    >
      <div class="ms-track">
        <div
          v-if="current.download"
          class="ms-buffer"
          :style="{ transform: `scaleX(${current.download.progress})` }"
        />
        <!-- 播放头每 0.25 秒更新一次:transform 过渡补齐中间,不触发 layout -->
        <div
          class="ms-fill"
          :style="{
            transform: `scaleX(${progress})`,
            transition: dragAt === null ? 'transform 250ms linear' : 'none',
          }"
        />
        <div
          v-for="(b, i) in skipBlocks"
          :key="i"
          class="ms-skip"
          :style="{ left: `${b.left}%`, width: `${b.width}%` }"
          :title="t('np.skipped', { from: formatTime(b.start), to: formatTime(b.end) })"
        />
      </div>
      <input
        v-if="canSeek"
        type="range"
        class="ms-input"
        min="0"
        :max="Math.max(1, Math.round(duration))"
        step="1"
        :value="sliderValue"
        :aria-label="t('np.seek')"
        :aria-valuetext="t('np.seekValue', { at: formatTime(sliderValue), total: formatTime(duration) })"
        @focus="onFocus"
        @blur="focused = false"
        @keydown="onKey"
        @input="onInput"
      />
    </div>
    <div class="ms-times" aria-hidden="true">
      <span>{{ formatTime(shownPlayhead) }}</span>
      <span>{{ current.duration ? formatTime(current.duration) : '--:--' }}</span>
    </div>
  </div>
</template>

<style scoped>
.ms { inline-size: 100%; }
/* 命中区域 24px(触屏 44px),用负外边距抵消多出来的高度 */
.ms-hit {
  position: relative;
  display: flex;
  align-items: center;
  block-size: 24px;
  margin-block: -10px;
}
.ms-hit--seek { cursor: pointer; touch-action: pan-y; }
@media (pointer: coarse) {
  .ms-hit { block-size: 44px; margin-block: -20px; }
}
.ms-track {
  position: relative;
  inline-size: 100%;
  block-size: 4px;
  overflow: hidden;
  background: var(--m-track);
}
.ms-buffer,
.ms-fill {
  position: absolute;
  inset: 0;
  transform-origin: left center;
}
.ms-buffer { background: var(--m-track); transition: transform 800ms linear; }
.ms-fill { background: var(--c-text); }
.ms-skip {
  position: absolute;
  inset-block: 0;
  background: repeating-linear-gradient(135deg, var(--c-text-muted) 0 3px, transparent 3px 6px);
}
.ms-hit--seek:hover .ms-track,
.ms-hit:has(.ms-input:focus-visible) .ms-track { block-size: 6px; }
.ms-input {
  position: absolute;
  inset: 0;
  inline-size: 100%;
  block-size: 100%;
  margin: 0;
  padding: 0;
  border: 0;
  appearance: none;
  background: transparent;
  pointer-events: none;
}
.ms-input::-webkit-slider-runnable-track { background: transparent; border: 0; }
.ms-input::-webkit-slider-thumb { appearance: none; inline-size: 0; block-size: 0; border: 0; }
.ms-input::-moz-range-track { background: transparent; border: 0; }
.ms-input::-moz-range-thumb { inline-size: 0; block-size: 0; border: 0; background: transparent; }
.ms-input:focus-visible { outline: 2px solid var(--c-accent); outline-offset: 0; }
.ms-times {
  display: flex;
  justify-content: space-between;
  margin-block-start: 0.375rem;
  font-size: 0.8125rem;
  font-variant-numeric: tabular-nums;
  color: var(--c-text-muted);
}
@media (forced-colors: active) {
  /* 背景色会被系统色替换:进度本身是信息,用系统色画出来 */
  .ms-track { border: 1px solid CanvasText; }
  .ms-fill { forced-color-adjust: none; background: Highlight; }
}
</style>
