<script setup lang="ts">
// Activity 被缩成画中画小窗(高度很小)时只显示这一块"动态磁贴":封面、歌名、播放 / 暂停、下一首,
// 底边一条细进度。Metro 风格,强调色铺底;只在 Activity 里出现,网页版不会用到。
import { computed } from 'vue'
import { thumbnailUrl } from '../api'
import { useStatus } from '../composables/useStatus'
import { t } from '../i18n'
import AuthImg from './AuthImg.vue'

const { status, control, progress } = useStatus()
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

function togglePlay() {
  if (!status.value) return
  control({ action: status.value.play ? 'pause' : 'resume' })
}
</script>

<template>
  <div class="mini">
    <div class="mini-cover" :class="{ 'mini-cover--type': !current?.has_thumbnail }" aria-hidden="true">
      <AuthImg
        v-if="current?.has_thumbnail"
        :src="thumbnailUrl(current.id, { version: current.artwork || 'pending' })"
        alt=""
        class="mini-img"
      />
      <span v-else-if="!titlePending" class="mini-word">{{ title }}</span>
    </div>
    <div class="mini-body">
      <p class="mini-title" :title="current?.title">{{ title }}</p>
      <p v-if="artist" class="mini-artist">{{ artist }}</p>
      <div class="mini-ctl">
        <button
          type="button"
          class="mini-btn"
          :title="status?.play ? t('ctl.pause') : t('ctl.play')"
          :aria-label="status?.play ? t('ctl.pause') : t('ctl.play')"
          @click="togglePlay"
        >
          <Icon :icon="status?.play ? 'pause' : 'play'" aria-hidden="true" />
        </button>
        <button
          type="button"
          class="mini-btn"
          :title="t('ctl.skip')"
          :aria-label="t('ctl.skip')"
          @click="control({ action: 'skip' })"
        >
          <Icon icon="forward-step" aria-hidden="true" />
        </button>
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
  background: var(--c-accent);
  color: var(--c-on-accent);
  font-family: var(--m-font);
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
/* 标题换行,不截成一行省略号;小窗里最多三行 */
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
.mini-artist {
  margin: 0.125rem 0 0;
  font-size: 0.8125rem;
  overflow-wrap: anywhere;
}
.mini-ctl {
  display: flex;
  gap: 0.25rem;
  margin-block-start: auto;
  padding-block-start: 0.5rem;
}
.mini-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  inline-size: 2.75rem;
  block-size: 2.75rem;
  border: 0;
  border-radius: 0;
  /* 往 --c-text 那边混:浅色主题变深(白色图标更清楚),深色主题变浅(深色图标更清楚)。
     压黑一层只适合白色图标,深色主题下图标对比会掉到 3:1 以下 */
  background: color-mix(in oklab, var(--c-accent) 78%, var(--c-text));
  color: inherit;
  font-size: 1.25rem;
  cursor: pointer;
  transition: background-color 120ms ease-out;
}
.mini-btn:hover { background: color-mix(in oklab, var(--c-accent) 66%, var(--c-text)); }
/* 强调色底上,默认的强调色焦点框看不见:换成前景色 */
.mini-btn:focus-visible { outline-color: var(--c-on-accent); }
@media (prefers-reduced-motion: no-preference) {
  .mini-btn { transition: background-color 120ms ease-out, scale 120ms ease-out; }
  .mini-btn:active { scale: 0.94; }
}
.mini-progress {
  position: absolute;
  inset: auto 0 0;
  block-size: 3px;
  background: color-mix(in oklab, var(--c-accent) 66%, var(--c-text));
}
.mini-fill {
  block-size: 100%;
  background: var(--c-on-accent);
  transform-origin: left center;
  transition: transform 250ms linear;
}
@media (forced-colors: active) {
  .mini-btn { border: 1px solid ButtonText; }
  .mini-fill { forced-color-adjust: none; background: CanvasText; }
}
</style>
