<script setup lang="ts">
// Activity 被缩成画中画小窗(高度很小)时只显示这一块"动态磁贴":封面、歌名、正在唱的歌词,底边一条细进度。
// Discord 的画中画小窗点不进去,所以这里没有按钮。底色按专辑封面取(Monet 的取色,见 useArtColor),
// 没有封面或取不到时用强调色。只在 Activity 里出现,网页版不会用到。
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { thumbnailUrl } from '../api'
import { useStatus } from '../composables/useStatus'
import { useSyncedLyrics } from '../composables/useSyncedLyrics'
import { paletteFor, renderedDark, sourceColorOf } from '../composables/useArtColor'
import { t } from '../i18n'
import AuthImg from './AuthImg.vue'

const { status, progress } = useStatus()
const current = computed(() => status.value?.current ?? null)
// 还在读取标题时 title 是原始链接:显示"正在读取标题…",不把链接排成大字
const titlePending = computed(() => !!status.value?.prep && /^https?:\/\//.test(current.value?.title ?? ''))
const title = computed(() =>
  titlePending.value
    ? t('np.loadingTitle')
    : (current.value?.track || current.value?.title || t('np.nothing')))
const artist = computed(() => {
  const a = current.value?.artist
  return a && a !== '??' ? a : ''
})
const artSrc = computed(() =>
  current.value?.has_thumbnail ? thumbnailUrl(current.value.id, { version: current.value.artwork || 'pending' }) : '')

// ---- 歌词:只有能跟着播放走的才显示,没有就不占地方 ----
const { lines, active } = useSyncedLyrics(current)
const hasLyrics = computed(() => lines.value.length > 0)
/** 大字那一行:正在唱的;第一句之前就是第一句(淡一点,表示还没到) */
const mainLine = computed(() => {
  const ls = lines.value
  if (!ls.length) return null
  const i = Math.max(0, active.value)
  return { key: i, text: ls[i]![1] || '♪', upcoming: active.value < 0 }
})
/** 小字那一行:有翻译显示翻译,没有就是下一句 */
const subLine = computed(() => {
  const ls = lines.value
  if (!ls.length) return ''
  const i = Math.max(0, active.value)
  if (active.value >= 0 && ls[i]![2]) return ls[i]![2]
  // 下一句:接在大字那一句后面(第一句之前大字已经是第一句了,这里就是第二句)
  return ls[i + 1]?.[1] ?? ''
})

// ---- 按封面取色 ----
const source = ref<number | null>(null)
const dark = ref(renderedDark())
watch(artSrc, () => { source.value = null })
function onArt(e: Event) {
  const img = e.target as HTMLImageElement
  if (!img.naturalWidth || !artSrc.value) return
  source.value = sourceColorOf(img, artSrc.value)
}
// 系统 / 主题换了深浅:同一个主题色重新出一套
const scheme = typeof matchMedia === 'function' ? matchMedia('(prefers-color-scheme: dark)') : null
const themeObserver = typeof MutationObserver !== 'undefined'
  ? new MutationObserver(() => { dark.value = renderedDark() })
  : null
function onScheme() { dark.value = renderedDark() }
scheme?.addEventListener('change', onScheme)
themeObserver?.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme', 'data-theme-default'] })
onBeforeUnmount(() => {
  scheme?.removeEventListener('change', onScheme)
  themeObserver?.disconnect()
})

const tileStyle = computed(() => {
  if (source.value === null) return undefined
  const p = paletteFor(source.value, dark.value)
  return { '--mini-bg': p.bg, '--mini-fg': p.fg, '--mini-accent': p.accent }
})
</script>

<template>
  <div class="mini" :class="{ 'mini--lyrics': hasLyrics }" :style="tileStyle">
    <div class="mini-cover" :class="{ 'mini-cover--type': !current?.has_thumbnail }" aria-hidden="true">
      <AuthImg v-if="artSrc" :src="artSrc" alt="" class="mini-img" @load="onArt" />
      <span v-else-if="!titlePending" class="mini-word">{{ title }}</span>
    </div>
    <div class="mini-body">
      <p class="mini-title" :title="current?.title">{{ title }}</p>
      <p v-if="artist" class="mini-artist">{{ artist }}</p>
      <!-- 换行时整块重挂,向上滑进来(动画在允许动效时才有) -->
      <div v-if="mainLine" :key="mainLine.key" class="mini-lyric">
        <p class="mini-line" :class="{ 'mini-line--upcoming': mainLine.upcoming }">{{ mainLine.text }}</p>
        <p v-if="subLine" class="mini-sub">{{ subLine }}</p>
      </div>
    </div>
    <!-- 播放头每 0.25 秒更新一次:transform 过渡补齐中间 -->
    <div v-if="current?.duration" class="mini-progress" aria-hidden="true">
      <div class="mini-fill" :style="{ transform: `scaleX(${progress})` }" />
    </div>
  </div>
</template>

<style scoped>
.mini {
  position: relative;
  display: flex;
  block-size: 100%;
  overflow: hidden;
  /* 封面取色(没有就是强调色)。底色换的时候慢慢过渡,不是一下跳过去 */
  background: var(--mini-bg, var(--c-accent));
  color: var(--mini-fg, var(--c-on-accent));
  font-family: var(--m-font);
  transition: background-color 600ms ease, color 600ms ease;
}
.mini-cover {
  position: relative;
  flex: none;
  block-size: 100%;
  aspect-ratio: 1;
  max-inline-size: 55%;
  overflow: hidden;
  background: var(--m-tile);
}
.mini-cover--type {
  display: flex;
  align-items: flex-end;
  padding: 0.75rem;
  box-sizing: border-box;
  background: var(--c-bg);
  color: var(--c-text);
}
.mini-img {
  position: absolute;
  inset: 0;
  inline-size: 100%;
  block-size: 100%;
  object-fit: cover;
}
.mini-word {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 4;
  line-clamp: 4;
  overflow: hidden;
  font-family: var(--m-font-display);
  font-size: clamp(1rem, 12vmin, 1.5rem);
  font-weight: 300;
  line-height: 1.08;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  overflow-wrap: anywhere;
}
.mini-body {
  display: flex;
  flex: 1;
  flex-direction: column;
  min-inline-size: 0;
  padding: 0.75rem 0.75rem 0.875rem 0.875rem;
}
/* 标题换行,不截成一行省略号;小窗里最多三行。有歌词时让出地方:两行、小一号 */
.mini-title {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 3;
  line-clamp: 3;
  overflow: hidden;
  margin: 0;
  font-family: var(--m-font-display);
  font-size: 1.25rem;
  font-weight: 300;
  line-height: 1.2;
  text-wrap: balance;
  overflow-wrap: anywhere;
}
.mini--lyrics .mini-title {
  -webkit-line-clamp: 2;
  line-clamp: 2;
  font-size: 1rem;
}
.mini-artist {
  margin: 0.125rem 0 0;
  font-size: 0.8125rem;
  overflow-wrap: anywhere;
}
.mini--lyrics .mini-artist {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 1;
  line-clamp: 1;
  overflow: hidden;
  font-size: 0.75rem;
}

/* ---- 歌词:贴在下面,大字是正在唱的,小字是翻译或下一句 ---- */
.mini-lyric {
  margin-block-start: auto;
  padding-block-start: 0.375rem;
  min-inline-size: 0;
}
.mini-line {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  overflow: hidden;
  margin: 0;
  font-size: 1.0625rem;
  font-weight: 600;
  line-height: 1.25;
  text-wrap: balance;
  overflow-wrap: anywhere;
}
.mini-line--upcoming { font-weight: 400; }
.mini-sub {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 1;
  line-clamp: 1;
  overflow: hidden;
  margin: 0.125rem 0 0;
  font-size: 0.75rem;
  line-height: 1.3;
  overflow-wrap: anywhere;
}
@media (prefers-reduced-motion: no-preference) {
  /* 换行:新的一句从下面滑上来,Metro 式的快起慢停 */
  .mini-lyric {
    animation: mini-line-in 360ms cubic-bezier(0.1, 0.9, 0.2, 1) both;
  }
}
@keyframes mini-line-in {
  from {
    opacity: 0;
    translate: 0 0.75rem;
  }
}

.mini-progress {
  position: absolute;
  inset: auto 0 0;
  block-size: 3px;
  background: color-mix(in oklab, var(--mini-fg, var(--c-on-accent)) 28%, transparent);
}
.mini-fill {
  block-size: 100%;
  background: var(--mini-fg, var(--c-on-accent));
  transform-origin: left center;
  transition: transform 250ms linear;
}
@media (forced-colors: active) {
  .mini-fill { forced-color-adjust: none; background: CanvasText; }
}
</style>
