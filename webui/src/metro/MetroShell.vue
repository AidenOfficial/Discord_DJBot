<script setup lang="ts" generic="V extends string">
// Activity 里的外壳(Metro 风格):一行小字的位置信息(服务器 · bot 所在语音频道、当前用户、
// 主题 / 语言),下面一排大号细体的视图名(pivot)。视图名放不下时横向滚动,选中的那个总在可见范围里。
// 这是页面导航,不是选项卡:<nav> + 按钮 + aria-current="page",都在 Tab 顺序里,不拦方向键。
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import UserChip from '../components/UserChip.vue'
import { useGuilds } from '../composables/useGuilds'
import { useStatus } from '../composables/useStatus'
import { t } from '../i18n'

const props = defineProps<{
  views: readonly V[]
  view: V
  label: (v: V) => string
  /** 内容自己管理滚动(正在播放页):主区域不滚动,子元素铺满 */
  fill?: boolean
}>()
const emit = defineEmits<{ select: [view: V] }>()

const { currentGuild } = useGuilds()
const { status } = useStatus()
const guildName = computed(() => currentGuild.value?.name || t('guild.label'))
const voiceName = computed(() => status.value?.voice_channel?.name ?? '')

const scroller = ref<HTMLElement | null>(null)
const main = ref<HTMLElement | null>(null)

function currentButton() {
  return scroller.value?.querySelector<HTMLElement>('[aria-current="page"]') ?? null
}
// 选中的视图名完整露出来:container: 'nearest' 只滚这一排,不认识的浏览器会忽略它
function reveal() {
  currentButton()?.scrollIntoView({ block: 'nearest', inline: 'nearest', container: 'nearest' } as ScrollIntoViewOptions)
}
watch(() => props.view, () => { void nextTick(reveal) })

/** 内容里的磁贴切换了视图(原来的按钮随之消失):焦点交给新选中的视图名 */
function focusCurrent() {
  void nextTick(() => currentButton()?.focus())
}
defineExpose({ main, focusCurrent })

// 不支持滚动驱动动画时,用 IntersectionObserver 判断两端还有没有被遮住的视图名
let edgeObserver: IntersectionObserver | null = null
onMounted(() => {
  reveal()
  const el = scroller.value
  if (!el || typeof IntersectionObserver === 'undefined') return
  if (typeof CSS !== 'undefined' && CSS.supports('animation-timeline', 'scroll()')) return
  const first = el.firstElementChild
  const last = el.lastElementChild
  if (!first || !last) return
  edgeObserver = new IntersectionObserver((entries) => {
    for (const { target, intersectionRatio } of entries) {
      el.classList.toggle(target === first ? 'more-start' : 'more-end', intersectionRatio < 1)
    }
  }, { root: el, threshold: 1, rootMargin: '1px' })
  edgeObserver.observe(first)
  edgeObserver.observe(last)
})
onBeforeUnmount(() => edgeObserver?.disconnect())
</script>

<template>
  <div class="ms-shell">
    <header class="ms-head">
      <div class="ms-crumb">
        <p class="ms-where">
          <Icon icon="headphones" class="ms-where-icon" aria-hidden="true" />
          <span>{{ guildName }}</span>
          <template v-if="voiceName">
            <span aria-hidden="true" class="ms-sep">·</span>
            <span>{{ voiceName }}</span>
          </template>
        </p>
        <div class="ms-actions">
          <UserChip />
          <slot name="actions" />
        </div>
      </div>
      <nav class="ms-nav" :aria-label="t('nav.pages')">
        <div ref="scroller" class="ms-pivots">
          <button
            v-for="v in props.views"
            :key="v"
            type="button"
            class="ms-pivot"
            :aria-current="props.view === v ? 'page' : undefined"
            @click="emit('select', v)"
          >{{ props.label(v) }}</button>
        </div>
      </nav>
    </header>
    <main ref="main" class="ms-main" :class="{ 'ms-main--fill': props.fill }">
      <slot />
    </main>
  </div>
</template>

<style scoped>
.ms-shell {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  /* 不写的话列宽按内容的最小宽度算,一排放不下的视图名会把整页撑宽 */
  grid-template-columns: minmax(0, 1fr);
  block-size: 100%;
  font-family: var(--m-font);
  color: var(--c-text);
  /* 视图名的字号跟着 Activity 框的高度走:矮的框里不占太多地方 */
  container: shell / size;
}

.ms-head {
  padding: 0.625rem var(--m-pad) 0;
}
.ms-crumb {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.25rem 0.75rem;
}
.ms-where {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0 0.5rem;
  min-inline-size: 0;
  margin: 0;
  font-size: 0.8125rem;
  letter-spacing: 0.03em;
  color: var(--c-text-muted);
  overflow-wrap: anywhere;
}
.ms-where-icon { font-size: 0.875rem; }
.ms-actions { display: flex; align-items: center; gap: 0.375rem; }
/* 用户、语言、主题这几个小控件:方角,触屏 44px(UserChip 只动触发按钮,不动弹出面板) */
.ms-actions > :deep(div > button),
.ms-actions :slotted(select),
.ms-actions :slotted(button) {
  border-radius: 0;
}
@media (pointer: coarse) {
  .ms-actions > :deep(div > button),
  .ms-actions :slotted(select),
  .ms-actions :slotted(button) { min-block-size: 2.75rem; }
  .ms-actions :slotted(button) { min-inline-size: 2.75rem; }
}

/* ---- pivot ---- */
@property --fade-start {
  syntax: "<length>";
  inherits: false;
  initial-value: 0px;
}
@property --fade-end {
  syntax: "<length>";
  inherits: false;
  initial-value: 0px;
}

.ms-nav { margin-inline: -0.25rem; }
.ms-pivots {
  --fade-size: 1.5rem;
  display: flex;
  gap: clamp(0.75rem, 2.5vw, 2.25rem);
  overflow-x: auto;
  overscroll-behavior-x: contain;
  /* 焦点框画在按钮外面:给它留出位置,不被滚动区裁掉 */
  padding: 0.25rem;
  scrollbar-width: none;
  scroll-padding-inline: var(--fade-size);
  mask:
    linear-gradient(black, black) no-clip subtract,
    linear-gradient(to right, black, transparent) 0 0 / var(--fade-start) 100% no-repeat no-clip,
    linear-gradient(to right, transparent, black) 100% 0 / var(--fade-end) 100% no-repeat no-clip;
  /* 长写法:构建时 shorthand 会被展开成 animation-duration: 0s,滚动驱动动画要的是 auto */
  animation-name: ms-reveal-fade-start, ms-hide-fade-end;
  animation-duration: auto;
  animation-timing-function: linear;
  animation-fill-mode: both;
  animation-timeline: scroll(self inline);
  animation-range: 0 var(--fade-size), calc(100% - var(--fade-size)) 100%;
}
.ms-pivots::-webkit-scrollbar { display: none; }

@keyframes ms-reveal-fade-start {
  to { --fade-start: var(--fade-size); }
}
@keyframes ms-hide-fade-end {
  from { --fade-end: var(--fade-size); }
}
@supports not (animation-timeline: scroll()) {
  .ms-pivots {
    animation: none;
    transition: --fade-start 0.2s, --fade-end 0.2s;
  }
  .ms-pivots.more-start { --fade-start: var(--fade-size); }
  .ms-pivots.more-end { --fade-end: var(--fade-size); }
}

.ms-pivot {
  position: relative;
  flex: none;
  margin: 0;
  border: 0;
  border-radius: 0;
  padding: 0 0 0.375rem;
  background: transparent;
  color: var(--c-text-muted);
  cursor: pointer;
  font-family: var(--m-font-display);
  /* 退路:视口高度(iframe 里就是 Activity 的框);支持容器单位时按外壳的宽高算 */
  font-size: clamp(1.75rem, min(0.75rem + 5vh, 6vw), 2.5rem);
  font-weight: 300;
  line-height: 1.25;
  white-space: nowrap;
  transition: color 120ms ease-out;
}
@supports (font-size: 1cqb) {
  .ms-pivot { font-size: clamp(1.75rem, min(0.75rem + 5cqb, 6cqi), 2.5rem); }
}
/* 触屏 44px;下划线画在底边,长高后仍对齐 */
@media (pointer: coarse) {
  .ms-pivot { min-block-size: 2.75rem; }
}
.ms-pivot:hover { color: var(--c-text); }
/* 当前视图:文字颜色 + 下划线(不只靠颜色区分);下划线是边框,高对比度模式下也在 */
.ms-pivot[aria-current="page"] { color: var(--c-text); }
.ms-pivot[aria-current="page"]::after {
  content: "";
  position: absolute;
  inset: auto 0 0;
  border-block-end: 3px solid var(--c-accent);
}

/* 很矮的 Activity 框(约 300–400px):顶部这两行收紧,把高度留给磁贴。
   字号下限仍是 rem,最大 / 最小 <= 2.5 倍;触屏上的 44px 下限不受影响(min-block-size 优先) */
@container shell (height < 25rem) {
  .ms-head { padding-block-start: 0.375rem; }
  .ms-actions > :deep(div > button),
  .ms-actions :slotted(select),
  .ms-actions :slotted(button) { block-size: 1.75rem; }
  .ms-actions :slotted(button) { inline-size: 1.75rem; }
  .ms-pivot { font-size: clamp(1.375rem, min(0.25rem + 5cqb, 6cqi), 2.5rem); padding-block-end: 0.25rem; }
}

/* ---- 主区域 ---- */
.ms-main {
  position: relative;
  min-block-size: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
}
.ms-main--fill { overflow: hidden; }

@media (forced-colors: active) {
  .ms-pivot[aria-current="page"]::after { border-color: Highlight; }
}
</style>
