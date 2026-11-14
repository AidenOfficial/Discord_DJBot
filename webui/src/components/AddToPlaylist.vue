<script lang="ts">
// 所有实例共享:当前打开的面板。触发按钮用了 click.stop,别的实例的 document
// 监听收不到这次点击,所以打开新的时由这里关掉旧的
let closeCurrent: (() => void) | null = null
</script>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId } from 'vue'
import { addToPlaylist, createPlaylist, type PlaylistSource } from '../api'
import { useMe } from '../composables/useMe'
import { useFavorites } from '../composables/useFavorites'
import { announce } from '../composables/useAnnounce'
import { t } from '../i18n'

const props = withDefaults(
  defineProps<{ source: PlaylistSource; label?: string; /** 列表行里用:按钮名字带上歌名 */ itemTitle?: string }>(),
  { label: '', itemTitle: '' },
)

const { me, playlists, reloadPlaylists } = useMe()
const { reloadFavorites } = useFavorites()

const open = ref(false)
const creating = ref(false)
const newName = ref('')
const feedback = ref('')
const feedbackOk = ref(false)
const root = ref<HTMLElement | null>(null)
const trigger = ref<HTMLButtonElement | null>(null)
const panel = ref<HTMLElement | null>(null)
const nameInput = ref<HTMLInputElement | null>(null)
const panelId = useId()
// 默认在按钮右下方展开;放不下时改成向上 / 左对齐(见 place())
const openUp = ref(false)
const alignStart = ref(false)
let closeTimer: ReturnType<typeof setTimeout> | undefined

// 有可见文字时就用可见文字当名字(Label in Name);只有图标时才用 aria-label
const ariaLabel = computed(() => {
  if (props.label) return undefined
  return props.itemTitle ? t('common.itemAction', { action: t('atp.title'), title: props.itemTitle }) : t('atp.title')
})

const closeMe = () => close()

function close(focusTrigger = false) {
  clearTimeout(closeTimer)
  if (!open.value) return
  // 先把焦点交回触发按钮,再移除面板;否则焦点掉到 <body>
  if (focusTrigger) trigger.value?.focus()
  open.value = false
  creating.value = false
  if (closeCurrent === closeMe) closeCurrent = null
}

/** 面板在视口里放不下时翻到上方 / 改成左对齐(锚点定位在 Chromium 里还不能用) */
function place() {
  openUp.value = false
  alignStart.value = false
  void nextTick(() => {
    const el = panel.value
    const anchor = root.value
    if (!el || !anchor) return
    const r = el.getBoundingClientRect()
    const a = anchor.getBoundingClientRect()
    if (r.left < 8) alignStart.value = true
    if (r.bottom > window.innerHeight - 8 && a.top > window.innerHeight - a.bottom) openUp.value = true
  })
}

function toggle() {
  if (open.value) {
    close()
    return
  }
  if (closeCurrent && closeCurrent !== closeMe) closeCurrent()
  closeCurrent = closeMe
  open.value = true
  feedback.value = ''
  feedbackOk.value = false
  creating.value = false
  reloadPlaylists()
  place()
}

function startCreate() {
  creating.value = true
  // 动态插入的输入框上 autofocus 不可靠(每个文档只生效一次,跨源 iframe 里不生效)
  void nextTick(() => nameInput.value?.focus())
}

async function addTo(id: number) {
  clearTimeout(closeTimer)
  feedback.value = '...'
  feedbackOk.value = false
  try {
    const rv = await addToPlaylist(id, props.source)
    const name = playlists.value.find((p) => p.id === id)?.favorites ? t('fav.name') : rv.playlist.name
    feedback.value = t(rv.added ? 'atp.added' : 'atp.already', { name })
    feedbackOk.value = !!rv.added
    announce(feedback.value)
    if (rv.added) reloadFavorites() // 可能刚好加进了"我喜欢的音乐"
    reloadPlaylists()
    closeTimer = setTimeout(() => {
      const active = document.activeElement
      // 焦点还在面板里(或因为表单被移除掉到了 body)才交回按钮,用户已经去别处了就不抢
      close(!active || active === document.body || !!root.value?.contains(active))
    }, 900)
  } catch {
    feedbackOk.value = false
    feedback.value = t('atp.failed')
    announce(feedback.value, { assertive: true })
  }
}

async function createAndAdd() {
  const name = newName.value.trim()
  if (!name) return
  try {
    const pl = await createPlaylist(name)
    newName.value = ''
    creating.value = false
    await addTo(pl.id)
  } catch {
    feedbackOk.value = false
    feedback.value = t('atp.createFailed')
    announce(feedback.value, { assertive: true })
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && open.value) {
    e.preventDefault()
    close(true)
  }
}

function onFocusOut(e: FocusEvent) {
  // relatedTarget 为空多半是面板里的元素被移除了(如"新建歌单"换成输入框),不算离开
  const next = e.relatedTarget as Node | null
  if (open.value && next && !root.value?.contains(next)) close()
}

function onDocClick(e: MouseEvent) {
  if (open.value && root.value && !root.value.contains(e.target as Node)) close()
}
onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick)
  clearTimeout(closeTimer)
  if (closeCurrent === closeMe) closeCurrent = null
})
</script>

<template>
  <div
    v-if="me?.can_have_playlists"
    ref="root"
    class="relative inline-flex"
    @keydown="onKeydown"
    @focusout="onFocusOut"
  >
    <button
      ref="trigger"
      type="button"
      class="inline-flex cursor-pointer items-center gap-1 rounded-md border-0 px-2 py-1 text-xs"
      :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
      :title="t('atp.title')"
      :aria-label="ariaLabel"
      :aria-expanded="open"
      :aria-controls="open ? panelId : undefined"
      @click.stop="toggle"
    ><Icon icon="list-ul" /><span v-if="props.label">{{ props.label }}</span></button>

    <div
      v-if="open"
      :id="panelId"
      ref="panel"
      class="absolute z-30 w-56 max-w-[calc(100vw-2rem)] rounded-xl p-1.5 text-left text-sm"
      :class="[openUp ? 'bottom-full mb-1' : 'top-full mt-1', alignStart ? 'left-0' : 'right-0']"
      :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-2)', border: '1px solid var(--c-border)' }"
      @click.stop
    >
      <p class="px-2 pt-1 pb-1.5 text-[11px] font-semibold uppercase tracking-wider" :style="{ color: 'var(--c-text-faint)' }">
        {{ t('atp.header') }}
      </p>
      <ul role="list" class="max-h-56 overflow-y-auto overscroll-contain">
        <li v-for="pl in playlists" :key="pl.id">
          <button
            type="button"
            class="flex w-full cursor-pointer items-center justify-between gap-2 rounded-lg border-0 bg-transparent px-2 py-1.5 text-left text-sm hover:opacity-80"
            :style="{ color: 'var(--c-text)' }"
            @click="addTo(pl.id)"
          >
            <span class="flex min-w-0 items-center gap-1.5">
              <Icon v-if="pl.favorites" icon="heart" class="shrink-0" :style="{ color: 'var(--c-danger)' }" />
              <span class="truncate">{{ pl.favorites ? t('fav.name') : pl.name }}</span>
            </span>
            <span class="shrink-0 text-xs tabular-nums" :style="{ color: 'var(--c-text-faint)' }">{{ pl.count }}</span>
          </button>
        </li>
      </ul>
      <form v-if="creating" class="flex gap-1 p-1" @submit.prevent="createAndAdd">
        <input
          ref="nameInput"
          v-model="newName"
          maxlength="60"
          :placeholder="t('atp.name')"
          :aria-label="t('atp.name')"
          class="min-w-0 flex-1 rounded-md border px-2 py-1 text-xs"
          :style="{ background: 'var(--c-bg)', borderColor: 'var(--c-border)', color: 'var(--c-text)' }"
        />
        <button
          type="submit"
          class="cursor-pointer rounded-md border-0 px-2 py-1 text-xs font-semibold"
          :style="{ background: 'var(--c-accent)', color: 'var(--c-on-accent)' }"
        >{{ t('atp.add') }}</button>
      </form>
      <button
        v-else
        type="button"
        class="w-full cursor-pointer rounded-lg border-0 bg-transparent px-2 py-1.5 text-left text-sm"
        :style="{ color: 'var(--c-accent)' }"
        @click="startCreate"
      ><Icon icon="plus" class="mr-1" />{{ t('atp.new') }}</button>
      <p v-if="feedback" class="px-2 pt-1 pb-0.5 text-xs" :style="{ color: 'var(--c-text-muted)' }">
        <Icon v-if="feedbackOk" icon="check" class="mr-1" :style="{ color: 'var(--c-success)' }" />{{ feedback }}
      </p>
    </div>
  </div>
</template>
