<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useStatus } from '../composables/useStatus'
import { modeLabel, t } from '../i18n'

const { status, control } = useStatus()

const volume = ref(0.5)
let volumeDragging = false
watch(
  () => status.value?.volume,
  (v) => {
    if (v !== undefined && !volumeDragging) volume.value = v
  },
  { immediate: true },
)

let volumeTimer: ReturnType<typeof setTimeout> | undefined
function onVolumeInput() {
  volumeDragging = true
  clearTimeout(volumeTimer)
  volumeTimer = setTimeout(() => {
    control({ action: 'volume', volume: volume.value })
    volumeDragging = false
  }, 150)
}

function togglePlay() {
  if (!status.value) return
  control({ action: status.value.play ? 'pause' : 'resume' })
}

const MODES = ['one-shot', 'repeat', 'single', 'random', 'autoplay']

// 单选组:只有选中的那个在 Tab 顺序里,方向键 / Home / End 在组内移动并直接选中
const modeEls: (HTMLButtonElement | null)[] = []
const tabbableMode = computed(() => Math.max(0, MODES.indexOf(status.value?.mode ?? '')))
function onModeKey(e: KeyboardEvent, i: number) {
  const step = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key]
  let next: number
  if (step !== undefined) next = (i + step + MODES.length) % MODES.length
  else if (e.key === 'Home') next = 0
  else if (e.key === 'End') next = MODES.length - 1
  else return
  e.preventDefault()
  modeEls[next]?.focus()
  control({ action: 'mode', mode: MODES[next]! })
}
</script>

<template>
  <div class="flex w-full max-w-xl flex-col items-center gap-5">
    <!-- transport -->
    <div class="flex items-center gap-4">
      <button
        class="flex h-14 w-14 cursor-pointer items-center justify-center rounded-full border-0"
        :style="{ background: 'var(--c-accent)', color: 'var(--c-on-accent)', boxShadow: 'var(--shadow-1)' }"
        :title="status?.play ? t('ctl.pause') : t('ctl.play')"
        :aria-label="status?.play ? t('ctl.pause') : t('ctl.play')"
        @click="togglePlay"
      >
        <Icon :icon="status?.play ? 'pause' : 'play'" class="text-xl" :class="{ 'translate-x-px': !status?.play }" />
      </button>
      <button
        class="flex h-11 w-11 cursor-pointer items-center justify-center rounded-full border-0"
        :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
        :title="t('ctl.skip')"
        :aria-label="t('ctl.skip')"
        @click="control({ action: 'skip' })"
      >
        <Icon icon="forward-step" class="text-lg" />
      </button>
    </div>

    <!-- volume -->
    <div class="flex w-full max-w-xs items-center gap-3">
      <Icon icon="volume-low" class="shrink-0 text-sm" :style="{ color: 'var(--c-text-muted)' }" />
      <input
        v-model.number="volume"
        type="range"
        min="0"
        max="1"
        step="0.01"
        class="volume-slider w-full"
        :aria-label="t('ctl.volume')"
        :aria-valuetext="`${Math.round(volume * 100)}%`"
        @input="onVolumeInput"
      />
      <span class="w-8 text-right text-xs tabular-nums" :style="{ color: 'var(--c-text-muted)' }" aria-hidden="true">
        {{ Math.round(volume * 100) }}
      </span>
    </div>

    <!-- mode -->
    <div
      class="flex max-w-full gap-1 overflow-x-auto rounded-full p-1"
      :style="{ background: 'var(--c-surface-2)' }"
      role="radiogroup"
      :aria-label="t('ctl.mode')"
    >
      <button
        v-for="(m, i) in MODES"
        :key="m"
        :ref="(el) => { modeEls[i] = el as HTMLButtonElement | null }"
        type="button"
        class="mode-btn min-h-6 shrink-0 cursor-pointer rounded-full border-0 px-2 py-1 text-xs font-medium whitespace-nowrap capitalize pointer-coarse:min-h-11 sm:px-3"
        :style="status?.mode === m
          ? { background: 'var(--c-accent)', color: 'var(--c-on-accent)' }
          : { background: 'transparent', color: 'var(--c-text-muted)' }"
        role="radio"
        :aria-checked="status?.mode === m"
        :tabindex="i === tabbableMode ? 0 : -1"
        @click="control({ action: 'mode', mode: m })"
        @keydown="onModeKey($event, i)"
      >{{ modeLabel(m) }}</button>
    </div>
  </div>
</template>

<style scoped>
/* 外观自己画:input 本身是透明的 24px(触屏 44px)命中区域,4px 的轨道画在伪元素上 */
.volume-slider {
  --slider-track-size: 4px;
  --slider-thumb-size: 14px;
  appearance: none;
  block-size: 24px;
  margin: 0;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
}
@media (pointer: coarse) {
  /* 负外边距抵消多出的高度,这一行的版面不变 */
  .volume-slider { block-size: 44px; margin-block: -10px; }
}
.volume-slider:focus-visible {
  outline: 2px solid var(--c-accent);
  outline-offset: 4px;
}
/* WebKit / Blink 和 Firefox 的伪元素分开写:写在一条规则里,不认识的那个会让整条失效 */
.volume-slider::-webkit-slider-runnable-track {
  block-size: var(--slider-track-size);
  border: 0;
  border-radius: 2px;
  background: var(--c-surface-2);
}
.volume-slider::-webkit-slider-thumb {
  appearance: none;
  block-size: var(--slider-thumb-size);
  inline-size: var(--slider-thumb-size);
  margin-block-start: calc((var(--slider-track-size) - var(--slider-thumb-size)) / 2);
  border: 0;
  border-radius: 50%;
  background: var(--c-accent);
}
.volume-slider::-moz-range-track {
  block-size: var(--slider-track-size);
  border: 0;
  border-radius: 2px;
  background: var(--c-surface-2);
}
.volume-slider::-moz-range-thumb {
  block-size: var(--slider-thumb-size);
  inline-size: var(--slider-thumb-size);
  border: 0;
  border-radius: 50%;
  background: var(--c-accent);
}
/* 模式条可以横向滚动,会裁掉外描边:焦点框画在按钮里面;选中的按钮底色就是强调色,换成对比色 */
.mode-btn:focus-visible { outline-offset: -2px; }
.mode-btn[aria-checked='true']:focus-visible { outline-color: var(--c-on-accent); }
</style>
