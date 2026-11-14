<script setup lang="ts">
import { computed } from 'vue'
import type { ChannelNode } from '../api'
import { t } from '../i18n'

// 递归渲染服务器 → 分类 → 语音频道。只有 bot 能进的语音频道才有"移到这里 / 设为默认"按钮。
const props = defineProps<{
  node: ChannelNode
  currentId: string | null
  defaultId: string | null
  busy: boolean
  depth?: number
}>()
const emit = defineEmits<{ move: [id: string]; setDefault: [id: string] }>()

const depth = computed(() => props.depth ?? 0)
const isHere = computed(() => props.node.id === props.currentId)
const isDefault = computed(() => props.node.id === props.defaultId)
const isVoice = computed(() => props.node.kind === 'voice' || props.node.kind === 'stage')
const canUse = computed(() => props.node.kind === 'voice' && props.node.joinable)
// 本频道里的真人数(不含 bot)
const people = computed(() => props.node.users.filter((u) => !u.is_me && !u.is_bot).length)
const icon = computed(() => ({
  guild: 'server', category: 'folder', voice: 'volume-high', stage: 'microphone',
}[props.node.kind] ?? 'hashtag'))
// 分类名在 Discord 里是小号大写字母
const isCategory = computed(() => props.node.kind === 'category')
</script>

<template>
  <li>
    <div
      class="group flex flex-wrap items-center gap-x-2 gap-y-1 rounded-xl px-2.5"
      :class="isCategory ? 'pt-3 pb-1' : 'py-2'"
      :style="isHere ? { background: 'var(--c-accent-soft)' } : {}"
      :aria-current="isHere ? 'true' : undefined"
    >
      <span class="flex min-w-0 items-center gap-1.5"
            :class="isCategory ? 'text-[11px] font-semibold uppercase tracking-wider' : 'text-sm font-medium'"
            :style="{ color: isHere ? 'var(--c-accent)' : (isCategory ? 'var(--c-text-muted)' : (isVoice && !node.joinable ? 'var(--c-text-faint)' : 'var(--c-text)')) }">
        <Icon :icon="icon" class="w-3.5 shrink-0 text-xs opacity-60" aria-hidden="true" />
        <span class="truncate">{{ node.name }}</span>
      </span>
      <span v-if="isDefault" class="rounded-full px-1.5 py-0.5 text-[10px] font-semibold"
            :style="{ background: 'var(--c-surface-2)', color: 'var(--c-accent)' }" :title="t('ch.defaultTitle')"><Icon icon="star" class="mr-0.5" />{{ t('ch.default') }}</span>
      <span v-if="node.afk" class="text-[10px]" :style="{ color: 'var(--c-text-faint)' }" :title="t('ch.afkTitle')"><Icon icon="moon" class="mr-0.5" />{{ t('ch.afk') }}</span>
      <span v-if="isVoice && !node.joinable" class="text-[10px]" :style="{ color: 'var(--c-text-faint)' }"
            :title="t(node.kind === 'stage' ? 'ch.stageTitle' : 'ch.noAccessTitle')"><Icon icon="lock" class="mr-0.5" />{{ t(node.kind === 'stage' ? 'ch.stage' : 'ch.noAccess') }}</span>
      <span v-if="people" class="text-[11px] tabular-nums" :style="{ color: 'var(--c-text-faint)' }">{{ people }} <Icon icon="user" class="text-[10px]" /></span>

      <!-- faded at rest only where hover exists (80% keeps the text readable), full while focused -->
      <span v-if="canUse" class="ml-auto flex shrink-0 gap-1 transition-opacity [@media(hover:hover)]:opacity-80 group-hover:opacity-100 group-focus-within:opacity-100">
        <!-- 名字带上频道名(以可见文字开头),读屏在一串"移到这里"里能分清是哪个频道 -->
        <button
          v-if="!isHere"
          type="button"
          class="cursor-pointer rounded-md border-0 px-2 py-0.5 text-[11px]"
          :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
          :disabled="busy"
          :title="t('ch.moveTitle')"
          :aria-label="t('common.itemAction', { action: t('ch.move'), title: node.name })"
          @click="emit('move', node.id)"
        >{{ t('ch.move') }}</button>
        <button
          v-if="!isDefault"
          type="button"
          class="cursor-pointer rounded-md border-0 px-2 py-0.5 text-[11px]"
          :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
          :disabled="busy"
          :title="t('ch.setDefaultTitle')"
          :aria-label="t('common.itemAction', { action: t('ch.setDefault'), title: node.name })"
          @click="emit('setDefault', node.id)"
        ><Icon :icon="['far', 'star']" class="mr-0.5" aria-hidden="true" />{{ t('ch.setDefault') }}</button>
      </span>

      <!-- 频道里的人 -->
      <div v-if="node.users.length" class="flex w-full flex-wrap gap-1.5 pl-5">
        <span
          v-for="u in node.users"
          :key="u.session"
          class="flex items-center gap-1 rounded-full py-0.5 pr-2 pl-0.5 text-xs"
          :style="{
            background: u.is_me ? 'var(--c-accent)' : 'var(--c-surface-2)',
            color: u.is_me ? 'var(--c-on-accent)' : (u.is_bot ? 'var(--c-text-muted)' : 'var(--c-text)'),
          }"
        >
          <span class="flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-semibold"
                :style="{ background: u.is_me ? 'rgba(255,255,255,0.25)' : 'var(--c-border)' }">
            <Icon v-if="u.is_me" icon="music" />
            <Icon v-else-if="u.is_bot_account" icon="robot" />
            <template v-else>{{ u.name.charAt(0).toUpperCase() }}</template>
          </span>
          {{ u.name }}
          <Icon v-if="u.deafened" icon="ear-deaf" class="text-[10px] opacity-70" :title="t('ch.deafened')" />
          <span v-else-if="u.muted" class="text-[10px] opacity-70" :title="t('ch.mutedTitle')">{{ t('ch.muted') }}</span>
        </span>
      </div>
    </div>

    <ul v-if="node.children.length" role="list"
        :class="depth === 0 ? '' : 'ml-4 border-l pl-2'"
        :style="{ borderColor: 'var(--c-border)' }">
      <ChannelTreeNode
        v-for="child in node.children"
        :key="child.id"
        :node="child"
        :current-id="currentId"
        :default-id="defaultId"
        :busy="busy"
        :depth="depth + 1"
        @move="(id: string) => emit('move', id)"
        @set-default="(id: string) => emit('setDefault', id)"
      />
    </ul>
  </li>
</template>
