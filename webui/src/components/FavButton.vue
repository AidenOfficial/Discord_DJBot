<script setup lang="ts">
import { computed, ref } from 'vue'
import type { PlaylistSource } from '../api'
import { useMe } from '../composables/useMe'
import { useFavorites } from '../composables/useFavorites'
import { announce } from '../composables/useAnnounce'
import { t } from '../i18n'

// 一键收藏到"我喜欢的音乐"(和聊天里的 !fav 同一张歌单)
const props = withDefaults(
  defineProps<{ itemId: string; source: PlaylistSource; label?: string; /** 列表行里用:按钮名字带上歌名 */ itemTitle?: string }>(),
  { label: '', itemTitle: '' },
)

const { me } = useMe()
const { favoriteIds, toggleFavorite } = useFavorites()

const on = computed(() => !!props.itemId && favoriteIds.value.has(props.itemId))
const failed = ref(false)

// 名字固定不变,开/关由 aria-pressed 表达(名字跟着状态变会被读两遍);
// 有可见文字时就用可见文字当名字
const ariaLabel = computed(() => {
  if (props.label) return undefined
  return props.itemTitle ? t('common.itemAction', { action: t('fav.name'), title: props.itemTitle }) : t('fav.name')
})

async function toggle() {
  if (!props.itemId) return
  // 保存中不禁用按钮(禁用会把焦点弄丢);重复点击由 toggleFavorite 自己忽略
  failed.value = !(await toggleFavorite(props.itemId, props.source))
  if (failed.value) {
    announce(t('fav.failed'), { assertive: true })
    setTimeout(() => (failed.value = false), 2500)
  }
}
</script>

<template>
  <button
    v-if="me?.can_have_playlists && props.itemId"
    type="button"
    class="inline-flex cursor-pointer items-center gap-1 rounded-md border-0 px-2 py-1 text-xs"
    :style="{ background: 'var(--c-surface-2)', color: on ? 'var(--c-danger)' : 'var(--c-text)' }"
    :title="failed ? t('fav.failed') : t(on ? 'fav.remove' : 'fav.add')"
    :aria-label="ariaLabel"
    :aria-pressed="on"
    @click.stop="toggle"
  >
    <Icon :icon="on ? 'heart' : ['far', 'heart']" />
    <span v-if="props.label">{{ props.label }}</span>
  </button>
</template>
