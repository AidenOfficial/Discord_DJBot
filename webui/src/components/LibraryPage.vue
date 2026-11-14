<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { enqueueLibraryItem, fetchLibraryInfo, formatBytes, queryLibrary, type LibraryItem } from '../api'
import { uploadFile, UploadError } from '../upload'
import { useStatus } from '../composables/useStatus'
import { announce } from '../composables/useAnnounce'
import AddToPlaylist from './AddToPlaylist.vue'
import FavButton from './FavButton.vue'
import { t, typeLabel } from '../i18n'
import type { Key } from '../i18n/en'

const { refresh } = useStatus()

const keywords = ref('')
const typeFilter = ref<'file' | 'url' | 'radio' | ''>('')
const tagFilter = ref('')
const allTags = ref<string[]>([])
const uploadEnabled = ref(false)
const items = ref<LibraryItem[]>([])
const totalPages = ref(0)
const page = ref(1)
const loading = ref(false)
const feedback = ref<Record<string, string>>({})

onMounted(async () => {
  try {
    const info = await fetchLibraryInfo()
    allTags.value = info.tags ?? []
    uploadEnabled.value = !!info.upload_enabled
  } catch { /* non-fatal */ }
  query()
})

let debounce: ReturnType<typeof setTimeout> | undefined
function onInput() {
  clearTimeout(debounce)
  debounce = setTimeout(() => query(1), 400)
}

async function query(toPage = 1) {
  loading.value = true
  page.value = toPage
  try {
    const data = await queryLibrary({
      type: typeFilter.value || 'file,url,radio',
      tags: tagFilter.value,
      keywords: keywords.value,
      page: toPage,
    })
    items.value = data.items ?? []
    totalPages.value = data.total_pages ?? 0
  } catch {
    items.value = []
    totalPages.value = 0
  } finally {
    loading.value = false
  }
}

const feedbackTimers = new Map<string, ReturnType<typeof setTimeout>>()

// The Queue / Next buttons stay mounted (and focused) while this runs; the result
// shows beside them. A failure stays until the next attempt on that row.
async function add(item: LibraryItem, next: boolean) {
  if (feedback.value[item.id] === '...') return
  clearTimeout(feedbackTimers.get(item.id))
  feedback.value[item.id] = '...'
  try {
    await enqueueLibraryItem(item.id, next ? 'next' : 'append')
    feedback.value[item.id] = 'ok'
    announce(t('lib.queuedItem', {
      verb: t(next ? 'pl.verbNext' : 'pl.verbAppend'),
      title: item.title || item.path,
    }))
    refresh()
    feedbackTimers.set(item.id, setTimeout(() => delete feedback.value[item.id], 2000))
  } catch {
    feedback.value[item.id] = 'err'
    announce(t('lib.queueFailed'), { assertive: true })
  }
}

function goPage(to: number) {
  if (to < 1 || to > totalPages.value) return
  query(to)
}

interface UploadRow {
  key: number
  name: string
  sent: number
  total: number
  phase: 'uploading' | 'processing' | 'done' | 'error'
  message: string
  itemId?: string
  queued?: boolean
  queueFailed?: boolean
  ctrl: AbortController
}
const uploads = ref<UploadRow[]>([])
let uploadSeq = 0

const UPLOAD_ERRORS = ['too_large', 'unsupported_type', 'no_space', 'network', 'aborted']

async function onUpload(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files ?? [])
  input.value = ''
  // 依次上传,避免多个大文件同时抢带宽
  for (const file of files) {
    const row = reactive<UploadRow>({
      key: ++uploadSeq, name: file.name, sent: 0, total: file.size, phase: 'uploading',
      message: '', ctrl: new AbortController(),
    })
    uploads.value.unshift(row)
    try {
      const rv = await uploadFile(file, (p) => {
        row.sent = p.sent
        row.phase = p.phase
      }, { signal: row.ctrl.signal })
      if (rv.status === 'done') {
        row.phase = 'done'
        row.itemId = rv.item_id
        row.message = rv.extracted
          ? t('lib.savedAudio', { size: formatBytes(rv.final_size ?? 0) })
          : t('lib.savedAs', { path: rv.path ?? '' })
        query(page.value)
        announce(`${row.name}: ${row.message}`)
      } else {
        row.phase = 'error'
        row.message = rv.error ?? t('lib.processFailed')
        announce(`${row.name}: ${row.message}`, { assertive: true })
      }
    } catch (err) {
      row.phase = 'error'
      row.message = !(err instanceof UploadError) ? t('lib.uploadFailed')
        : UPLOAD_ERRORS.includes(err.code) ? t(`upload.${err.code}` as Key)
        : t('lib.uploadFailedCode', { code: err.code })
      const cancelled = err instanceof UploadError && err.code === 'aborted'
      announce(`${row.name}: ${row.message}`, { assertive: !cancelled })
    }
  }
}

async function queueUpload(row: UploadRow) {
  if (!row.itemId) return
  row.queueFailed = false
  try {
    await enqueueLibraryItem(row.itemId, 'append')
    row.queued = true
    announce(t('lib.queuedItem', { verb: t('pl.verbAppend'), title: row.name }))
    refresh()
  } catch {
    row.queueFailed = true
    row.message = t('lib.queueFailed')
    announce(t('lib.queueFailed'), { assertive: true })
  }
}

const TYPES = ['', 'file', 'url', 'radio'] as const
</script>

<template>
  <section class="mx-auto w-full max-w-3xl px-4 py-8">
    <!-- filters -->
    <div class="flex flex-col gap-3">
      <input
        v-model="keywords"
        type="search"
        :placeholder="t('lib.filter')"
        :aria-label="t('lib.filter')"
        class="w-full rounded-full border px-5 py-2.5 text-sm"
        :style="{ background: 'var(--c-surface)', borderColor: 'var(--c-border)', color: 'var(--c-text)' }"
        @input="onInput"
      />
      <div class="flex flex-wrap items-center gap-2">
        <div class="flex gap-1 rounded-full p-1" :style="{ background: 'var(--c-surface-2)' }">
          <button
            v-for="k in TYPES"
            :key="k"
            class="cursor-pointer rounded-full border-0 px-3 py-1 text-xs font-medium"
            :style="typeFilter === k
              ? { background: 'var(--c-accent)', color: 'var(--c-on-accent)' }
              : { background: 'transparent', color: 'var(--c-text-muted)' }"
            :aria-pressed="typeFilter === k"
            @click="typeFilter = k; query(1)"
          >{{ k ? typeLabel(k) : t('common.all') }}</button>
        </div>
        <select
          v-if="allTags.length"
          v-model="tagFilter"
          :aria-label="t('lib.tagFilter')"
          class="rounded-full border px-3 py-1.5 text-xs"
          :style="{ background: 'var(--c-surface)', borderColor: 'var(--c-border)', color: 'var(--c-text)' }"
          @change="query(1)"
        >
          <option value="">{{ t('lib.allTags') }}</option>
          <option v-for="tag in allTags" :key="tag" :value="tag">{{ tag }}</option>
        </select>
        <!-- The input stays in the tab order (sr-only, not display:none); the label shows its focus ring. -->
        <label
          v-if="uploadEnabled"
          class="relative ml-auto cursor-pointer rounded-full px-3 py-1.5 text-xs font-medium has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-offset-2 has-[:focus-visible]:outline-[var(--c-accent)]"
          :style="{ background: 'var(--c-accent-soft)', color: 'var(--c-accent)' }"
        >
          <Icon icon="upload" class="mr-1" />{{ t('lib.upload') }}
          <input type="file" accept="audio/*,video/*,.mkv,.flv" multiple class="sr-only" @change="onUpload" />
        </label>
      </div>
      <!-- 上传进度 -->
      <ul v-if="uploads.length" role="list" class="flex flex-col gap-1.5">
        <li v-for="u in uploads" :key="u.key" class="rounded-xl px-3 py-2"
            :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)' }">
          <div class="flex items-center gap-2 text-xs">
            <span class="min-w-0 flex-1 truncate font-medium" :title="u.name">{{ u.name }}</span>
            <span class="shrink-0 tabular-nums" :style="{ color: 'var(--c-text-muted)' }">
              <template v-if="u.phase === 'uploading'">{{ formatBytes(u.sent) }} / {{ formatBytes(u.total) }}</template>
              <template v-else-if="u.phase === 'processing'">{{ t('lib.processing') }}</template>
            </span>
            <button v-if="u.phase === 'uploading'" class="shrink-0 cursor-pointer border-0 bg-transparent p-0 text-xs"
                    :style="{ color: 'var(--c-text-faint)' }" :title="t('common.cancel')" :aria-label="t('common.cancel')"
                    @click="u.ctrl.abort()"><Icon icon="xmark" /></button>
            <button v-if="u.phase === 'done' && u.itemId && !u.queued"
                    class="shrink-0 cursor-pointer rounded-md border-0 px-2 py-0.5 text-xs font-semibold"
                    :style="{ background: 'var(--c-accent)', color: 'var(--c-on-accent)' }"
                    @click="queueUpload(u)"><Icon icon="plus" class="mr-1" />{{ t('common.queue') }}</button>
            <span v-if="u.queued" class="shrink-0" :style="{ color: 'var(--c-accent)' }"><Icon icon="check" class="mr-1" />{{ t('common.queued') }}</span>
          </div>
          <progress v-if="u.phase === 'uploading'" class="bar mt-1.5" :value="u.sent" :max="Math.max(u.total, 1)"
                    :aria-label="u.name" />
          <!-- no value = indeterminate while the server extracts audio -->
          <progress v-else-if="u.phase === 'processing'" class="bar mt-1.5" :aria-label="u.name" />
          <p v-if="u.message" class="mt-1 text-xs"
             :style="{ color: u.phase === 'error' || u.queueFailed ? 'var(--c-danger)' : 'var(--c-success)' }">{{ u.message }}</p>
        </li>
      </ul>
    </div>

    <!-- results -->
    <ul v-if="items.length" role="list" class="mt-4 flex flex-col gap-1.5">
      <li
        v-for="item in items"
        :key="item.id"
        class="flex items-center gap-3 rounded-xl px-3 py-2"
        :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)' }"
      >
        <div class="h-10 w-10 shrink-0 overflow-hidden rounded-lg" :style="{ background: 'var(--c-surface-2)' }">
          <img v-if="item.thumb && item.thumb.startsWith('data:')" :src="item.thumb" alt="" class="h-full w-full object-cover" />
          <div v-else class="flex h-full w-full items-center justify-center opacity-40">
            <Icon icon="music" />
          </div>
        </div>
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm font-medium" :title="item.title">{{ item.title || item.path }}</p>
          <p class="flex items-center gap-1.5 truncate text-xs" :style="{ color: 'var(--c-text-muted)' }">
            <span v-if="item.artist">{{ item.artist }}</span>
            <span v-for="tag in item.tags.slice(0, 3)" :key="tag" class="rounded-full px-1.5 py-0.5 text-[10px]" :style="{ background: 'var(--c-accent-soft)', color: 'var(--c-accent)' }">{{ tag }}</span>
          </p>
        </div>
        <div class="flex shrink-0 items-center gap-1">
          <!-- result is announced; the icon is the visual echo -->
          <span v-if="feedback[item.id]" class="px-1 text-xs" aria-hidden="true"
                :style="{ color: feedback[item.id] === 'err' ? 'var(--c-danger)' : 'var(--c-accent)' }">
            <Icon v-if="feedback[item.id] === 'ok'" icon="check" />
            <Icon v-else-if="feedback[item.id] === 'err'" icon="xmark" />
            <template v-else>...</template>
          </span>
          <FavButton :item-id="item.id" :source="{ source: 'library', item_id: item.id }" />
          <AddToPlaylist :source="{ source: 'library', item_id: item.id }" />
          <button
            class="cursor-pointer rounded-md border-0 px-2 py-1 text-xs aria-disabled:opacity-60"
            :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
            :title="t('common.playNext')"
            :aria-disabled="feedback[item.id] === '...' || undefined"
            @click="add(item, true)"
          ><Icon icon="arrow-turn-up" class="mr-1" />{{ t('lib.next') }}</button>
          <button
            class="cursor-pointer rounded-md border-0 px-2.5 py-1 text-xs font-semibold aria-disabled:opacity-60"
            :style="{ background: 'var(--c-accent)', color: 'var(--c-on-accent)' }"
            :title="t('common.addToQueue')"
            :aria-disabled="feedback[item.id] === '...' || undefined"
            @click="add(item, false)"
          ><Icon icon="plus" class="mr-1" />{{ t('common.queue') }}</button>
        </div>
      </li>
    </ul>
    <p v-else-if="!loading" class="mt-8 text-center text-sm" :style="{ color: 'var(--c-text-muted)' }">
      {{ t('lib.empty') }}
    </p>

    <!-- pagination -->
    <div v-if="totalPages > 1" class="mt-4 flex items-center justify-center gap-2 text-xs">
      <!-- aria-disabled, not disabled: reaching the last page must not drop focus from the button -->
      <button
        class="cursor-pointer rounded-full border-0 px-3 py-1.5 aria-disabled:cursor-default aria-disabled:opacity-50"
        :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
        :aria-disabled="page <= 1 || undefined"
        @click="goPage(page - 1)"
      ><Icon icon="angle-left" class="mr-1" />{{ t('lib.prev') }}</button>
      <span class="tabular-nums" :style="{ color: 'var(--c-text-muted)' }">{{ page }} / {{ totalPages }}</span>
      <button
        class="cursor-pointer rounded-full border-0 px-3 py-1.5 aria-disabled:cursor-default aria-disabled:opacity-50"
        :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
        :aria-disabled="page >= totalPages || undefined"
        @click="goPage(page + 1)"
      >{{ t('lib.nextPage') }}<Icon icon="angle-right" class="ml-1" /></button>
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
  /* lets the indeterminate fill move in track units (cqi) */
  container-type: inline-size;
  --bar-indeterminate-duration: 1.5s;
}

@media (prefers-reduced-motion: reduce) {
  .bar {
    --bar-indeterminate-duration: 10s;
  }
}

.bar:indeterminate {
  --bar-animation: lib-bar-indeterminate var(--bar-indeterminate-duration) infinite linear;
}

.bar::-webkit-progress-bar {
  background: transparent;
}

.bar::-webkit-progress-value {
  background: var(--c-accent);
  border-radius: 1e5px;
  transition: inline-size 0.3s;
  animation: var(--bar-animation, revert-rule);
}

.bar::-moz-progress-bar {
  background: var(--c-accent);
  border-radius: 1e5px;
  transition: inline-size 0.3s;
  animation: var(--bar-animation, revert-rule);
}
</style>

<style>
/* Unscoped on purpose: the name is referenced from a custom property, which
   Vue's scoped keyframe renaming does not rewrite. */
@keyframes lib-bar-indeterminate {
  from, to {
    inline-size: 30%;
    margin-right: auto;
  }
  from { translate: -100%; }
  to { translate: 100cqi; }
}
</style>
