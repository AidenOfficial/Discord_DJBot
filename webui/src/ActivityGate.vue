<script setup lang="ts">
// 根组件。普通网页直接是 App;Discord Activity 里先登录(拿 Bearer 令牌)再显示 App,
// 登录不了 / 令牌续不上(离开了语音频道)时显示原因和重试。
import { computed, onBeforeUnmount, onMounted } from 'vue'
import App from './App.vue'
import { activity, embedded, renew, revokeOnExit } from './activity'
import { t } from './i18n'
import type { Key } from './i18n/en'

const KNOWN = ['not_in_voice_channel', 'not_a_member', 'guild_not_served', 'guild_required',
  'activity_disabled', 'authorize_cancelled', 'discord_auth_failed']

const message = computed(() => KNOWN.includes(activity.error)
  ? t(`act.err.${activity.error}` as Key)
  : t('act.err.other', { code: activity.error || '?' }))

function retry() {
  void renew()
}

onMounted(() => {
  if (!embedded) return
  void renew()
  window.addEventListener('pagehide', revokeOnExit)
})
onBeforeUnmount(() => window.removeEventListener('pagehide', revokeOnExit))
</script>

<template>
  <App v-if="!embedded || activity.phase === 'ready'" />
  <div v-else class="flex min-h-full items-center justify-center p-6">
    <div
      v-if="activity.phase === 'error'"
      class="w-full max-w-sm rounded-2xl p-5 text-center"
      :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)' }"
      role="alert"
    >
      <p class="font-medium">{{ t('act.failedTitle') }}</p>
      <p class="mt-2 text-sm leading-relaxed" :style="{ color: 'var(--c-text-muted)' }">{{ message }}</p>
      <button
        class="mt-4 cursor-pointer rounded-full border-0 px-4 py-2 text-sm font-semibold"
        :style="{ background: 'var(--c-accent)', color: 'var(--c-on-accent)' }"
        @click="retry"
      >{{ t('act.retry') }}</button>
    </div>
    <p v-else class="text-sm" :style="{ color: 'var(--c-text-muted)' }" aria-live="polite">
      <Icon icon="music" class="mr-2" aria-hidden="true" />{{ t('act.connecting') }}
    </p>
  </div>
</template>
