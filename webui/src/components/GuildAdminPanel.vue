<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  addGuildBan, fetchGuildBans, fetchGuildSettings, removeGuildBan, saveGuildSettings,
  type BanKind, type GuildBans, type GuildSettings,
} from '../api'
import { selectedGuild } from '../guild'
import { t, timeAgo } from '../i18n'
import type { Key } from '../i18n/en'
import { announce } from '../composables/useAnnounce'

// 设置 → 服务器:只有能管理这个服务器的人看得到(父组件按 can_manage 决定显示)。
const settings = ref<GuildSettings | null>(null)
const bans = ref<GuildBans | null>(null)
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

const announceDraft = ref('')
const announceError = ref('')
const volumeDraft = ref(100)
const banDraft = ref<Record<BanKind, { value: string; note: string }>>({
  user_ban: { value: '', note: '' },
  url_ban: { value: '', note: '' },
})

function applySettings(s: GuildSettings) {
  settings.value = s
  announceDraft.value = s.announce_channel ?? ''
  // keep a slider value that is still waiting to be saved
  if (!volumeTimer && !volumeSending) volumeDraft.value = s.max_volume
}

async function reload() {
  const guild = selectedGuild.value
  try {
    const [s, b] = await Promise.all([fetchGuildSettings(), fetchGuildBans()])
    if (guild !== selectedGuild.value) return
    applySettings(s)
    bans.value = b
    error.value = ''
  } catch {
    if (guild !== selectedGuild.value) return
    error.value = t('adm.loadFailed')
    announce(error.value, { assertive: true })
  }
}

onMounted(reload)
watch(selectedGuild, () => {
  // a queued max-volume save belongs to the previous server
  clearTimeout(volumeTimer)
  volumeTimer = undefined
  volumeSeq++
  volumeSending = 0
  settings.value = null
  bans.value = null
  reload()
})

function onAnnounceInvalid() {
  announceError.value = t('adm.invalidChannel')
  announce(announceError.value, { assertive: true })
}

async function saveAnnounce() {
  const value = announceDraft.value.trim()
  if (value && !/^\d{1,20}$/.test(value)) {
    // The pattern attribute normally stops this first; keep the check for pasted spaces etc.
    onAnnounceInvalid()
    return
  }
  announceError.value = ''
  busy.value = true
  try {
    applySettings(await saveGuildSettings({ announce_channel: value || null }))
    say(t('adm.announceSaved'))
  } catch {
    say(t('common.saveFailed'), false)
  } finally {
    busy.value = false
  }
}

// Arrow keys fire change on every step, so wait for the user to settle before saving.
// The slider stays enabled throughout: disabling it would drop keyboard focus.
let volumeTimer: ReturnType<typeof setTimeout> | undefined
let volumeSeq = 0
let volumeSending = 0 // seq of the request in flight, 0 when none
function queueVolume() {
  clearTimeout(volumeTimer)
  volumeTimer = setTimeout(saveVolume, 400)
}
onBeforeUnmount(() => clearTimeout(volumeTimer))

async function saveVolume() {
  volumeTimer = undefined
  const n = Math.max(0, Math.min(100, Math.round(Number(volumeDraft.value) || 0)))
  const mySeq = ++volumeSeq
  volumeSending = mySeq
  try {
    const s = await saveGuildSettings({ max_volume: n })
    // a newer value is queued or on its way: let that response settle the slider
    if (mySeq !== volumeSeq || volumeTimer) return
    settings.value = s
    volumeDraft.value = s.max_volume
    say(t('adm.maxVolumeSaved', { n }))
  } catch {
    if (mySeq !== volumeSeq || volumeTimer) return
    say(t('common.saveFailed'), false)
    if (settings.value) volumeDraft.value = settings.value.max_volume
  } finally {
    if (volumeSending === mySeq) volumeSending = 0
  }
}

async function ban(kind: BanKind) {
  const draft = banDraft.value[kind]
  const value = draft.value.trim()
  if (!value) return
  busy.value = true
  try {
    bans.value = await addGuildBan(kind, value, draft.note.trim())
    banDraft.value[kind] = { value: '', note: '' }
    say(t('common.saved'))
  } catch {
    say(t('adm.invalid'), false)
  } finally {
    busy.value = false
  }
}

async function unban(kind: BanKind, value: string) {
  busy.value = true
  try {
    bans.value = await removeGuildBan(kind, value)
  } catch {
    say(t('common.saveFailed'), false)
  } finally {
    busy.value = false
  }
}

const BAN_SECTIONS: { kind: BanKind; title: Key; empty: Key; placeholder: Key }[] = [
  { kind: 'user_ban', title: 'adm.userBans', empty: 'adm.noUsers', placeholder: 'adm.userPlaceholder' },
  { kind: 'url_ban', title: 'adm.urlBans', empty: 'adm.noUrls', placeholder: 'adm.urlPlaceholder' },
]

/** 备注在后端已经转义过(和聊天命令存的一样),显示前还原 */
function unescape(s: string) {
  const el = document.createElement('textarea')
  el.innerHTML = s
  return el.value
}
</script>

<template>
  <div>
    <p v-if="error" class="mt-3 rounded-lg px-3 py-2 text-sm" :style="{ background: 'var(--c-accent-soft)', color: 'var(--c-danger)' }">{{ error }}</p>
    <p v-else-if="!settings" class="mt-5 text-sm" :style="{ color: 'var(--c-text-faint)' }">{{ t('common.loading') }}</p>

    <template v-if="settings && bans">
      <div class="mt-5 rounded-2xl p-5" :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)' }">
        <!-- 公告频道 -->
        <label for="announce-channel" class="text-sm font-semibold uppercase tracking-wider" :style="{ color: 'var(--c-text-muted)' }">{{ t('adm.announce') }}</label>
        <p id="announce-hint" class="mt-1 text-xs" :style="{ color: 'var(--c-text-muted)' }">{{ t('adm.announceHint') }}</p>
        <form class="mt-3 flex flex-wrap gap-2" @submit.prevent="saveAnnounce">
          <select
            v-if="settings.text_channels.length"
            id="announce-channel"
            v-model="announceDraft"
            aria-describedby="announce-hint"
            class="min-w-0 flex-1 rounded-lg border px-3 py-1.5 text-sm"
            :style="{ background: 'var(--c-bg)', borderColor: 'var(--c-border)', color: 'var(--c-text)' }"
          >
            <option value="">{{ t('adm.announceAuto') }}</option>
            <option v-for="c in settings.text_channels" :key="c.id" :value="c.id"># {{ c.name }}</option>
          </select>
          <input
            v-else
            id="announce-channel"
            v-model="announceDraft"
            inputmode="numeric"
            pattern="\s*\d{1,20}\s*"
            autocomplete="off"
            autocorrect="off"
            autocapitalize="none"
            spellcheck="false"
            :placeholder="`${t('adm.announcePlaceholder')} · ${t('adm.announceAuto')}`"
            :aria-invalid="announceError ? 'true' : undefined"
            :aria-describedby="announceError ? 'announce-error announce-hint' : 'announce-hint'"
            class="min-w-0 flex-1 rounded-lg border px-3 py-1.5 font-mono text-sm"
            :style="{ background: 'var(--c-bg)', borderColor: announceError ? 'var(--c-danger)' : 'var(--c-border)', color: 'var(--c-text)' }"
            @invalid="onAnnounceInvalid"
            @input="announceError = ''"
          />
          <button
            type="submit"
            class="cursor-pointer rounded-lg border-0 px-3 py-1.5 text-xs font-semibold"
            :style="{ background: 'var(--c-accent)', color: 'var(--c-on-accent)' }"
            :disabled="busy"
          >{{ t('common.save') }}</button>
        </form>
        <p v-if="announceError" id="announce-error" class="mt-1.5 text-xs" :style="{ color: 'var(--c-danger)' }">
          <Icon icon="triangle-exclamation" class="mr-1" aria-hidden="true" />{{ announceError }}
        </p>

        <!-- 最大音量 -->
        <label for="max-volume" class="mt-6 block text-sm font-semibold uppercase tracking-wider" :style="{ color: 'var(--c-text-muted)' }">{{ t('adm.maxVolume') }}</label>
        <p id="max-volume-hint" class="mt-1 text-xs" :style="{ color: 'var(--c-text-muted)' }">{{ t('adm.maxVolumeHint', { n: settings.default_max_volume }) }}</p>
        <div class="mt-3 flex items-center gap-3">
          <input
            id="max-volume"
            v-model.number="volumeDraft"
            type="range"
            min="0"
            max="100"
            step="1"
            class="min-w-0 flex-1"
            :style="{ accentColor: 'var(--c-accent)' }"
            :aria-valuetext="`${volumeDraft}%`"
            aria-describedby="max-volume-hint"
            @change="queueVolume"
          />
          <span class="w-12 text-right text-sm tabular-nums">{{ volumeDraft }}%</span>
        </div>

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

      <!-- 本服务器的封禁 -->
      <div class="mt-5 rounded-2xl p-5" :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)' }">
        <h2 class="text-sm font-semibold uppercase tracking-wider" :style="{ color: 'var(--c-text-muted)' }">{{ t('adm.bans') }}</h2>
        <p class="mt-1 text-xs" :style="{ color: 'var(--c-text-muted)' }">{{ t('adm.bansHint') }}</p>

        <div v-for="sec in BAN_SECTIONS" :key="sec.kind" class="mt-4">
          <h3 class="text-sm font-medium">{{ t(sec.title) }}</h3>
          <ul v-if="bans[sec.kind].length" role="list" class="mt-2 divide-y" :style="{ borderColor: 'var(--c-border)' }">
            <li v-for="r in bans[sec.kind]" :key="r.value" class="flex items-center gap-3 py-2 text-sm" :style="{ borderColor: 'var(--c-border)' }">
              <div class="min-w-0 flex-1">
                <p class="truncate font-mono text-xs" :title="r.value">{{ r.value }}</p>
                <p class="truncate text-[11px]" :style="{ color: 'var(--c-text-faint)' }">
                  <template v-if="r.note">{{ unescape(r.note) }} · </template>{{ timeAgo(r.created_at) }}
                </p>
              </div>
              <button
                class="shrink-0 cursor-pointer rounded-full border-0 px-3 py-1 text-xs"
                :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
                :disabled="busy"
                @click="unban(sec.kind, r.value)"
              >{{ t('adm.unban') }}</button>
            </li>
          </ul>
          <p v-else class="mt-1 text-xs" :style="{ color: 'var(--c-text-faint)' }">{{ t(sec.empty) }}</p>
          <form class="mt-2 flex flex-wrap gap-2" @submit.prevent="ban(sec.kind)">
            <input
              v-model="banDraft[sec.kind].value"
              :type="sec.kind === 'user_ban' ? 'text' : 'url'"
              required
              :placeholder="t(sec.placeholder)"
              :aria-label="t(sec.placeholder)"
              :inputmode="sec.kind === 'user_ban' ? 'numeric' : 'url'"
              autocomplete="off"
              autocorrect="off"
              autocapitalize="none"
              spellcheck="false"
              class="min-w-0 flex-[2] rounded-lg border px-3 py-1.5 text-sm"
              :style="{ background: 'var(--c-bg)', borderColor: 'var(--c-border)', color: 'var(--c-text)' }"
            />
            <input
              v-model="banDraft[sec.kind].note"
              maxlength="100"
              :placeholder="t('adm.notePlaceholder')"
              :aria-label="t('adm.notePlaceholder')"
              class="min-w-0 flex-1 rounded-lg border px-3 py-1.5 text-sm"
              :style="{ background: 'var(--c-bg)', borderColor: 'var(--c-border)', color: 'var(--c-text)' }"
            />
            <button
              type="submit"
              class="cursor-pointer rounded-lg border-0 px-3 py-1.5 text-xs font-semibold"
              :style="{ background: 'var(--c-accent)', color: 'var(--c-on-accent)' }"
              :disabled="busy"
            >{{ t('adm.ban') }}</button>
          </form>
        </div>
      </div>
    </template>
  </div>
</template>
