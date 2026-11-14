<script lang="ts">
import type { InjectionKey } from 'vue'

/** App.vue provides this: rebuilds the failed page component so the chunk is requested again. */
export const RETRY_VIEW: InjectionKey<() => void> = Symbol('retryView')
</script>

<script setup lang="ts">
import { inject, onMounted } from 'vue'
import { announce } from '../composables/useAnnounce'
import { t } from '../i18n'

// Shown when a page's code chunk fails to load: offline, or the bot was redeployed
// and the old chunk names are gone (then only a reload helps).
// defineAsyncComponent passes the load error as a prop; declared so it does not fall
// through as an `error="..."` attribute (with the chunk URL) on the root element
defineProps<{ error?: unknown }>()

const reload = () => location.reload()
const retry = inject(RETRY_VIEW, reload)

onMounted(() => announce(t('nav.loadFailed'), { assertive: true }))
</script>

<template>
  <section class="mx-auto w-full max-w-3xl px-4 py-8">
    <div class="rounded-2xl p-5 text-center" :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-1)' }">
      <p class="text-sm">
        <Icon icon="triangle-exclamation" class="mr-1.5" aria-hidden="true" :style="{ color: 'var(--c-danger)' }" />{{ t('nav.loadFailed') }}
      </p>
      <div class="mt-4 flex flex-wrap justify-center gap-2">
        <button
          type="button"
          class="cursor-pointer rounded-full border-0 px-4 py-2 text-xs font-semibold"
          :style="{ background: 'var(--c-accent)', color: 'var(--c-on-accent)' }"
          @click="retry"
        >{{ t('common.retry') }}</button>
        <button
          type="button"
          class="cursor-pointer rounded-full border-0 px-4 py-2 text-xs"
          :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
          @click="reload"
        >{{ t('nav.reload') }}</button>
      </div>
    </div>
  </section>
</template>
