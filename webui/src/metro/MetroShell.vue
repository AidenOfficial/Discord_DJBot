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

// 进场方向跟着导航走:去右边的视图,新内容从右边进来;回左边的,从左边进来
const enterX = ref('2.5rem')
watch(() => props.view, (next, prev) => {
  enterX.value = props.views.indexOf(next) < props.views.indexOf(prev) ? '-2.5rem' : '2.5rem'
}, { flush: 'sync' })

// ---- 当前视图的下划线 ----
// 画在 .ms-pivots::before 上(伪元素、用边框画,高对比度模式下也在),位置由这里写进 --ul-l / --ul-r。
// 换视图时两条边分先后:往右切,右边先伸到新视图名的右端,左边稍后跟过去收拢;往左切反过来。
// 动画是 CSS 里 inset 的过渡(只在允许动效时)。不用 anchor positioning:Discord 桌面版(Chromium)还不支持
const ulDir = ref<'fwd' | 'back'>('fwd')
const ulReady = ref(false)
function placeUnderline() {
  const strip = scroller.value
  const btn = strip?.querySelector<HTMLElement>(`[data-view="${props.view}"]`)
  if (!strip || !btn) return
  // 绝对定位在滚动容器里:left / right 都相对容器的内边距框(随内容一起滚)
  strip.style.setProperty('--ul-l', `${btn.offsetLeft}px`)
  strip.style.setProperty('--ul-r', `${strip.clientWidth - btn.offsetLeft - btn.offsetWidth}px`)
  strip.style.setProperty('--ul-t', `${btn.offsetTop + btn.offsetHeight}px`)
}
watch(() => props.view, (next, prev) => {
  ulDir.value = props.views.indexOf(next) < props.views.indexOf(prev) ? 'back' : 'fwd'
  void nextTick(placeUnderline)
})
let ulResize: ResizeObserver | null = null

/** 内容里的磁贴切换了视图(原来的按钮随之消失):焦点交给新选中的视图名 */
function focusCurrent() {
  void nextTick(() => currentButton()?.focus())
}
defineExpose({ main, focusCurrent })

// 不支持滚动驱动动画时,用 IntersectionObserver 判断两端还有没有被遮住的视图名
let edgeObserver: IntersectionObserver | null = null
onMounted(() => {
  reveal()
  placeUnderline()
  // 第一次放好、让浏览器先算一遍样式,再开过渡:打开时不从 0 滑过来。
  // 不用 requestAnimationFrame:Activity 在后台时不跑动画帧,过渡就一直开不了
  void scroller.value?.offsetWidth
  ulReady.value = true
  // 视图名换语言、字号随框变化、窗口改大小:重新量,不动画也行(过渡会顺带平滑过去)
  if (typeof ResizeObserver !== 'undefined' && scroller.value) {
    ulResize = new ResizeObserver(() => placeUnderline())
    ulResize.observe(scroller.value)
    for (const b of scroller.value.children) ulResize.observe(b)
  }
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
onBeforeUnmount(() => {
  edgeObserver?.disconnect()
  ulResize?.disconnect()
})
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
        <div
          ref="scroller"
          class="ms-pivots"
          :class="{ 'ms-pivots--ready': ulReady }"
          :data-ul-dir="ulDir"
        >
          <button
            v-for="v in props.views"
            :key="v"
            type="button"
            class="ms-pivot"
            :data-view="v"
            :aria-current="props.view === v ? 'page' : undefined"
            @click="emit('select', v)"
          >{{ props.label(v) }}</button>
        </div>
      </nav>
    </header>
    <main ref="main" class="ms-main" :class="{ 'ms-main--fill': props.fill }">
      <!-- 按视图换 key:换视图时重新挂载,进场动画随之播放(动画本身在 CSS 里,只在允许动效时) -->
      <div
        :key="props.view"
        class="ms-view"
        :class="{ 'ms-view--fill': props.fill }"
        :style="{ '--enter-x': enterX }"
      >
        <slot />
      </div>
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

/* 当前视图的下划线:一条,在两个视图名之间先伸展再收拢(位置见脚本里的 placeUnderline) */
.ms-pivots { position: relative; }
.ms-pivots::before {
  content: "";
  position: absolute;
  inset-block-start: calc(var(--ul-t, 0px) - 3px);
  inset-inline-start: var(--ul-l, 0px);
  inset-inline-end: var(--ul-r, 100%);
  /* 用边框画:高对比度模式会去掉背景色,边框留着 */
  border-block-end: 3px solid var(--c-accent);
  pointer-events: none;
}
@media (prefers-reduced-motion: no-preference) {
  /* 领头的那条边先走、快;跟在后面的那条晚一点出发、慢一点收拢。都是非线性的 */
  .ms-pivots--ready[data-ul-dir="fwd"]::before {
    transition:
      inset-inline-end 190ms cubic-bezier(0.3, 0, 0.1, 1),
      inset-inline-start 230ms cubic-bezier(0.5, 0, 0.1, 1) 80ms;
  }
  .ms-pivots--ready[data-ul-dir="back"]::before {
    transition:
      inset-inline-start 190ms cubic-bezier(0.3, 0, 0.1, 1),
      inset-inline-end 230ms cubic-bezier(0.5, 0, 0.1, 1) 80ms;
  }
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
/* 进场时内容往旁边偏一点,不该闪出横向滚动条 */
.ms-main { overflow-x: hidden; }
/* 正在播放页自己铺满(它里面是 position: absolute; inset: 0) */
.ms-view--fill { position: absolute; inset: 0; }

@media (prefers-reduced-motion: no-preference) {
  /* 其它视图整页滑进来;正在播放页由自己的磁贴依次飞入(见 MetroNow) */
  .ms-view:not(.ms-view--fill) {
    animation-name: ms-enter;
    animation-duration: 480ms;
    animation-timing-function: cubic-bezier(0.1, 0.9, 0.2, 1);
    animation-fill-mode: both;
  }
}
@keyframes ms-enter {
  from {
    opacity: 0;
    translate: var(--enter-x) 0;
  }
}

@media (forced-colors: active) {
  .ms-pivots::before { border-color: Highlight; }
}
</style>
