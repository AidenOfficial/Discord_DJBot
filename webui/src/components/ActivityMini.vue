<script setup lang="ts">
// Activity 被缩成画中画小窗(高度很小)时只显示这一条:封面、歌名、播放 / 暂停、下一首。
import { computed } from 'vue'
import { thumbnailUrl } from '../api'
import { useStatus } from '../composables/useStatus'
import { t } from '../i18n'
import AuthImg from './AuthImg.vue'

const { status, control } = useStatus()
const current = computed(() => status.value?.current ?? null)

function togglePlay() {
  if (!status.value) return
  control({ action: status.value.play ? 'pause' : 'resume' })
}
</script>

<template>
  <div class="flex h-full items-center gap-3 px-3">
    <div class="h-12 w-12 shrink-0 overflow-hidden rounded-lg" :style="{ background: 'var(--c-surface-2)' }">
      <AuthImg
        v-if="current?.has_thumbnail"
        :src="thumbnailUrl(current.id, { small: true })"
        alt=""
        class="h-full w-full object-cover"
      />
    </div>
    <div class="min-w-0 flex-1">
      <p class="truncate text-sm font-medium">{{ current?.title || t('np.nothing') }}</p>
      <p v-if="current?.artist" class="truncate text-xs" :style="{ color: 'var(--c-text-muted)' }">{{ current.artist }}</p>
    </div>
    <button
      class="flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-full border-0"
      :style="{ background: 'var(--c-accent)', color: 'var(--c-on-accent)' }"
      :title="status?.play ? t('ctl.pause') : t('ctl.play')"
      :aria-label="status?.play ? t('ctl.pause') : t('ctl.play')"
      @click="togglePlay"
    >
      <Icon :icon="status?.play ? 'pause' : 'play'" />
    </button>
    <button
      class="flex h-10 w-10 shrink-0 cursor-pointer items-center justify-center rounded-full border-0"
      :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
      :title="t('ctl.skip')"
      :aria-label="t('ctl.skip')"
      @click="control({ action: 'skip' })"
    >
      <Icon icon="forward-step" />
    </button>
  </div>
</template>
