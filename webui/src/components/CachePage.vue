<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  cleanupCache, deleteCache, fetchCache, formatBytes, pinCache, saveCacheToLibrary,
  type CacheEntry, type CacheSummary,
} from '../api'
import { formatTime } from '../composables/useStatus'
import { t, timeAgo } from '../i18n'
import { announce } from '../composables/useAnnounce'
import { useConfirm } from '../composables/useConfirm'

const { confirm } = useConfirm()

const summary = ref<CacheSummary | null>(null)
const entries = ref<CacheEntry[]>([])
const loading = ref(false)
const toast = ref('')
const toastOk = ref(true)
const rowBusy = ref<Record<string, boolean>>({})
const filter = ref<'all' | 'pinned' | 'frequent' | 'cold'>('all')
const sortBy = ref<'last_used' | 'size' | 'plays'>('last_used')

let toastTimer: ReturnType<typeof setTimeout> | undefined
/** Failures stay until the next message or until dismissed; successes fade after 3.5 s. */
function say(msg: string, ok = true) {
  toast.value = msg
  toastOk.value = ok
  clearTimeout(toastTimer)
  if (ok) toastTimer = setTimeout(() => (toast.value = ''), 3500)
  announce(msg, { assertive: !ok })
}
function dismissToast() {
  clearTimeout(toastTimer)
  toast.value = ''
}

async function reload() {
  loading.value = true
  try {
    const data = await fetchCache()
    summary.value = data.summary
    entries.value = data.entries
  } catch {
    say(t('cache.loadFailed'), false)
  } finally {
    loading.value = false
  }
}
onMounted(reload)

const shown = computed(() => {
  let list = entries.value
  if (filter.value === 'pinned') list = list.filter((e) => e.pinned)
  else if (filter.value === 'frequent') list = list.filter((e) => e.frequent)
  else if (filter.value === 'cold') list = list.filter((e) => !e.pinned && !e.frequent && !e.in_queue)
  const key = sortBy.value
  return [...list].sort((a, b) => (b[key] as number) - (a[key] as number))
})

const usedPct = computed(() => {
  const s = summary.value
  if (!s || !s.limit_bytes) return 0
  return Math.min(100, (s.total_bytes / s.limit_bytes) * 100)
})
const pinnedPct = computed(() => {
  const s = summary.value
  if (!s || !s.limit_bytes) return 0
  return Math.min(100, (s.pinned_bytes / s.limit_bytes) * 100)
})

async function togglePin(e: CacheEntry) {
  rowBusy.value[e.id] = true
  try {
    await pinCache(e.id, !e.pinned)
    e.pinned = !e.pinned
    say(t(e.pinned ? 'cache.pinned' : 'cache.unpinned'))
    reload()
  } catch {
    say(t('cache.pinFailed'), false)
  } finally {
    rowBusy.value[e.id] = false
  }
}

async function remove(e: CacheEntry) {
  const force = e.in_queue
  if (force && !(await confirm({ message: t('cache.confirmQueued'), confirmLabel: t('common.delete'), destructive: true }))) return
  rowBusy.value[e.id] = true
  try {
    const freed = await deleteCache(e.id, force)
    say(t('cache.freed', { size: formatBytes(freed) }))
    reload()
  } catch (err) {
    say(t(err instanceof Error && err.message === 'busy' ? 'cache.busy' : 'cache.deleteFailed'), false)
  } finally {
    rowBusy.value[e.id] = false
  }
}

async function saveToLibrary(e: CacheEntry) {
  rowBusy.value[e.id] = true
  try {
    const rv = await saveCacheToLibrary(e.id)
    say(t('cache.savedTo', { path: rv.path }))
  } catch {
    say(t('cache.saveFailed'), false)
  } finally {
    rowBusy.value[e.id] = false
  }
}

async function cleanup(mode: 'limit' | 'expired' | 'unpinned') {
  if (mode === 'unpinned' && !(await confirm({ message: t('cache.confirmUnpinned'), confirmLabel: t('common.delete'), destructive: true }))) return
  loading.value = true
  try {
    const rv = await cleanupCache(mode)
    say(rv.freed ? t('cache.freed', { size: formatBytes(rv.freed) }) : t('cache.nothing'))
  } catch {
    say(t('cache.cleanupFailed'), false)
  }
  await reload()
}

// 每行按钮的名字带上标题,读屏在一串"删除"里能分清是哪一条
const entryName = (e: CacheEntry) => e.title || e.url || t('cache.unknown', { id: e.id.slice(0, 8) })
const named = (action: string, e: CacheEntry) => t('common.itemAction', { action, title: entryName(e) })

const FILTERS = [
  { key: 'all', label: 'common.all' },
  { key: 'pinned', label: 'cache.fPinned' },
  { key: 'frequent', label: 'cache.fFrequent' },
  { key: 'cold', label: 'cache.fCold' },
] as const
</script>

<template>
  <section class="mx-auto w-full max-w-3xl px-4 py-8">
    <!-- 概览 -->
    <div v-if="summary" class="rounded-2xl p-5" :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)' }">
      <div class="flex flex-wrap items-baseline justify-between gap-2">
        <p class="text-2xl font-semibold tabular-nums">
          {{ formatBytes(summary.total_bytes) }}
          <span class="text-sm font-normal" :style="{ color: 'var(--c-text-muted)' }">
            <template v-if="summary.limit_bytes !== null">{{ t('cache.ofLimit', { size: formatBytes(summary.limit_bytes) }) }}</template>
            <template v-else>{{ t('cache.noLimit') }}</template>
          </span>
        </p>
        <p class="text-xs" :style="{ color: 'var(--c-text-muted)' }">
          {{ t('cache.count', { n: summary.count }) }} ·
          {{ t('cache.diskFree', { size: formatBytes(summary.disk_free) }) }}
        </p>
      </div>
      <div v-if="summary.limit_bytes" class="relative mt-3 h-2 w-full overflow-hidden rounded-full" :style="{ background: 'var(--c-surface-2)' }"
           role="meter" :aria-label="t('cache.usage')" :aria-valuenow="Math.round(usedPct)" aria-valuemin="0" aria-valuemax="100"
           :aria-valuetext="t('cache.usageText', { used: formatBytes(summary.total_bytes), limit: formatBytes(summary.limit_bytes), pct: Math.round(usedPct) })">
        <div class="absolute inset-y-0 left-0 rounded-full" :style="{ width: `${usedPct}%`, background: 'var(--c-accent)' }" />
        <div class="absolute inset-y-0 left-0 rounded-full" :style="{ width: `${pinnedPct}%`, background: 'var(--c-accent-strong)', opacity: 0.55 }" />
      </div>
      <p class="mt-2 text-[11px]" :style="{ color: 'var(--c-text-faint)' }">
        {{ t('cache.policy', { plays: summary.auto_keep_plays, days: summary.keep_days }) }}
      </p>
      <p v-if="!summary.persistent" class="mt-3 rounded-lg px-3 py-2 text-xs"
         :style="{ background: 'var(--c-accent-soft)', color: 'var(--c-danger)' }">
        {{ t('cache.ephemeral', { folder: summary.folder }) }}
      </p>
      <div class="mt-4 flex flex-wrap gap-2">
        <button class="cursor-pointer rounded-full border-0 px-3.5 py-1.5 text-xs font-semibold"
                :style="{ background: 'var(--c-accent)', color: 'var(--c-on-accent)' }"
                :disabled="loading" @click="cleanup('limit')">{{ t('cache.trim') }}</button>
        <button class="cursor-pointer rounded-full border-0 px-3.5 py-1.5 text-xs"
                :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
                :disabled="loading" @click="cleanup('expired')">{{ t('cache.expired') }}</button>
        <button class="cursor-pointer rounded-full border-0 px-3.5 py-1.5 text-xs"
                :style="{ background: 'var(--c-surface-2)', color: 'var(--c-danger)' }"
                :disabled="loading" @click="cleanup('unpinned')">{{ t('cache.clearUnpinned') }}</button>
      </div>
    </div>

    <p v-if="toast" class="mt-3 flex items-start gap-2 rounded-lg px-3 py-2 text-sm"
       :style="{ background: 'var(--c-accent-soft)', color: toastOk ? 'var(--c-accent)' : 'var(--c-danger)' }">
      <Icon :icon="toastOk ? 'check' : 'triangle-exclamation'" class="mt-1 text-xs" aria-hidden="true" />
      <span class="min-w-0 flex-1">{{ toast }}</span>
      <button
        v-if="!toastOk"
        type="button"
        class="cursor-pointer rounded border-0 bg-transparent px-1 text-xs"
        :style="{ color: 'var(--c-text-muted)' }"
        :aria-label="t('common.dismiss')"
        @click="dismissToast"
      ><Icon icon="xmark" aria-hidden="true" /></button>
    </p>

    <!-- 筛选 / 排序 -->
    <div class="mt-5 flex flex-wrap items-center gap-2">
      <div role="group" :aria-label="t('cache.filter')" class="flex gap-1 rounded-full p-1" :style="{ background: 'var(--c-surface-2)' }">
        <button v-for="f in FILTERS" :key="f.key" type="button" :aria-pressed="filter === f.key"
                class="cursor-pointer rounded-full border-0 px-3 py-1 text-xs font-medium"
                :style="filter === f.key ? { background: 'var(--c-accent)', color: 'var(--c-on-accent)' } : { background: 'transparent', color: 'var(--c-text-muted)' }"
                @click="filter = f.key">{{ t(f.label) }}</button>
      </div>
      <select v-model="sortBy" :aria-label="t('cache.sortBy')" class="ml-auto rounded-full border px-3 py-1.5 text-xs"
              :style="{ background: 'var(--c-surface)', borderColor: 'var(--c-border)', color: 'var(--c-text)' }">
        <option value="last_used">{{ t('cache.sortRecent') }}</option>
        <option value="size">{{ t('cache.sortSize') }}</option>
        <option value="plays">{{ t('cache.sortPlays') }}</option>
      </select>
    </div>

    <!-- 列表 -->
    <ul v-if="shown.length" role="list" class="mt-3 flex flex-col gap-1.5">
      <li v-for="e in shown" :key="e.id" class="flex items-center gap-3 rounded-xl px-3 py-2.5"
          :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)' }">
        <div class="min-w-0 flex-1">
          <p class="truncate text-sm font-medium" :title="e.url || e.id">
            <a v-if="e.url" :href="e.url" target="_blank" rel="noopener noreferrer" class="no-underline"
               :style="{ color: 'var(--c-text)' }">{{ e.title || e.url }}</a>
            <span v-else :style="{ color: 'var(--c-text-muted)' }">{{ e.title || t('cache.unknown', { id: e.id.slice(0, 8) }) }}</span>
          </p>
          <p class="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs" :style="{ color: 'var(--c-text-muted)' }">
            <span class="tabular-nums">{{ formatBytes(e.size) }}</span>
            <span v-if="e.duration" class="tabular-nums">{{ formatTime(e.duration) }}</span>
            <span>{{ t('common.plays', { n: e.plays }) }}</span>
            <span>{{ t('cache.used', { ago: timeAgo(e.last_used) }) }}</span>
            <span v-if="e.pinned" class="rounded-full px-1.5 py-0.5 text-[10px] font-semibold"
                  :style="{ background: 'var(--c-accent-soft)', color: 'var(--c-accent)' }">{{ t('cache.fPinned') }}</span>
            <span v-if="e.frequent" class="rounded-full px-1.5 py-0.5 text-[10px] font-semibold"
                  :style="{ background: 'var(--c-surface-2)', color: 'var(--c-success)' }">{{ t('cache.fFrequent') }}</span>
            <span v-if="e.in_queue" class="rounded-full px-1.5 py-0.5 text-[10px] font-semibold"
                  :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }">{{ t('cache.inQueue') }}</span>
            <span v-if="e.downloading" class="rounded-full px-1.5 py-0.5 text-[10px] font-semibold"
                  :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text-muted)' }">{{ t('cache.downloading') }}</span>
          </p>
        </div>
        <div class="flex shrink-0 items-center gap-1">
          <button type="button" class="cursor-pointer rounded-md border-0 px-2 py-1 text-xs"
                  :style="e.pinned ? { background: 'var(--c-accent)', color: 'var(--c-on-accent)' } : { background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
                  :title="t(e.pinned ? 'cache.unpin' : 'cache.pin')" :aria-label="named(t('cache.pin'), e)"
                  :aria-pressed="e.pinned"
                  :disabled="rowBusy[e.id]" @click="togglePin(e)"><Icon icon="thumbtack" aria-hidden="true" /></button>
          <button class="cursor-pointer rounded-md border-0 px-2 py-1 text-xs"
                  :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
                  :title="t('cache.copy')" :aria-label="named(t('cache.copy'), e)"
                  :disabled="rowBusy[e.id] || !e.complete" @click="saveToLibrary(e)"><Icon icon="floppy-disk" aria-hidden="true" /></button>
          <button class="cursor-pointer rounded-md border-0 px-2 py-1 text-xs"
                  :style="{ background: 'var(--c-surface-2)', color: 'var(--c-danger)' }"
                  :title="t('cache.delete')" :aria-label="named(t('cache.delete'), e)" :disabled="rowBusy[e.id] || e.downloading" @click="remove(e)"><Icon icon="trash-can" aria-hidden="true" /></button>
        </div>
      </li>
    </ul>
    <p v-else-if="!loading" class="mt-8 text-center text-sm" :style="{ color: 'var(--c-text-muted)' }">
      {{ t(entries.length ? 'cache.noMatch' : 'cache.empty') }}
    </p>
  </section>
</template>
