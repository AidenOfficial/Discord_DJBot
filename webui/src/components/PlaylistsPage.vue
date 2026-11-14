<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  addToPlaylist, copyPlaylist, createPlaylist, deletePlaylist, fetchPlaylist, fetchPublicPlaylists,
  movePlaylistItem, playPlaylist, removeFromPlaylist, renamePlaylist, setPlaylistPublic, startImport,
  fetchImportJob, type ImportJob, type PlaylistDetail, type PlaylistSummary,
} from '../api'
import AddToPlaylist from './AddToPlaylist.vue'
import FavButton from './FavButton.vue'
import { useMe } from '../composables/useMe'
import { useFavorites } from '../composables/useFavorites'
import { formatTime, useStatus } from '../composables/useStatus'
import { announce } from '../composables/useAnnounce'
import { useConfirm } from '../composables/useConfirm'
import { t, tParts, typeLabel } from '../i18n'
import type { Key } from '../i18n/en'

const { me, playlists, reloadPlaylists } = useMe()
const { reloadFavorites } = useFavorites()
const { applyStatus } = useStatus()
const { confirm } = useConfirm()

const selectedId = ref<number | null>(null)
const detail = ref<PlaylistDetail | null>(null)
const newName = ref('')
const newNameInput = ref<HTMLInputElement>()
const renaming = ref(false)
const renameDraft = ref('')
const renameInput = ref<HTMLInputElement>()
const renameBtn = ref<HTMLButtonElement>()
const toast = ref('')
const toastErr = ref(false)
const busy = ref(false)
const dragFrom = ref<number | null>(null)
const dragOver = ref<number | null>(null)
// Long playlists (up to 1000 songs) render the first page until asked, like QueueList.
const ITEM_PAGE = 100
const showAllItems = ref(false)

let toastTimer: ReturnType<typeof setTimeout> | undefined
function say(msg: string) {
  toast.value = msg
  toastErr.value = false
  clearTimeout(toastTimer)
  toastTimer = setTimeout(() => (toast.value = ''), 3000)
  announce(msg)
}
// Failures stay on screen until the next action instead of timing out.
function sayError(msg: string) {
  clearTimeout(toastTimer)
  toast.value = msg
  toastErr.value = true
  announce(msg, { assertive: true })
}
function clearError() {
  if (toastErr.value) toast.value = ''
}

watch(() => me.value?.can_have_playlists, (ok) => { if (ok) reloadPlaylists() }, { immediate: true })
const signedIn = computed(() => !!me.value?.can_have_playlists)

// "我喜欢的音乐"(♥ / !fav 收藏的那张)排最前;还没收藏过任何歌时也占个位,告诉用户怎么用
const sortedPlaylists = computed(() =>
  [...playlists.value].sort((a, b) => Number(!!b.favorites) - Number(!!a.favorites)))
const hasFavorites = computed(() => playlists.value.some((p) => p.favorites))
const favHint = ref(false)
const plName = (pl: { name: string; favorites?: boolean }) => (pl.favorites ? t('fav.name') : pl.name)

// 别人公开的歌单(访客也能看、能播放)
const shared = ref<PlaylistSummary[]>([])
async function loadShared() {
  try {
    shared.value = await fetchPublicPlaylists()
  } catch { /* 状态轮询那边会提示连接错误 */ }
}
let sharedTimer: ReturnType<typeof setInterval> | undefined
onMounted(() => {
  loadShared()
  sharedTimer = setInterval(loadShared, 60000)
})
onBeforeUnmount(() => clearInterval(sharedTimer))

// 默认选中:自己的第一个,没有就选大家的第一个
watch([sortedPlaylists, shared], ([mine, others]) => {
  if (selectedId.value === null && !favHint.value) {
    const first = mine[0] ?? others[0]
    if (first) select(first.id)
    return
  }
  // 自己的歌单在别处被删了
  if (detail.value?.mine && !mine.some((p) => p.id === selectedId.value)) {
    selectedId.value = null
    detail.value = null
  }
})

async function select(id: number) {
  if (id !== selectedId.value) showAllItems.value = false
  selectedId.value = id
  favHint.value = false
  renaming.value = false
  clearError()
  try {
    detail.value = await fetchPlaylist(id)
  } catch {
    // 别人刚把它改回私人 / 删掉了
    const wasShared = shared.value.some((p) => p.id === id)
    detail.value = null
    selectedId.value = null
    if (wasShared) {
      say(t('pl.noLongerShared'))
      loadShared()
    }
  }
}

async function togglePublic() {
  if (!detail.value?.mine) return
  clearError()
  try {
    const next = !detail.value.public
    detail.value = await setPlaylistPublic(detail.value.id, next)
    say(t(next ? 'pl.nowPublic' : 'pl.nowPrivate'))
    reloadPlaylists()
  } catch {
    sayError(t('common.saveFailed'))
  }
}

async function copyToMine() {
  if (!detail.value || detail.value.mine) return
  clearError()
  try {
    const pl = await copyPlaylist(detail.value.id)
    await reloadPlaylists()
    await select(pl.id)
    say(t('pl.copied', { name: pl.name }))
  } catch (e) {
    sayError(e instanceof Error && e.message.endsWith('409') ? t('import.too_many_playlists') : t('pl.copyFailed'))
  }
}

async function create() {
  const name = newName.value.trim()
  if (!name) return
  clearError()
  try {
    const pl = await createPlaylist(name)
    newName.value = ''
    await reloadPlaylists()
    select(pl.id)
  } catch {
    sayError(t('pl.createFailed'))
  }
}

// The rename button is replaced by the input, so move focus there and back.
async function startRename() {
  if (!detail.value) return
  renameDraft.value = detail.value.name
  renaming.value = true
  await nextTick()
  renameInput.value?.focus()
  renameInput.value?.select()
}

async function endRename() {
  renaming.value = false
  await nextTick()
  renameBtn.value?.focus()
}

function cancelRename(e: KeyboardEvent) {
  if (e.isComposing) return // Esc first cancels an IME composition
  e.preventDefault()
  endRename()
}

async function rename() {
  if (!detail.value) return
  const name = renameDraft.value.trim()
  if (!name) return
  clearError()
  try {
    detail.value = await renamePlaylist(detail.value.id, name)
    endRename()
    reloadPlaylists()
  } catch {
    sayError(t('pl.renameFailed'))
  }
}

async function remove() {
  if (!detail.value) return
  const { id, name, favorites: wasFavorites } = detail.value
  const ok = await confirm({
    message: t('pl.confirmDelete', { name: plName(detail.value) }),
    confirmLabel: t('common.delete'),
    destructive: true,
  })
  if (!ok) return
  clearError()
  try {
    await deletePlaylist(id)
  } catch {
    sayError(t('common.saveFailed'))
    return
  }
  selectedId.value = null
  detail.value = null
  reloadPlaylists()
  if (wasFavorites) reloadFavorites()
  announce(t('pl.deleted', { name: wasFavorites ? t('fav.name') : name }))
  // The delete button went away with the detail view.
  await nextTick()
  newNameInput.value?.focus()
}

async function play(mode: 'append' | 'next' | 'replace', opts: { shuffle?: boolean; item?: number } = {}) {
  if (!detail.value || busy.value) return
  busy.value = true
  clearError()
  try {
    const rv = await playPlaylist(detail.value.id, { mode, ...opts })
    applyStatus(rv)
    const verb = t(mode === 'replace' ? 'pl.verbReplace' : mode === 'next' ? 'pl.verbNext' : 'pl.verbAppend')
    say(t('pl.playResult', { verb, n: rv.queued }) +
        (rv.skipped ? t('pl.unavailable', { n: rv.skipped }) : ''))
  } catch {
    sayError(t('pl.queueFailed'))
  } finally {
    busy.value = false
  }
}

// ---- 导入 YouTube / 网易云 / Spotify 歌单 ----
const importOpen = ref(false)
const importUrl = ref('')
const importInto = ref<'new' | 'current'>('new')
const importJob = ref<ImportJob | null>(null)
const importError = ref('')
const IMPORT_ERRORS = ['unsupported_source', 'spotify_not_configured', 'list_failed', 'no_entries', 'too_many_playlists']
const importErrorText = (code: string) =>
  IMPORT_ERRORS.includes(code) ? t(`import.${code}` as Key) : t('pl.importFailed')

const importBusy = ref(false)

function failImport(msg: string) {
  importError.value = msg
  announce(msg, { assertive: true })
}

async function runImport() {
  if (importBusy.value) return
  importBusy.value = true
  importError.value = ''
  importJob.value = null
  try {
    const id = await startImport(importUrl.value.trim(),
      importInto.value === 'current' && detail.value ? detail.value.id : undefined)
    for (;;) {
      const job = await fetchImportJob(id)
      importJob.value = job
      if (job.status === 'done' || job.status === 'error') break
      await new Promise((r) => setTimeout(r, 1500))
    }
    const job = importJob.value!
    if (job.status === 'error') {
      failImport(importErrorText(job.error ?? ''))
      return
    }
    importUrl.value = ''
    await reloadPlaylists()
    if (job.playlist_id) await select(job.playlist_id)
    say(t('pl.imported', { n: job.added ?? 0 }) +
        (job.unmatched?.length ? t('pl.importedUnmatched', { n: job.unmatched.length }) : '') +
        (job.note === 'spotify_truncated' ? t('pl.importedTruncated') : ''))
  } catch (e) {
    failImport(importErrorText(e instanceof Error ? e.message : ''))
  } finally {
    importBusy.value = false
  }
}

const importRunning = computed(() => !!importJob.value && ['listing', 'matching'].includes(importJob.value.status))
const importProgress = computed(() => {
  const j = importJob.value
  if (!j) return ''
  if (j.status === 'listing') return t('pl.reading')
  if (j.status === 'matching') {
    return j.source === 'youtube'
      ? t('pl.addingVideos', { n: j.total })
      : t('pl.matching', { done: j.processed, total: j.total })
  }
  return ''
})

async function saveQueue() {
  if (!detail.value) return
  clearError()
  try {
    const rv = await addToPlaylist(detail.value.id, { source: 'all_queue' })
    detail.value = rv.playlist
    say(rv.added ? t('pl.savedQueue', { n: rv.added }) : t('pl.queueEmpty'))
    reloadPlaylists()
    if (rv.playlist.favorites) reloadFavorites()
  } catch {
    sayError(t('pl.saveQueueFailed'))
  }
}

const itemList = ref<HTMLUListElement>()

async function dropItem(rowId: number, index: number) {
  if (!detail.value) return
  clearError()
  const hadFocus = !!itemList.value?.contains(document.activeElement)
  try {
    detail.value = await removeFromPlaylist(detail.value.id, rowId)
  } catch {
    sayError(t('common.saveFailed'))
    return
  }
  reloadPlaylists()
  if (detail.value.favorites) reloadFavorites()
  // The focused remove button left with its row: continue at the same position.
  if (hadFocus) {
    await nextTick()
    const buttons = itemList.value?.querySelectorAll<HTMLButtonElement>('[data-remove]')
    if (buttons?.length) buttons[Math.min(index, buttons.length - 1)]!.focus()
  }
}

const visibleItems = computed(() => {
  const items = detail.value?.items ?? []
  return showAllItems.value ? items : items.slice(0, ITEM_PAGE)
})

async function revealAllItems() {
  showAllItems.value = true
  await nextTick()
  // The "show all" button is gone; keep focus at the first newly shown row.
  itemList.value?.children[ITEM_PAGE]?.querySelector<HTMLButtonElement>('button')?.focus()
}

async function onDrop(i: number) {
  const from = dragFrom.value
  dragFrom.value = null
  dragOver.value = null
  if (!detail.value || from === null || from === i) return
  const moved = detail.value.items.splice(from, 1)[0]!
  detail.value.items.splice(i, 0, moved)
  try {
    detail.value = await movePlaylistItem(detail.value.id, from, i)
  } catch {
    select(detail.value.id)
  }
}

const totalDuration = computed(() =>
  (detail.value?.items ?? []).reduce((sum, e) => sum + (e.duration || 0), 0))

</script>

<template>
  <section class="mx-auto w-full max-w-5xl px-4 py-8">
    <!-- 访客、也没有任何公开歌单:只解释为什么空 -->
    <div v-if="me && !signedIn && !shared.length" class="mx-auto max-w-md rounded-2xl p-6 text-center"
         :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)' }">
      <p class="font-semibold">{{ t('pl.needSignIn') }}</p>
      <p class="mt-2 text-sm" :style="{ color: 'var(--c-text-muted)' }">{{ t('pl.needSignInHint') }}</p>
    </div>

    <div v-else class="grid gap-6 md:grid-cols-[16rem_1fr]">
      <!-- 歌单列表 -->
      <aside>
        <div v-if="!signedIn" class="rounded-xl p-3 text-xs leading-relaxed"
             :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)', color: 'var(--c-text-muted)' }">
          <p class="font-semibold" :style="{ color: 'var(--c-text)' }">{{ t('pl.needSignIn') }}</p>
          <p class="mt-1">{{ t('pl.guestShared') }}</p>
        </div>
        <template v-else>
        <form class="flex gap-2" @submit.prevent="create">
          <input
            ref="newNameInput"
            v-model="newName"
            maxlength="60"
            :placeholder="t('pl.newPlaceholder')"
            :aria-label="t('pl.newPlaceholder')"
            class="min-w-0 flex-1 rounded-full border px-4 py-2 text-sm"
            :style="{ background: 'var(--c-surface)', borderColor: 'var(--c-border)', color: 'var(--c-text)' }"
          />
          <button
            type="submit"
            class="cursor-pointer rounded-full border-0 px-3.5 text-sm font-semibold"
            :style="{ background: 'var(--c-accent)', color: 'var(--c-on-accent)' }"
            :title="t('pl.create')"
            :aria-label="t('pl.create')"
          ><Icon icon="plus" /></button>
        </form>
        <button
          class="mt-2 w-full cursor-pointer rounded-full border-0 px-4 py-2 text-xs font-medium"
          :style="{ background: importOpen ? 'var(--c-accent-soft)' : 'var(--c-surface-2)', color: importOpen ? 'var(--c-accent)' : 'var(--c-text)' }"
          :aria-expanded="importOpen"
          :aria-controls="importOpen ? 'pl-import-panel' : undefined"
          @click="importOpen = !importOpen"
        ><Icon icon="file-import" class="mr-1.5" />{{ t('pl.importToggle') }}</button>
        <div v-if="importOpen" id="pl-import-panel" class="mt-2 rounded-xl p-3 text-xs"
             :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)' }">
          <form class="flex flex-col gap-2" @submit.prevent="runImport">
            <input
              v-model="importUrl"
              type="url"
              required
              autocapitalize="none"
              autocorrect="off"
              spellcheck="false"
              :placeholder="t('pl.importLink')"
              :aria-label="t('pl.importLink')"
              aria-describedby="pl-import-hint"
              class="rounded-lg border px-3 py-1.5 text-xs"
              :style="{ background: 'var(--c-bg)', borderColor: 'var(--c-border)', color: 'var(--c-text)' }"
              :disabled="importRunning"
            />
            <select
              v-model="importInto"
              :aria-label="t('pl.importTarget')"
              class="rounded-lg border px-2 py-1.5 text-xs"
              :style="{ background: 'var(--c-bg)', borderColor: 'var(--c-border)', color: 'var(--c-text)' }"
              :disabled="importRunning"
            >
              <option value="new">{{ t('pl.importNew') }}</option>
              <option v-if="detail?.mine" value="current">{{ t('pl.importInto', { name: detail.name }) }}</option>
            </select>
            <!-- aria-disabled keeps focus on the button while the import runs; `required` covers the empty link -->
            <button type="submit" class="cursor-pointer rounded-lg border-0 px-3 py-1.5 text-xs font-semibold aria-disabled:cursor-default aria-disabled:opacity-60"
                    :style="{ background: 'var(--c-accent)', color: 'var(--c-on-accent)' }"
                    :aria-disabled="importBusy || undefined">{{ t('pl.import') }}</button>
          </form>
          <p id="pl-import-hint" class="mt-2 leading-relaxed" :style="{ color: 'var(--c-text-faint)' }">
            {{ t('pl.importHint') }}
          </p>
          <template v-if="importJob && importRunning">
            <p id="pl-import-progress" class="mt-2" :style="{ color: 'var(--c-text-muted)' }">{{ importProgress }}</p>
            <progress v-if="importJob.total" class="bar mt-1" :value="importJob.processed" :max="importJob.total"
                      aria-labelledby="pl-import-progress" />
          </template>
          <p v-if="importError" class="mt-2" :style="{ color: 'var(--c-danger)' }">{{ importError }}</p>
          <details v-if="importJob?.status === 'done' && importJob.unmatched?.length" class="mt-2">
            <summary class="cursor-pointer" :style="{ color: 'var(--c-text-muted)' }">
              {{ t('pl.notFound', { n: importJob.unmatched.length }) }}
            </summary>
            <ul class="mt-1 max-h-32 overflow-y-auto pl-3" :style="{ color: 'var(--c-text-faint)' }">
              <li v-for="u in importJob.unmatched" :key="u" class="truncate">{{ u }}</li>
            </ul>
          </details>
        </div>
        <h2 class="mt-5 mb-1 px-3 text-[11px] font-semibold uppercase tracking-wider" :style="{ color: 'var(--c-text-faint)' }">
          {{ t('pl.mine') }}
        </h2>
        <ul role="list" class="flex flex-col gap-1">
          <li v-if="!hasFavorites">
            <button
              class="flex w-full cursor-pointer items-center justify-between gap-2 rounded-xl border-0 px-3 py-2.5 text-left"
              :style="favHint
                ? { background: 'var(--c-accent-soft)', color: 'var(--c-accent)' }
                : { background: 'transparent', color: 'var(--c-text)' }"
              :aria-current="favHint || undefined"
              @click="favHint = true; selectedId = null; detail = null"
            >
              <span class="flex min-w-0 items-center gap-2 text-sm font-medium">
                <Icon icon="heart" class="shrink-0" :style="{ color: 'var(--c-danger)' }" />
                <span class="truncate">{{ t('fav.name') }}</span>
              </span>
              <span class="shrink-0 text-xs tabular-nums" :style="{ color: 'var(--c-text-faint)' }">0</span>
            </button>
          </li>
          <li v-for="pl in sortedPlaylists" :key="pl.id">
            <button
              class="flex w-full cursor-pointer items-center justify-between gap-2 rounded-xl border-0 px-3 py-2.5 text-left"
              :style="pl.id === selectedId
                ? { background: 'var(--c-accent-soft)', color: 'var(--c-accent)' }
                : { background: 'transparent', color: 'var(--c-text)' }"
              :aria-current="pl.id === selectedId || undefined"
              @click="select(pl.id)"
            >
              <span class="flex min-w-0 items-center gap-2 text-sm font-medium">
                <Icon v-if="pl.favorites" icon="heart" class="shrink-0" :style="{ color: 'var(--c-danger)' }" />
                <span class="truncate">{{ plName(pl) }}</span>
              </span>
              <span class="flex shrink-0 items-center gap-1.5 text-xs tabular-nums" :style="{ color: 'var(--c-text-faint)' }">
                <Icon v-if="pl.public" icon="globe" :title="t('pl.publicBadge')" />{{ pl.count }}
              </span>
            </button>
          </li>
        </ul>
        <p v-if="!playlists.length" class="mt-1 px-3 text-sm" :style="{ color: 'var(--c-text-faint)' }">
          <template v-for="(p, k) in tParts('pl.noneYet', { heart: 'heart' })" :key="k"><template v-if="p.param"><Icon icon="heart" :style="{ color: 'var(--c-danger)' }" /><span class="sr-only">{{ t('fav.heartWord') }}</span></template><template v-else>{{ p.text }}</template></template>
        </p>
        </template>

        <!-- 大家公开的歌单 -->
        <template v-if="shared.length">
          <h2 class="mt-5 mb-1 px-3 text-[11px] font-semibold uppercase tracking-wider" :style="{ color: 'var(--c-text-faint)' }">
            {{ t('pl.shared') }}
          </h2>
          <ul role="list" class="flex flex-col gap-1">
            <li v-for="pl in shared" :key="pl.id">
              <button
                class="flex w-full cursor-pointer items-center justify-between gap-2 rounded-xl border-0 px-3 py-2 text-left"
                :style="pl.id === selectedId
                  ? { background: 'var(--c-accent-soft)', color: 'var(--c-accent)' }
                  : { background: 'transparent', color: 'var(--c-text)' }"
                :aria-current="pl.id === selectedId || undefined"
                @click="select(pl.id)"
              >
                <span class="min-w-0">
                  <span class="block truncate text-sm font-medium">{{ pl.name }}</span>
                  <span class="block truncate text-[11px]" :style="{ color: 'var(--c-text-muted)' }">{{ pl.owner_name }}</span>
                </span>
                <span class="shrink-0 text-xs tabular-nums" :style="{ color: 'var(--c-text-faint)' }">{{ pl.count }}</span>
              </button>
            </li>
          </ul>
        </template>
        <p v-else-if="signedIn" class="mt-5 px-3 text-xs leading-relaxed" :style="{ color: 'var(--c-text-faint)' }">
          {{ t('pl.sharedNone') }}
        </p>
      </aside>

      <!-- 还没有"我喜欢的音乐":说明怎么用 -->
      <div v-if="favHint && !detail" class="min-w-0">
        <h1 class="flex items-center gap-2 text-2xl font-semibold">
          <Icon icon="heart" :style="{ color: 'var(--c-danger)' }" />{{ t('fav.name') }}
        </h1>
        <div class="mt-4 rounded-2xl p-6 text-center text-sm"
             :style="{ background: 'var(--c-surface)', color: 'var(--c-text-muted)' }">
          <template v-for="(p, k) in tParts('fav.hint', { heart: 'heart' })" :key="k"><template v-if="p.param"><Icon icon="heart" :style="{ color: 'var(--c-danger)' }" /><span class="sr-only">{{ t('fav.heartWord') }}</span></template><template v-else>{{ p.text }}</template></template>
        </div>
      </div>

      <!-- 歌单详情 -->
      <div v-else-if="detail" class="min-w-0">
        <div class="flex flex-wrap items-end justify-between gap-3">
          <div class="min-w-0">
            <form v-if="renaming" class="flex gap-2" @submit.prevent="rename">
              <input
                ref="renameInput"
                v-model="renameDraft"
                maxlength="60"
                :aria-label="t('pl.nameLabel')"
                class="min-w-0 rounded-lg border px-3 py-1.5 text-lg font-semibold"
                :style="{ background: 'var(--c-surface)', borderColor: 'var(--c-border)', color: 'var(--c-text)' }"
                @keydown.esc="cancelRename"
              />
              <button type="submit" class="cursor-pointer rounded-lg border-0 px-3 text-xs font-semibold"
                      :style="{ background: 'var(--c-accent)', color: 'var(--c-on-accent)' }">{{ t('common.save') }}</button>
            </form>
            <!-- The name wraps instead of truncating, and the actions sit outside the heading so a long name cannot push them out. -->
            <div v-else class="flex items-baseline gap-2">
              <h1 class="min-w-0 text-2xl font-semibold text-balance [overflow-wrap:anywhere]">
                <Icon v-if="detail.favorites" icon="heart" class="mr-2" :style="{ color: 'var(--c-danger)' }" />{{ plName(detail) }}
              </h1>
              <div v-if="detail.mine" class="flex shrink-0 items-center gap-2">
                <!-- 改了名就不再是收藏歌单了,所以收藏歌单不给改名 -->
                <button v-if="!detail.favorites" ref="renameBtn" class="cursor-pointer border-0 bg-transparent p-0 text-sm" :style="{ color: 'var(--c-text-faint)' }"
                        :title="t('pl.rename')" :aria-label="t('pl.rename')"
                        @click="startRename"><Icon icon="pen" /></button>
                <button class="cursor-pointer border-0 bg-transparent p-0 text-sm" :style="{ color: 'var(--c-text-faint)' }"
                        :title="t('pl.delete')" :aria-label="t('pl.delete')" @click="remove"><Icon icon="trash-can" /></button>
              </div>
            </div>
            <p class="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm" :style="{ color: 'var(--c-text-muted)' }">
              <template v-if="!detail.mine">
                <span>{{ t('pl.by', { name: detail.owner_name ?? '?' }) }}</span>
                <span aria-hidden="true">·</span>
              </template>
              <span>{{ t('common.songs', { n: detail.items.length }) }}<template v-if="totalDuration"> · {{ formatTime(totalDuration) }}</template></span>
              <button
                v-if="detail.mine"
                class="cursor-pointer rounded-full border-0 px-2.5 py-0.5 text-xs font-medium"
                :style="detail.public
                  ? { background: 'var(--c-accent-soft)', color: 'var(--c-accent)' }
                  : { background: 'var(--c-surface-2)', color: 'var(--c-text-muted)' }"
                :title="t(detail.public ? 'pl.makePrivateHint' : 'pl.makePublicHint')"
                :aria-pressed="detail.public"
                @click="togglePublic"
              ><Icon :icon="detail.public ? 'globe' : 'lock'" class="mr-1" />{{ t(detail.public ? 'pl.public' : 'pl.private') }}</button>
            </p>
          </div>
          <div class="flex flex-wrap gap-2">
            <button
              class="cursor-pointer rounded-full border-0 px-4 py-2 text-sm font-semibold"
              :style="{ background: 'var(--c-accent)', color: 'var(--c-on-accent)' }"
              :disabled="!detail.items.length"
              :aria-disabled="busy || undefined"
              :title="t('pl.playNowHint')"
              @click="play('replace')"
            ><Icon icon="play" class="mr-1.5" />{{ t('pl.playNow') }}</button>
            <button
              class="cursor-pointer rounded-full border-0 px-3.5 py-2 text-sm"
              :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
              :disabled="!detail.items.length"
              :aria-disabled="busy || undefined"
              @click="play('replace', { shuffle: true })"
            ><Icon icon="shuffle" class="mr-1.5" />{{ t('pl.shuffle') }}</button>
            <button
              class="cursor-pointer rounded-full border-0 px-3.5 py-2 text-sm"
              :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
              :disabled="!detail.items.length"
              :aria-disabled="busy || undefined"
              @click="play('append')"
            ><Icon icon="plus" class="mr-1.5" />{{ t('pl.queueAll') }}</button>
            <button
              v-if="!detail.mine && signedIn"
              class="cursor-pointer rounded-full border-0 px-3.5 py-2 text-sm"
              :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
              :title="t('pl.copyHint')"
              @click="copyToMine"
            ><Icon icon="copy" class="mr-1.5" />{{ t('pl.copy') }}</button>
          </div>
        </div>

        <!-- announced via announce(); no live region here so it is not read twice -->
        <p v-if="toast" class="mt-3 rounded-lg px-3 py-2 text-sm"
           :style="toastErr
             ? { background: 'var(--c-surface-2)', color: 'var(--c-danger)' }
             : { background: 'var(--c-accent-soft)', color: 'var(--c-accent)' }"
        ><Icon v-if="toastErr" icon="triangle-exclamation" class="mr-1.5" />{{ toast }}</p>

        <ul v-if="detail.items.length" ref="itemList" role="list" class="mt-4 flex flex-col gap-1.5">
          <li
            v-for="(e, i) in visibleItems"
            :key="e.id"
            class="group flex items-center gap-3 rounded-xl px-3 py-2"
            :class="detail.mine ? 'cursor-grab active:cursor-grabbing' : ''"
            :style="{
              background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)',
              ...(dragOver === i && dragFrom !== null && dragFrom !== i ? { outline: '2px solid var(--c-accent)', outlineOffset: '-2px' } : {}),
              ...(dragFrom === i ? { opacity: 0.4 } : {}),
            }"
            :draggable="detail.mine"
            @dragstart="detail.mine && (dragFrom = i)"
            @dragover.prevent="detail.mine && (dragOver = i)"
            @drop.prevent="onDrop(i)"
            @dragend="dragFrom = null; dragOver = null"
          >
            <span class="w-5 shrink-0 text-right text-xs tabular-nums" :style="{ color: 'var(--c-text-faint)' }">{{ i + 1 }}</span>
            <div class="min-w-0 flex-1">
              <p class="truncate text-sm font-medium" :title="e.title">{{ e.title || e.ref }}</p>
              <p class="truncate text-xs" :style="{ color: 'var(--c-text-muted)' }">
                {{ [typeLabel(e.type), e.duration ? formatTime(e.duration) : ''].filter(Boolean).join(' · ') }}
              </p>
            </div>
            <div class="flex shrink-0 items-center gap-1 opacity-60 transition-opacity group-focus-within:opacity-100 group-hover:opacity-100">
              <button class="cursor-pointer rounded-md border-0 px-2 py-1 text-xs"
                      :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
                      :title="t('common.playNext')" :aria-label="t('common.playNext')"
                      @click="play('next', { item: e.id })"><Icon icon="arrow-turn-up" /></button>
              <button class="cursor-pointer rounded-md border-0 px-2 py-1 text-xs"
                      :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
                      :title="t('common.addToQueue')" :aria-label="t('common.addToQueue')"
                      @click="play('append', { item: e.id })"><Icon icon="plus" /></button>
              <FavButton v-if="signedIn && !detail.favorites" :item-id="e.item_id"
                         :source="{ source: 'playlist_entry', playlist_id: detail.id, entry: e.id }" />
              <button v-if="detail.mine" class="cursor-pointer rounded-md border-0 px-2 py-1 text-xs"
                      :style="{ background: 'var(--c-surface-2)', color: 'var(--c-danger)' }"
                      :title="t('pl.removeItem')" :aria-label="t('pl.removeItem')" data-remove
                      @click="dropItem(e.id, i)"><Icon icon="xmark" /></button>
              <AddToPlaylist v-else :source="{ source: 'playlist_entry', playlist_id: detail.id, entry: e.id }" />
            </div>
          </li>
        </ul>
        <button v-if="detail.items.length > visibleItems.length"
                class="mt-2 w-full cursor-pointer rounded-xl border-0 px-3 py-2 text-xs font-medium"
                :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
                @click="revealAllItems">{{ t('queue.showAll', { n: detail.items.length }) }}</button>
        <div v-else-if="!detail.items.length && detail.mine" class="mt-6 rounded-2xl p-6 text-center text-sm"
             :style="{ background: 'var(--c-surface)', color: 'var(--c-text-muted)' }">
          <p>{{ t('pl.empty') }}</p>
          <p class="mt-1"><template v-for="(p, k) in tParts(detail.favorites ? 'fav.hint' : 'pl.emptyHint', { heart: 'heart' })" :key="k"><template v-if="p.param"><Icon icon="heart" :style="{ color: 'var(--c-danger)' }" /><span class="sr-only">{{ t('fav.heartWord') }}</span></template><template v-else>{{ p.text }}</template></template></p>
          <button class="mt-3 cursor-pointer rounded-full border-0 px-4 py-2 text-xs font-semibold"
                  :style="{ background: 'var(--c-accent-soft)', color: 'var(--c-accent)' }"
                  @click="saveQueue">{{ t('pl.saveQueueHere') }}</button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
/* Native <progress> (exposes role=progressbar and its value), restyled as the thin accent bar. */
.bar {
  appearance: none;
  border: 0 solid;
  overflow: clip;
  display: block;
  inline-size: 100%;
  block-size: 0.25rem;
  border-radius: 1e5px;
  background: var(--c-surface-2);
}

.bar::-webkit-progress-bar {
  background: transparent;
}

.bar::-webkit-progress-value {
  background: var(--c-accent);
  border-radius: 1e5px;
  transition: inline-size 0.4s;
}

.bar::-moz-progress-bar {
  background: var(--c-accent);
  border-radius: 1e5px;
  transition: inline-size 0.4s;
}
</style>
