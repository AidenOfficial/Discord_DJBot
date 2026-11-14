<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { apiFetch } from '../api'
import { useGuilds } from '../composables/useGuilds'
import { formatTime } from '../composables/useStatus'
import { t, typeLabel } from '../i18n'

interface Stats {
  total_plays: number
  total_seconds: number
  unique_tracks: number
  by_type: { type: string; count: number }[]
  top_tracks: { item_id: string; title: string; count: number }[]
  top_users: { user: string; count: number }[]
  hours: number[]
  weekdays: number[]
  most_skipped: { item_id: string; title: string; count: number }[]
  busiest_day: { date: string; count: number } | null
  last_30d: { date: string; count: number }[]
}

const stats = ref<Stats | null>(null)
const error = ref(false)

// 统计哪个服务器:默认跟着顶栏选的;bot 主人还能选"全部服务器"(all)
const { guilds, owner, multi, selectedGuild } = useGuilds()
const scope = ref<string>(selectedGuild.value)
watch(selectedGuild, (id) => { if (scope.value !== 'all') scope.value = id })
const showScope = computed(() => multi.value && (owner.value || guilds.value.length > 1))

let seq = 0
async function load() {
  const mySeq = ++seq
  stats.value = null
  error.value = false
  try {
    const query = scope.value ? `?guild=${encodeURIComponent(scope.value)}` : ''
    const rv = await apiFetch(`../api/stats${query}`)
    if (!rv.ok) throw new Error(String(rv.status))
    const data = await rv.json()
    if (mySeq === seq) stats.value = data
  } catch {
    if (mySeq === seq) error.value = true
  }
}

onMounted(load)
watch(scope, load)

// Source colors are CSS custom properties (see <style> below), so they follow
// theme changes without any JS theme detection.
const TYPE_COLORS: Record<string, string> = {
  url: 'var(--stats-url)',
  file: 'var(--stats-file)',
  radio: 'var(--stats-radio)',
  playlist: 'var(--stats-playlist)',
}

function typeColor(t: string): string {
  return TYPE_COLORS[t] ?? 'var(--c-text-faint)'
}

const totalHours = computed(() =>
  stats.value ? (stats.value.total_seconds / 3600).toFixed(1) : '0')

const maxHour = computed(() => Math.max(1, ...(stats.value?.hours ?? [1])))
const maxTrack = computed(() => Math.max(1, ...(stats.value?.top_tracks.map(t => t.count) ?? [1])))
const maxUser = computed(() => Math.max(1, ...(stats.value?.top_users.map(u => u.count) ?? [1])))
const typeTotal = computed(() =>
  Math.max(1, (stats.value?.by_type ?? []).reduce((a, b) => a + b.count, 0)))

const HOUR_LABELS = [0, 6, 12, 18]
const pad = (h: number) => String(h).padStart(2, '0')
</script>

<template>
  <section class="stats mx-auto w-full max-w-3xl px-4 py-8">
    <div v-if="showScope" class="mb-5 flex items-center justify-end gap-2 text-sm">
      <label for="stats-scope" :style="{ color: 'var(--c-text-muted)' }">{{ t('stats.scope') }}</label>
      <select
        id="stats-scope"
        v-model="scope"
        class="max-w-[14rem] cursor-pointer rounded-full border px-3 py-1.5 text-sm"
        :style="{ background: 'var(--c-bg)', borderColor: 'var(--c-border)', color: 'var(--c-text)' }"
      >
        <option v-if="owner" value="all">{{ t('stats.allServers') }}</option>
        <option v-for="g in guilds" :key="g.id" :value="g.id">{{ g.name }}</option>
      </select>
    </div>
    <p v-if="error" class="text-center text-sm" :style="{ color: 'var(--c-text-muted)' }">
      {{ t('stats.unavailable') }}
    </p>
    <p v-else-if="!stats" class="text-center text-sm" :style="{ color: 'var(--c-text-faint)' }">
      {{ t('common.loading') }}
    </p>

    <template v-else-if="stats.total_plays === 0">
      <p class="mt-10 text-center text-sm" :style="{ color: 'var(--c-text-muted)' }">
        {{ t('stats.noPlays') }}
      </p>
    </template>

    <template v-else>
      <!-- stat tiles -->
      <div class="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div
          v-for="tile in ([
            { label: t('stats.totalPlays'), value: String(stats.total_plays), sub: undefined },
            { label: t('stats.hours'), value: totalHours, sub: undefined },
            { label: t('stats.unique'), value: String(stats.unique_tracks), sub: undefined },
            { label: t('stats.busiest'), value: stats.busiest_day ? String(stats.busiest_day.count) : '-',
              sub: stats.busiest_day?.date },
          ] as { label: string; value: string; sub?: string }[])"
          :key="tile.label"
          class="rounded-xl p-4"
          :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)' }"
        >
          <p class="text-2xl font-semibold tabular-nums">{{ tile.value }}</p>
          <p class="mt-0.5 text-xs" :style="{ color: 'var(--c-text-muted)' }">
            {{ tile.label }}<span v-if="tile.sub"> · {{ tile.sub }}</span>
          </p>
        </div>
      </div>

      <!-- source share -->
      <div class="mt-6 rounded-xl p-4" :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)' }">
        <h2 class="mb-3 text-sm font-semibold">{{ t('stats.sources') }}</h2>
        <div class="flex h-3 w-full gap-[2px] overflow-hidden rounded-full" aria-hidden="true">
          <div
            v-for="row in stats.by_type"
            :key="row.type"
            :style="{ width: `${(row.count / typeTotal) * 100}%`, background: typeColor(row.type) }"
            :title="`${typeLabel(row.type)}: ${row.count}`"
          />
        </div>
        <ul role="list" class="mt-3 flex flex-wrap gap-x-4 gap-y-1">
          <li v-for="row in stats.by_type" :key="row.type" class="flex items-center gap-1.5 text-xs">
            <span class="h-2.5 w-2.5 rounded-sm" :style="{ background: typeColor(row.type) }" aria-hidden="true" />
            <span>{{ typeLabel(row.type) }}<span class="sr-only">:</span></span>
            <span class="tabular-nums" :style="{ color: 'var(--c-text-muted)' }">{{ row.count }}</span>
          </li>
        </ul>
      </div>

      <!-- hour histogram -->
      <div class="mt-4 rounded-xl p-4" :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)' }">
        <h2 id="stats-hours-title" class="mb-3 text-sm font-semibold">{{ t('stats.whenListens') }}</h2>
        <div class="flex h-24 items-end gap-[2px]" aria-hidden="true">
          <div
            v-for="(count, h) in stats.hours"
            :key="h"
            class="min-w-0 flex-1 rounded-t"
            :style="{
              height: `${(count / maxHour) * 100}%`,
              background: 'var(--c-accent)',
              opacity: count ? 1 : 0.15,
              minHeight: '2px',
            }"
            :title="t('stats.hourTip', { h: pad(h), n: count })"
          />
        </div>
        <div class="mt-1 flex justify-between text-[10px] tabular-nums" :style="{ color: 'var(--c-text-faint)' }" aria-hidden="true">
          <span v-for="h in HOUR_LABELS" :key="h">{{ pad(h) }}:00</span>
          <span>23:00</span>
        </div>
        <!-- the bars above are hidden from screen readers; this table carries the same numbers -->
        <table class="sr-only" aria-labelledby="stats-hours-title">
          <thead>
            <tr>
              <th scope="col">{{ t('stats.hour') }}</th>
              <th scope="col">{{ t('stats.playsCol') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(count, h) in stats.hours" :key="h">
              <th scope="row">{{ pad(h) }}:00</th>
              <td>{{ count }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- top tracks / users -->
      <div class="mt-4 grid gap-4 sm:grid-cols-2">
        <div class="rounded-xl p-4" :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)' }">
          <h2 class="mb-3 text-sm font-semibold">
            {{ t('stats.mostPlayed') }}
            <span v-if="stats.top_tracks[0]" class="ml-1 rounded-full px-1.5 py-0.5 text-[10px]" :style="{ background: 'var(--c-accent-soft)', color: 'var(--c-accent)' }">{{ t('stats.crown') }}</span>
          </h2>
          <ol role="list" class="flex flex-col gap-2">
            <li v-for="t in stats.top_tracks.slice(0, 8)" :key="t.item_id" class="text-xs">
              <div class="mb-0.5 flex justify-between gap-2">
                <span class="truncate" :title="t.title">{{ t.title || t.item_id }}</span>
                <span class="tabular-nums" :style="{ color: 'var(--c-text-muted)' }">{{ t.count }}</span>
              </div>
              <div class="h-1.5 rounded-full" :style="{ background: 'var(--c-surface-2)' }">
                <div class="h-full rounded-full" :style="{ width: `${(t.count / maxTrack) * 100}%`, background: 'var(--c-accent)' }" />
              </div>
            </li>
          </ol>
        </div>

        <div class="flex flex-col gap-4">
          <div class="rounded-xl p-4" :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)' }">
            <h2 class="mb-3 text-sm font-semibold">{{ t('stats.topUsers') }}</h2>
            <ol role="list" class="flex flex-col gap-2">
              <li v-for="u in stats.top_users.slice(0, 5)" :key="u.user" class="text-xs">
                <div class="mb-0.5 flex justify-between gap-2">
                  <span class="truncate">{{ u.user }}</span>
                  <span class="tabular-nums" :style="{ color: 'var(--c-text-muted)' }">{{ u.count }}</span>
                </div>
                <div class="h-1.5 rounded-full" :style="{ background: 'var(--c-surface-2)' }">
                  <div class="h-full rounded-full" :style="{ width: `${(u.count / maxUser) * 100}%`, background: 'var(--c-accent)' }" />
                </div>
              </li>
            </ol>
          </div>

          <div v-if="stats.most_skipped.length" class="rounded-xl p-4" :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)' }">
            <h2 class="mb-2 text-sm font-semibold">{{ t('stats.mostSkipped') }}</h2>
            <ul role="list" class="flex flex-col gap-1">
              <li v-for="s in stats.most_skipped.slice(0, 3)" :key="s.item_id" class="flex justify-between gap-2 text-xs">
                <span class="truncate" :title="s.title">{{ s.title || s.item_id }}</span>
                <span class="tabular-nums" :style="{ color: 'var(--c-text-muted)' }">{{ s.count }}×</span>
              </li>
            </ul>
          </div>
        </div>
      </div>

      <p class="mt-4 text-center text-[11px]" :style="{ color: 'var(--c-text-faint)' }">
        {{ t('stats.total', { t: formatTime(stats.total_seconds) }) }}
      </p>
    </template>
  </section>
</template>

<style scoped>
/* Categorical palette for source identity - validated (dataviz six checks)
   for both surfaces; light mode relies on the visible labels for relief.
   The selectors mirror the theme blocks in style.css. */
.stats {
  --stats-url: #6d5ef2;
  --stats-file: #1baf7a;
  --stats-radio: #eda100;
  --stats-playlist: #e87ba4;
}
@media (prefers-color-scheme: dark) {
  .stats {
    --stats-url: #8577ff;
    --stats-file: #199e70;
    --stats-radio: #c98500;
    --stats-playlist: #d55181;
  }
}
:root[data-theme='light'] .stats {
  --stats-url: #6d5ef2;
  --stats-file: #1baf7a;
  --stats-radio: #eda100;
  --stats-playlist: #e87ba4;
}
:root[data-theme='dark'] .stats,
:root[data-theme-default='dark']:not([data-theme]) .stats {
  --stats-url: #8577ff;
  --stats-file: #199e70;
  --stats-radio: #c98500;
  --stats-playlist: #d55181;
}
</style>
