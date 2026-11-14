<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, useId } from 'vue'
import { useGuilds } from '../composables/useGuilds'
import { t } from '../i18n'

// 顶栏的服务器切换:只能操作一个服务器(或旧的单服务器模式)时只显示名字,不弹菜单。
// 弹出的是一组普通按钮(Tab 逐个走),不是 listbox:没有方向键那一套,就不声明那个角色。
const { guilds, currentGuild, selectGuild } = useGuilds()

const open = ref(false)
const root = ref<HTMLElement | null>(null)
const trigger = ref<HTMLButtonElement | null>(null)
const switchable = computed(() => guilds.value.length > 1)
const uid = useId()
const triggerId = `${uid}-trigger`
const panelId = `${uid}-panel`

function initial(name: string) {
  return (name || '?').trim().charAt(0).toUpperCase()
}

function close(returnFocus = false) {
  if (!open.value) return
  // 先把焦点还给按钮再移除列表,否则焦点会掉到 <body>
  if (returnFocus) trigger.value?.focus()
  open.value = false
}

function toggle() {
  if (!switchable.value) return
  if (open.value) close()
  else open.value = true
}

function pick(id: string) {
  selectGuild(id)
  close(true)
}

// 捕获阶段监听:别的组件的 @click.stop 拦不住它
function onDocClick(e: MouseEvent) {
  if (open.value && root.value && !root.value.contains(e.target as Node)) close()
}
function onKey(e: KeyboardEvent) {
  if (e.key !== 'Escape' || !open.value || e.defaultPrevented) return
  close(!!root.value?.contains(document.activeElement))
}
// Tab 出列表就关掉;relatedTarget 为空(点了不可聚焦的地方)时不关
function onFocusOut(e: FocusEvent) {
  const next = e.relatedTarget
  if (open.value && next instanceof Node && root.value && !root.value.contains(next)) close()
}
onMounted(() => {
  document.addEventListener('click', onDocClick, true)
  document.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick, true)
  document.removeEventListener('keydown', onKey)
})
</script>

<template>
  <div v-if="currentGuild" ref="root" class="relative min-w-0" @focusout="onFocusOut">
    <button
      :id="triggerId"
      ref="trigger"
      type="button"
      class="flex h-9 max-w-[12rem] min-w-0 items-center gap-2 rounded-full border-0 py-1 pr-3 pl-1 text-xs font-medium"
      :class="switchable ? 'cursor-pointer' : 'cursor-default'"
      :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
      :title="switchable ? t('guild.switch') : currentGuild.name"
      :aria-label="switchable ? `${t('guild.switch')}: ${currentGuild.name}` : `${t('guild.label')}: ${currentGuild.name}`"
      :aria-expanded="switchable ? open : undefined"
      :aria-controls="switchable && open ? panelId : undefined"
      @click="toggle"
    >
      <img v-if="currentGuild.icon" :src="currentGuild.icon" alt="" class="h-7 w-7 shrink-0 rounded-full" />
      <span
        v-else
        class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold"
        :style="{ background: 'var(--c-border)', color: 'var(--c-text-muted)' }"
        aria-hidden="true"
      >{{ initial(currentGuild.name) }}</span>
      <span class="truncate">{{ currentGuild.name }}</span>
      <Icon v-if="switchable" icon="chevron-down" class="shrink-0 text-[10px] opacity-60" aria-hidden="true" />
    </button>

    <ul
      v-if="open"
      :id="panelId"
      role="list"
      :aria-labelledby="triggerId"
      class="absolute top-full left-0 z-30 mt-2 max-h-80 w-64 max-w-[calc(100vw-2rem)] overflow-y-auto overscroll-contain rounded-2xl p-1.5 text-sm"
      :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-2)', border: '1px solid var(--c-border)' }"
    >
      <li v-for="g in guilds" :key="g.id">
        <button
          type="button"
          :aria-current="g.id === currentGuild.id ? 'true' : undefined"
          class="flex w-full cursor-pointer items-center gap-2.5 rounded-xl border-0 px-2 py-1.5 text-left"
          :style="g.id === currentGuild.id
            ? { background: 'var(--c-accent-soft)', color: 'var(--c-text)' }
            : { background: 'transparent', color: 'var(--c-text)' }"
          @click="pick(g.id)"
        >
          <img v-if="g.icon" :src="g.icon" alt="" class="h-7 w-7 shrink-0 rounded-full" />
          <span
            v-else
            class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold"
            :style="{ background: 'var(--c-border)', color: 'var(--c-text-muted)' }"
            aria-hidden="true"
          >{{ initial(g.name) }}</span>
          <span class="min-w-0 flex-1 truncate">{{ g.name }}</span>
          <Icon v-if="g.id === currentGuild.id" icon="check" class="shrink-0 text-xs" aria-hidden="true" :style="{ color: 'var(--c-accent)' }" />
        </button>
      </li>
    </ul>
  </div>
</template>
