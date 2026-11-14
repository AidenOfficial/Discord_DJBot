<script setup lang="ts">
import {
  computed, defineAsyncComponent, nextTick, onBeforeUnmount, onMounted, provide, ref, shallowReactive, watch,
  type Component,
} from 'vue'
import NowPlaying from './components/NowPlaying.vue'
import ViewLoadError, { RETRY_VIEW } from './components/ViewLoadError.vue'
import QueueList from './components/QueueList.vue'
import UserChip from './components/UserChip.vue'
import GuildSwitcher from './components/GuildSwitcher.vue'
import ActivityMini from './components/ActivityMini.vue'
import { embedded } from './activity'
import { useGuilds } from './composables/useGuilds'
import { getItem, removeItem, setItem } from './storage'
import { LOCALES, locale, setLocale, t, type Locale } from './i18n'
import type { Key } from './i18n/en'

// 首页之外的视图按需加载,首屏只需要 NowPlaying + QueueList
const loaders = {
  search: () => import('./components/SearchPage.vue'),
  library: () => import('./components/LibraryPage.vue'),
  lists: () => import('./components/PlaylistsPage.vue'),
  stats: () => import('./components/StatsPage.vue'),
  cache: () => import('./components/CachePage.vue'),
  settings: () => import('./components/SettingsPage.vue'),
}
type LazyView = keyof typeof loaders
// 页面代码加载失败(断网、刚重新部署旧文件没了):先悄悄重试一次,还不行就显示
// ViewLoadError,它的"重试"会重建这个组件,让浏览器再请求一次
function lazyView(name: LazyView): Component {
  return defineAsyncComponent({
    loader: loaders[name],
    errorComponent: ViewLoadError,
    onError(_err, retry, fail, attempts) {
      if (attempts <= 1) setTimeout(retry, 1000)
      else fail()
    },
  })
}
const pages = shallowReactive({} as Record<LazyView, Component>)
for (const name of Object.keys(loaders) as LazyView[]) pages[name] = lazyView(name)
const mainEl = ref<HTMLElement | null>(null)
provide(RETRY_VIEW, () => {
  const v = view.value
  if (v === 'home') return
  // 点的"重试"按钮马上会被换掉:焦点先放到 <main> 开头,别掉回 body;
  // 加载成功或再次失败,Tab 都从这里进入新内容。tabindex 只临时加,
  // 平时点 main 的空白处不会把焦点落到 main 上
  const el = mainEl.value
  if (el) {
    el.tabIndex = -1
    el.addEventListener('blur', () => el.removeAttribute('tabindex'), { once: true })
    el.focus()
  }
  pages[v] = lazyView(v)
})

type Theme = 'light' | 'dark' | 'auto'
type Scheme = 'light' | 'dark'
const THEME_KEY: Record<Theme, Key> = { auto: 'theme.auto', light: 'theme.light', dark: 'theme.dark' }

type View = 'home' | 'search' | 'library' | 'lists' | 'stats' | 'cache' | 'settings'
const VIEWS: View[] = ['home', 'search', 'library', 'lists', 'stats', 'cache', 'settings']
const VIEW_LABEL: Record<View, Key> = {
  home: 'nav.home', search: 'nav.search', library: 'nav.library', lists: 'nav.lists', stats: 'nav.stats', cache: 'nav.cache', settings: 'nav.settings',
}
// 这些页面自己没有 <h1>,由这里补一个只给读屏用的
const NEEDS_HEADING: View[] = ['search', 'library', 'stats', 'cache']
const view = ref<View>('home')
const { noAccess } = useGuilds()

// Activity 被缩成画中画小窗:只显示一条迷你播放器。
// 监听先注册,后面读存储即使出问题也不会漏掉它。
const pip = embedded ? window.matchMedia('(max-height: 300px)') : null
const compact = ref(!!pip?.matches)
function onPip(e: MediaQueryListEvent) { compact.value = e.matches }
pip?.addEventListener('change', onPip)

// ---- 主题 ----
// theme-init.js 在首帧前已经按存储设好了 data-theme;这里同步状态,之后的切换也由这里负责。
// iOS 的 Activity 里没存主题时 theme-init.js 会设 data-theme-default=dark,"跟随系统"就是深色。
const root = document.documentElement
const sysQuery = window.matchMedia('(prefers-color-scheme: dark)')
const sysDark = ref(sysQuery.matches)
function onSysChange(e: MediaQueryListEvent) { sysDark.value = e.matches }
sysQuery.addEventListener('change', onSysChange)

const systemScheme = computed<Scheme>(() =>
  root.getAttribute('data-theme-default') === 'dark' || sysDark.value ? 'dark' : 'light')

function readStored(): Theme {
  const s = getItem('theme')
  return s === 'light' || s === 'dark' ? s : 'auto'
}
const theme = ref<Theme>(readStored())
const rendered = computed<Scheme>(() => theme.value === 'auto' ? systemScheme.value : theme.value)

function applyTheme(next: Theme, persist = true) {
  theme.value = next
  if (next === 'auto') root.removeAttribute('data-theme')
  else root.setAttribute('data-theme', next)
  document.querySelector('meta[name="color-scheme"]')?.setAttribute('content',
    next === 'auto' ? (root.hasAttribute('data-theme-default') ? 'dark' : 'light dark') : next)
  // 存不了(iframe 里站点数据被拦)也照样生效,只是不记住
  if (persist) {
    if (next === 'auto') removeItem('theme')
    else setItem('theme', next)
  }
}
applyTheme(theme.value, false)

// 顶栏按钮只有两个状态:切到和现在看到的相反的配色;和系统一致时就是回到"跟随系统"
function toggleTheme() {
  const target: Scheme = rendered.value === 'dark' ? 'light' : 'dark'
  applyTheme(target === systemScheme.value ? 'auto' : target)
}
const themeAction = computed(() => t(rendered.value === 'dark' ? 'theme.toLight' : 'theme.toDark'))
const themeState = computed(() => t('theme.title', {
  mode: theme.value === 'auto'
    ? t('theme.autoAs', { mode: t(THEME_KEY[systemScheme.value]) })
    : t(THEME_KEY[theme.value]),
}))

// 另一个标签页改了主题
function onStorage(e: StorageEvent) {
  if (e.key !== 'theme') return
  applyTheme(e.newValue === 'light' || e.newValue === 'dark' ? e.newValue : 'auto', false)
}
window.addEventListener('storage', onStorage)

// 语言包按需加载:加载失败时界面还是原来的语言,下拉框也要跟着退回去,
// 不然显示的选项和界面语言对不上(下次再选会重新请求)
async function onLangChange(e: Event) {
  const sel = e.target as HTMLSelectElement
  const want = sel.value as Locale
  const ok = await setLocale(want)
  if (!ok && sel.value === want) sel.value = locale.value
}

// ---- 页面标题 + 导航 ----
watch([view, locale], () => {
  document.title = `${t(VIEW_LABEL[view.value])} · DJ Bot`
}, { immediate: true })

const navScroller = ref<HTMLElement | null>(null)
function select(v: View, e: MouseEvent) {
  view.value = v
  // 窄屏时导航横向滚动:把选中的按钮完整露出来。container: 'nearest' 只滚导航,
  // 不认识这个选项的浏览器会忽略它,导航本身不滚整页(block: 'nearest')。
  const btn = e.currentTarget as HTMLElement
  void nextTick(() => btn.scrollIntoView({ block: 'nearest', inline: 'nearest', container: 'nearest' } as ScrollIntoViewOptions))
}

// 不支持滚动驱动动画时,用 IntersectionObserver 判断两端还有没有被遮住的按钮
let edgeObserver: IntersectionObserver | null = null
function observeNavEdges() {
  const el = navScroller.value
  if (!el || edgeObserver || typeof IntersectionObserver === 'undefined') return
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
}
watch(compact, (c) => {
  if (c) { edgeObserver?.disconnect(); edgeObserver = null }
  else void nextTick(observeNavEdges)
})

// 空闲时预取其它页面的代码,第一次切过去时不用等下载
function prefetchViews() {
  const run = () => { for (const load of Object.values(loaders)) load().catch(() => { /* 切过去时会再试 */ }) }
  if ('requestIdleCallback' in window) window.requestIdleCallback(run, { timeout: 4000 })
  else setTimeout(run, 1500)
}

onMounted(() => {
  observeNavEdges()
  prefetchViews()
})
onBeforeUnmount(() => {
  pip?.removeEventListener('change', onPip)
  sysQuery.removeEventListener('change', onSysChange)
  window.removeEventListener('storage', onStorage)
  edgeObserver?.disconnect()
})
</script>

<template>
  <ActivityMini v-if="compact" class="h-full" />
  <div v-else class="flex min-h-full flex-col">
    <!-- Activity 里 body 让出了顶部安全区;吸顶后 header 停在视口最上面,所以把它拉进这块区域,
         用自己的背景盖住刘海 / 状态栏,内容再往下让出同样的高度 -->
    <header
      class="sticky top-0 z-10 border-b backdrop-blur"
      :style="{
        borderColor: 'var(--c-border)',
        background: 'color-mix(in srgb, var(--c-bg) 85%, transparent)',
        ...(embedded ? {
          marginTop: 'calc(-1 * var(--discord-safe-area-inset-top, 0px))',
          paddingTop: 'var(--discord-safe-area-inset-top, 0px)',
        } : {}),
      }"
    >
      <div class="mx-auto flex w-full max-w-5xl flex-wrap items-center justify-between gap-x-3 gap-y-2 px-4 py-3">
        <div class="flex min-w-0 items-center gap-2">
          <span
            class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full"
            :style="{ background: 'var(--c-accent)', color: 'var(--c-on-accent)' }"
          >
            <Icon icon="music" class="text-sm" aria-hidden="true" />
          </span>
          <span class="hidden text-base font-semibold tracking-tight sm:inline">DJ Bot</span>
          <!-- Activity 里服务器固定是打开它的那个 -->
          <GuildSwitcher v-if="!embedded" />
        </div>
        <!-- 窄屏时导航换到第二行并可横向滚动 -->
        <nav
          class="order-last flex w-full min-w-0 rounded-full md:order-none md:w-auto"
          :style="{ background: 'var(--c-surface-2)' }"
        >
          <div ref="navScroller" class="nav-scroller flex min-w-0 flex-1 gap-1 overflow-x-auto p-1">
            <button
              v-for="v in VIEWS"
              :key="v"
              type="button"
              class="shrink-0 cursor-pointer rounded-full border-0 px-3.5 py-1.5 text-xs font-medium whitespace-nowrap"
              :style="view === v
                ? { background: 'var(--c-surface)', color: 'var(--c-text)', boxShadow: 'var(--shadow-1)' }
                : { background: 'transparent', color: 'var(--c-text-muted)' }"
              :aria-current="view === v ? 'page' : undefined"
              @click="select(v, $event)"
            >{{ t(VIEW_LABEL[v]) }}</button>
          </div>
        </nav>
        <div class="flex items-center gap-2">
          <UserChip />
          <select
            :value="locale"
            @change="onLangChange"
            class="h-9 cursor-pointer rounded-full border-0 px-2.5 text-xs"
            :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
            :title="t('lang.title')"
            :aria-label="t('lang.title')"
          >
            <option v-for="l in LOCALES" :key="l.code" :value="l.code">{{ l.label }}</option>
          </select>
          <button
            type="button"
            class="flex h-9 w-9 cursor-pointer items-center justify-center rounded-full border-0 text-sm"
            :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
            :aria-label="themeAction"
            :title="`${themeAction} · ${themeState}`"
            @click="toggleTheme"
          >
            <Icon :icon="rendered === 'dark' ? 'moon' : 'sun'" aria-hidden="true" />
          </button>
        </div>
      </div>
    </header>

    <main ref="mainEl" class="flex-1">
      <h1 v-if="NEEDS_HEADING.includes(view)" class="sr-only">{{ t(VIEW_LABEL[view]) }}</h1>
      <div v-if="noAccess" class="mx-auto mt-6 w-full max-w-3xl px-4">
        <div class="rounded-2xl p-5" :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)' }">
          <p class="font-medium"><Icon icon="lock" class="mr-2" aria-hidden="true" :style="{ color: 'var(--c-text-muted)' }" />{{ t('guild.noAccessTitle') }}</p>
          <p class="mt-1 text-sm" :style="{ color: 'var(--c-text-muted)' }">{{ t('guild.noAccessHint') }}</p>
        </div>
      </div>
      <template v-if="view === 'home'">
        <NowPlaying />
        <QueueList />
      </template>
      <component :is="pages[view]" v-else />
    </main>
  </div>
</template>

<style scoped>
/* 导航在窄屏横向滚动:哪一端后面还有按钮,哪一端就渐隐,提示可以继续滑。
   滚动驱动动画按自身滚动位置伸缩两端的渐隐带;内容放得下时时间线不激活,也就没有渐隐。 */
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

.nav-scroller {
  --fade-size: 1.5rem;
  --fade-dir: right;
  --fade-start-pos: 0;
  --fade-end-pos: 100%;
  scrollbar-width: none;
  /* 键盘切到的按钮不要停在渐隐带里 */
  scroll-padding-inline: var(--fade-size);
  mask:
    linear-gradient(black, black) no-clip subtract,
    linear-gradient(to var(--fade-dir), black, transparent) var(--fade-start-pos) 0 / var(--fade-start) 100% no-repeat no-clip,
    linear-gradient(to var(--fade-dir), transparent, black) var(--fade-end-pos) 0 / var(--fade-end) 100% no-repeat no-clip;
  /* 用长写法:构建时 shorthand 会被展开成 animation-duration: 0s,滚动驱动动画要的是 auto */
  animation-name: reveal-fade-start, hide-fade-end;
  animation-duration: auto;
  animation-timing-function: linear;
  animation-fill-mode: both;
  animation-timeline: scroll(self inline);
  animation-range: 0 var(--fade-size), calc(100% - var(--fade-size)) 100%;
}

.nav-scroller::-webkit-scrollbar {
  display: none;
}

@keyframes reveal-fade-start {
  to { --fade-start: var(--fade-size); }
}

@keyframes hide-fade-end {
  from { --fade-end: var(--fade-size); }
}

/* 退路:不支持滚动驱动动画时由 IntersectionObserver 加这两个 class */
@supports not (animation-timeline: scroll()) {
  .nav-scroller {
    /* 没有滚动时间线时动画会按时间跑完并停在终点,永远显示开头的渐隐 */
    animation: none;
    transition: --fade-start 0.2s, --fade-end 0.2s;
  }
  .nav-scroller.more-start {
    --fade-start: var(--fade-size);
  }
  .nav-scroller.more-end {
    --fade-end: var(--fade-size);
  }
}
</style>
