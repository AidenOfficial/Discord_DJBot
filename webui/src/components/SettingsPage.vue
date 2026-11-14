<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import {
  fetchChannels, joinChannel, leaveChannel, saveChannelSettings, type ChannelNode, type ChannelOverview,
  type FollowMode,
} from '../api'
import ChannelTreeNode from './ChannelTreeNode.vue'
import GuildAdminPanel from './GuildAdminPanel.vue'
import LogsPanel from './LogsPanel.vue'
import { useGuilds } from '../composables/useGuilds'
import { useMe } from '../composables/useMe'
import { selectedGuild } from '../guild'
import { t, tParts } from '../i18n'
import type { Key } from '../i18n/en'
import { announce } from '../composables/useAnnounce'
import { getItem, setItem } from '../storage'

const { me } = useMe()
const { canManage } = useGuilds()
type Tab = 'channel' | 'server' | 'logs'
const tab = ref<Tab>('channel')
const savedTab = getItem('settingsTab')
if (savedTab === 'logs' || savedTab === 'server') tab.value = savedTab
function setTab(next: Tab) {
  tab.value = next
  setItem('settingsTab', next)
}
// 服务器管理只给能管理当前服务器的人,日志只给能看日志的人
const tabs = computed<Tab[]>(() => [
  'channel',
  ...(canManage.value ? ['server' as const] : []),
  ...(me.value?.can_view_logs ? ['logs' as const] : []),
])
const activeTab = computed<Tab>(() => (tabs.value.includes(tab.value) ? tab.value : 'channel'))
const TAB_LABEL: Record<Tab, Key> = { channel: 'set.tabChannel', server: 'set.tabServer', logs: 'logs.tab' }

const data = ref<ChannelOverview | null>(null)
const error = ref('')
const busy = ref(false)
const toast = ref('')
const toastOk = ref(true)

let toastTimer: ReturnType<typeof setTimeout> | undefined
/** Failures stay until the next message or until dismissed; successes fade after 3 s. */
function say(msg: string, ok = true) {
  toast.value = msg
  toastOk.value = ok
  clearTimeout(toastTimer)
  if (ok) toastTimer = setTimeout(() => (toast.value = ''), 3000)
  announce(msg, { assertive: !ok })
}
function dismissToast() {
  clearTimeout(toastTimer)
  toast.value = ''
}

async function reload() {
  const guild = selectedGuild.value
  try {
    const fresh = await fetchChannels()
    if (guild !== selectedGuild.value) return  // 途中换了服务器
    data.value = fresh
    error.value = ''
  } catch {
    if (guild !== selectedGuild.value) return
    // Polling repeats every few seconds: announce only when the error first appears
    if (!error.value) announce(t('set.readFailed'), { assertive: true })
    error.value = t('set.readFailed')
  }
}

watch(selectedGuild, () => {
  data.value = null
  error.value = ''
  reload()
})

/** 不能改这个服务器的频道设置(只能移动 / 离开) */
const locked = computed(() => data.value?.can_edit_settings === false)

// 频道里的人随时在变,定时刷新;只在"频道"子标签打开时轮询
let timer: ReturnType<typeof setInterval> | undefined
watch(activeTab, (next) => {
  clearInterval(timer)
  timer = undefined
  if (next === 'channel') {
    reload()
    timer = setInterval(reload, 4000)
  }
}, { immediate: true })
onBeforeUnmount(() => clearInterval(timer))

function findPath(node: ChannelNode | null, id: string | null): string {
  if (!node || id === null) return ''
  if (node.id === id) return node.path.length ? node.path.join(' / ') : node.name
  for (const c of node.children) {
    const p = findPath(c, id)
    if (p) return p
  }
  return ''
}
const currentName = computed(() => findPath(data.value?.tree ?? null, data.value?.current_channel_id ?? null))
const defaultName = computed(() => {
  const s = data.value?.settings
  if (!s) return ''
  if (s.default_channel_id === null) return s.default_path.length ? t('set.notFound', { path: s.default_path.join(' / ') }) : ''
  return findPath(data.value?.tree ?? null, s.default_channel_id)
})

// Auto-saving controls stay enabled while a save is in flight (disabling the focused
// control drops keyboard focus to <body>), so saves can overlap: only the latest
// response is applied.
let applySeq = 0
let pending = 0
async function apply(promise: Promise<ChannelOverview>, msg: string) {
  const mySeq = ++applySeq
  pending++
  busy.value = true
  try {
    const fresh = await promise
    if (mySeq === applySeq) data.value = fresh
    say(msg)
  } catch {
    say(t('common.saveFailed'), false)
    if (mySeq === applySeq) reload() // put the controls back to what the server has
  } finally {
    busy.value = --pending > 0
  }
}

function setFollow(mode: FollowMode) {
  const body: Parameters<typeof saveChannelSettings>[0] = { follow: mode }
  // 切到"跟随某人"时,默认选第一个在线的人
  if (mode === 'user' && !data.value?.settings.follow_user && data.value?.online_users.length) {
    body.follow_user = data.value.online_users[0]
  }
  apply(saveChannelSettings(body), t('set.followSaved'))
}

// 跟随对象离线时也保留在下拉里,免得一刷新就被换掉
const followChoices = computed(() => {
  const list = [...(data.value?.online_users ?? [])]
  const cur = data.value?.settings.follow_user
  if (cur && !list.includes(cur)) list.unshift(cur)
  return list
})

function onIdleMinutes(e: Event) {
  const input = e.target as HTMLInputElement
  const minutes = Math.max(0, Math.min(1440, Math.round(Number(input.value) || 0)))
  input.value = String(minutes)
  apply(saveChannelSettings({ idle_pause_minutes: minutes }),
    minutes ? t('set.idleSaved', { n: minutes }) : t('set.idleOff'))
}

const MODES: { key: FollowMode; label: Key; hint: Key }[] = [
  { key: 'off', label: 'set.offLabel', hint: 'set.offHint' },
  { key: 'auto', label: 'set.autoLabel', hint: 'set.autoHint' },
  { key: 'user', label: 'set.userLabel', hint: 'set.userHint' },
]
const modeHint = computed(() => {
  const m = MODES.find((m) => m.key === data.value?.settings.follow)
  return m ? t(m.hint) : ''
})
</script>

<template>
  <section class="mx-auto w-full max-w-3xl px-4 py-8">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <h1 class="text-xl font-semibold">{{ t('set.title') }}</h1>
      <div v-if="tabs.length > 1" role="group" :aria-label="t('set.sections')" class="flex gap-1 rounded-full p-1" :style="{ background: 'var(--c-surface-2)' }">
        <button
          v-for="tb in tabs"
          :key="tb"
          type="button"
          :aria-pressed="tb === activeTab"
          class="cursor-pointer rounded-full border-0 px-3.5 py-1 text-xs font-medium"
          :style="tb === activeTab
            ? { background: 'var(--c-surface)', color: 'var(--c-text)', boxShadow: 'var(--shadow-1)' }
            : { background: 'transparent', color: 'var(--c-text-muted)' }"
          @click="setTab(tb)"
        >{{ t(TAB_LABEL[tb]) }}</button>
      </div>
    </div>

    <LogsPanel v-if="activeTab === 'logs'" class="mt-5" />
    <GuildAdminPanel v-else-if="activeTab === 'server'" />

    <template v-else>
    <p v-if="locked" class="mt-3 rounded-lg px-3 py-2 text-xs" :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text-muted)' }"><Icon icon="lock" class="mr-1.5" aria-hidden="true" />{{ t('set.manageOnly') }}</p>
    <p v-if="error" class="mt-3 rounded-lg px-3 py-2 text-sm" :style="{ background: 'var(--c-accent-soft)', color: 'var(--c-danger)' }"><Icon icon="triangle-exclamation" class="mr-1.5" aria-hidden="true" />{{ error }}</p>

    <template v-if="data">
      <!-- 跟随 -->
      <div class="mt-5 rounded-2xl p-5" :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)' }">
        <h2 class="text-sm font-semibold uppercase tracking-wider" :style="{ color: 'var(--c-text-muted)' }">{{ t('set.channel') }}</h2>
        <p class="mt-2 text-sm">
          <template v-for="(p, i) in tParts('set.nowIn', { cur: currentName || t('set.notInVoice'), def: defaultName || t('set.noDefault') })" :key="i"><b
            v-if="p.param">{{ p.text }}</b><template v-else>{{ p.text }}</template></template>
        </p>
        <div class="mt-2 flex flex-wrap gap-2">
          <button
            v-if="data.current_channel_id"
            class="cursor-pointer rounded-full border-0 px-3 py-1 text-xs"
            :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
            :disabled="busy"
            :title="t('set.leaveTitle')"
            @click="apply(leaveChannel(), t('set.left'))"
          ><Icon icon="right-from-bracket" class="mr-1" />{{ t('set.leave') }}</button>
          <button
            v-if="data.settings.default_path.length"
            class="cursor-pointer rounded-full border-0 px-3 py-1 text-xs"
            :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
            :disabled="busy || locked"
            :title="t('set.clearDefaultTitle')"
            @click="apply(saveChannelSettings({ default_channel_id: null }), t('set.defaultCleared'))"
          ><Icon icon="xmark" class="mr-1" />{{ t('set.clearDefault') }}</button>
        </div>

        <div
          role="group"
          :aria-label="t('set.followMode')"
          aria-describedby="follow-mode-hint"
          class="mt-4 grid grid-cols-3 gap-1 rounded-2xl p-1 sm:inline-grid sm:rounded-full"
          :style="{ background: 'var(--c-surface-2)' }"
        >
          <button
            v-for="m in MODES"
            :key="m.key"
            type="button"
            :aria-pressed="data.settings.follow === m.key"
            class="cursor-pointer rounded-xl border-0 px-2 py-1.5 text-xs font-medium sm:rounded-full sm:px-3.5"
            :style="data.settings.follow === m.key
              ? { background: 'var(--c-accent)', color: 'var(--c-on-accent)' }
              : { background: 'transparent', color: 'var(--c-text-muted)' }"
            :disabled="locked"
            @click="data.settings.follow !== m.key && setFollow(m.key)"
          ><Icon v-if="data.settings.follow === m.key" icon="check" class="mr-1" aria-hidden="true" />{{ t(m.label) }}</button>
        </div>
        <p id="follow-mode-hint" class="mt-2 text-xs" :style="{ color: 'var(--c-text-muted)' }">{{ modeHint }}</p>

        <div v-if="data.settings.follow === 'user'" class="mt-3 flex items-center gap-2 text-sm">
          <label for="follow-user" :style="{ color: 'var(--c-text-muted)' }">{{ t('set.follow') }}</label>
          <select
            id="follow-user"
            :value="data.settings.follow_user"
            class="rounded-full border px-3 py-1.5 text-sm"
            :style="{ background: 'var(--c-bg)', borderColor: 'var(--c-border)', color: 'var(--c-text)' }"
            :disabled="locked"
            @change="apply(saveChannelSettings({ follow_user: ($event.target as HTMLSelectElement).value }), t('common.saved'))"
          >
            <option v-if="!followChoices.length" value="">{{ t('set.nobody') }}</option>
            <option v-for="n in followChoices" :key="n" :value="n">
              {{ n }}{{ data.online_users.includes(n) ? '' : t('set.offline') }}
            </option>
          </select>
        </div>

        <label v-if="data.settings.follow !== 'off'" class="mt-3 flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            :checked="data.settings.return_home"
            :disabled="locked"
            class="h-4 w-4"
            :style="{ accentColor: 'var(--c-accent)' }"
            @change="apply(saveChannelSettings({ return_home: ($event.target as HTMLInputElement).checked }), t('common.saved'))"
          />
          {{ t('set.returnHome') }}
        </label>

        <p v-if="toast" class="mt-3 flex items-start gap-1.5 text-xs" :style="{ color: toastOk ? 'var(--c-success)' : 'var(--c-danger)' }">
          <Icon :icon="toastOk ? 'check' : 'triangle-exclamation'" class="mt-0.5" aria-hidden="true" />
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
      </div>

      <!-- 没人时自动暂停 -->
      <div class="mt-5 rounded-2xl p-5" :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)' }">
        <h2 class="text-sm font-semibold uppercase tracking-wider" :style="{ color: 'var(--c-text-muted)' }">{{ t('set.idleTitle') }}</h2>
        <div class="mt-3 flex flex-wrap items-center gap-2 text-sm">
          <label for="idle-minutes">{{ t('set.idleLabel') }}</label>
          <input
            id="idle-minutes"
            type="number"
            min="0"
            max="1440"
            :value="data.settings.idle_pause_minutes"
            :disabled="locked"
            aria-describedby="idle-hint"
            class="w-20 rounded-lg border px-2 py-1 text-sm tabular-nums"
            :style="{ background: 'var(--c-bg)', borderColor: 'var(--c-border)', color: 'var(--c-text)' }"
            @change="onIdleMinutes"
          />
          <span>{{ t('set.minutes') }}</span>
        </div>
        <p id="idle-hint" class="mt-1 text-xs" :style="{ color: 'var(--c-text-muted)' }">
          {{ t('set.idleHint') }}
        </p>
        <label class="mt-3 flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            :checked="data.settings.idle_resume"
            :disabled="locked || data.settings.idle_pause_minutes === 0"
            class="h-4 w-4"
            :style="{ accentColor: 'var(--c-accent)' }"
            @change="apply(saveChannelSettings({ idle_resume: ($event.target as HTMLInputElement).checked }), t('common.saved'))"
          />
          {{ t('set.idleResume') }}
        </label>
      </div>

      <!-- 频道树 -->
      <div class="mt-5 rounded-2xl p-3 sm:p-4" :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)' }">
        <div class="flex items-center justify-between px-2 pb-2">
          <h2 class="text-sm font-semibold uppercase tracking-wider" :style="{ color: 'var(--c-text-muted)' }">{{ t('set.channels') }}</h2>
          <span class="text-[11px]" :style="{ color: 'var(--c-text-faint)' }">{{ t('set.online', { n: data.online_users.length }) }}</span>
        </div>
        <ul v-if="data.tree" role="list">
          <ChannelTreeNode
            :node="data.tree"
            :current-id="data.current_channel_id"
            :default-id="data.settings.default_channel_id"
            :busy="busy"
            @move="(id: string) => apply(joinChannel(id), t(data?.settings.follow === 'off' ? 'set.moving' : 'set.movingFollow'))"
            @set-default="(id: string) => locked ? say(t('set.manageOnly'), false) : apply(saveChannelSettings({ default_channel_id: id }), t('set.defaultSaved'))"
          />
        </ul>
        <p v-else class="px-2 py-4 text-sm" :style="{ color: 'var(--c-text-muted)' }">{{ t('set.notConnected') }}</p>
      </div>
    </template>
    </template>
  </section>
</template>
