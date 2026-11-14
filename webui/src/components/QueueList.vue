<script lang="ts">
import { ref } from 'vue'
import type { QueueItem } from '../api'

// 模块级:切到别的页面再回来时先显示上次的队列(和展开状态),后台再刷新,
// 不会先空一下再弹出来。记下属于哪个服务器,换过服务器就不用。
const items = ref<QueueItem[]>([])
const expanded = ref<Set<string>>(new Set())
const showAll = ref<Set<string>>(new Set())
let cachedGuild: string | undefined
</script>

<script setup lang="ts">
import { computed, nextTick, watch } from 'vue'
import { fetchQueue, postQueue, type QueueAction, type QueueGroup } from '../api'
import { formatTime, useStatus } from '../composables/useStatus'
import { announce } from '../composables/useAnnounce'
import { usePolling } from '../composables/usePolling'
import AddToPlaylist from './AddToPlaylist.vue'
import QueueRow from './QueueRow.vue'
import { t } from '../i18n'
import { selectedGuild } from '../guild'

const { status, applyStatus } = useStatus()

const busy = ref(false)
const dragFrom = ref<number | null>(null)
const dragOver = ref<number | null>(null)
const listEl = ref<HTMLElement | null>(null)

// ---- 整张歌单一起入队的,折叠成一组 ------------------------------------------

interface Member { item: QueueItem; index: number; key: string }
type Row =
  | { kind: 'item'; key: string; member: Member }
  | { kind: 'group'; key: string; group: QueueGroup; members: Member[]; currentPos: number; duration: number }

/**
 * 每个条目的 key:id + 同一 id 第几次出现(同一首歌可以重复入队)。不带下标,
 * 删除或移动别的行时 key 不变,Vue 只移动节点,不会把后面的行全部销毁重建。
 */
const itemKeys = computed(() => {
  const seen = new Map<string, number>()
  return items.value.map((it) => {
    const n = seen.get(it.id) ?? 0
    seen.set(it.id, n + 1)
    return `${it.id}#${n}`
  })
})

/** 连续、同一组的条目合成一行;只剩一首的组就当普通单曲显示 */
const rows = computed<Row[]>(() => {
  const out: Row[] = []
  const list = items.value
  const keys = itemKeys.value
  const groupSeen = new Map<string, number>()
  let i = 0
  while (i < list.length) {
    const item = list[i]!
    const key = item.group?.key
    let j = i + 1
    if (key) while (j < list.length && list[j]!.group?.key === key) j++
    if (key && j - i > 1) {
      const members = list.slice(i, j).map((it, k) => ({ item: it, index: i + k, key: keys[i + k]! }))
      const n = groupSeen.get(key) ?? 0
      groupSeen.set(key, n + 1)
      out.push({
        kind: 'group',
        key: `g-${key}#${n}`,
        group: item.group!,
        members,
        currentPos: members.findIndex((m) => m.item.is_current),
        duration: members.reduce((sum, m) => sum + (m.item.duration || 0), 0),
      })
    } else {
      for (let k = i; k < j; k++) out.push({ kind: 'item', key: keys[k]!, member: { item: list[k]!, index: k, key: keys[k]! } })
    }
    i = j
  }
  return out
})

// 展开状态按组 key 记(队列推进、下标变化时不会自己收起);见上面的模块级 expanded / showAll
const PAGE = 100

function toggled(set: Set<string>, key: string) {
  const next = new Set(set)
  if (next.has(key)) next.delete(key)
  else next.add(key)
  return next
}
const toggleExpanded = (key: string) => (expanded.value = toggled(expanded.value, key))
const toggleShowAll = (key: string) => (showAll.value = toggled(showAll.value, key))

/** 展开后默认只渲染 100 首(从正在播的附近开始),上千首的歌单不会卡页面 */
function visibleMembers(row: Extract<Row, { kind: 'group' }>): Member[] {
  if (showAll.value.has(row.group.key) || row.members.length <= PAGE) return row.members
  const start = row.currentPos > PAGE / 2 ? row.currentPos - 10 : 0
  return row.members.slice(start, start + PAGE)
}

const nextIndex = computed(() => (status.value?.current_index ?? -1) + 1)

function onDragStart(i: number, e: DragEvent) {
  dragFrom.value = i
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.setData('text/plain', String(i))
  }
}

function onDragOver(i: number, e: DragEvent) {
  e.preventDefault()
  dragOver.value = i
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'move'
}

async function onDrop(i: number) {
  const from = dragFrom.value
  dragFrom.value = null
  dragOver.value = null
  if (from === null || from === i) return
  await moveItem(from, i)
}

/** 拖拽和"上移 / 下移"按钮共用。成功后播报新位置。 */
async function moveItem(from: number, to: number): Promise<boolean> {
  if (busy.value || to < 0 || to >= items.value.length || from === to) return false
  const title = items.value[from]!.title || t('common.untitled')
  // optimistic reorder so the row lands immediately
  const moved = items.value.splice(from, 1)[0]!
  items.value.splice(to, 0, moved)
  const ok = await act({ action: 'move', index: from, to })
  if (ok) announce(t('queue.moved', { title, n: to + 1 }))
  return ok
}

/**
 * 键盘 / 读屏用的上移、下移。Vue 移动 DOM 节点时焦点会丢,所以按 key 找回
 * 同一行的同一个按钮;移到头 / 尾按钮变成禁用时,改聚焦另一个方向的按钮。
 */
async function onMove(index: number, dir: 'up' | 'down') {
  const to = dir === 'up' ? index - 1 : index + 1
  const key = itemKeys.value[index]
  if (key === undefined) return
  const refocus = async (onlyIfLost: boolean, moved = true) => {
    await nextTick()
    const active = document.activeElement
    // 等服务器返回期间用户可能已经去了别处,那时不抢焦点
    if (onlyIfLost && active && active !== document.body) return
    // 移动后同一首歌的 key 可能和相邻的同名条目互换,所以按新位置的 key 找;失败时它回到了原位
    const rowKey = (moved ? itemKeys.value[to] : itemKeys.value[index]) ?? key
    const row = listEl.value?.querySelector<HTMLElement>(`[data-key="${CSS.escape(rowKey)}"]`)
    const btn = row?.querySelector<HTMLButtonElement>(`[data-move="${dir}"]:not(:disabled)`)
      ?? row?.querySelector<HTMLButtonElement>('[data-move]:not(:disabled)')
    if (!row || !btn) return
    // 整行滚进视口(只 focus 按钮的话,行的其余部分可能还在视口外)
    row.scrollIntoView({ block: 'nearest', inline: 'nearest' })
    if (active !== btn) btn.focus({ preventScroll: true })
  }
  if (busy.value || to < 0 || to >= items.value.length) return
  const pending = moveItem(index, to)
  await refocus(false)
  await refocus(true, await pending)
}

function onDragEnd() {
  dragFrom.value = null
  dragOver.value = null
}

async function reload(background = false) {
  const guild = selectedGuild.value
  try {
    const q = await fetchQueue({ background })
    if (guild !== selectedGuild.value) return  // 途中换了服务器:丢掉
    items.value = q.items
    cachedGuild = guild
  } catch {
    /* the status poll already surfaces connectivity errors */
  }
}

// 换服务器时旧队列立刻清掉,展开状态也不带过去
function forgetQueue() {
  items.value = []
  expanded.value = new Set()
  showAll.value = new Set()
  cachedGuild = undefined
}
if (cachedGuild !== selectedGuild.value) forgetQueue()
watch(selectedGuild, forgetQueue)

// refresh whenever (guild, playlist version) changes (covers external edits too);
// 不同服务器的队列版本号可能碰巧相同,所以服务器也算在内
// 两个源分开写:一个 getter 返回新数组的话,每次状态轮询都会被当成"变了"而重新拉队列
watch([selectedGuild, () => status.value?.version], () => reload(), { immediate: true })

// 兜底的定时刷新(下载进度等不改版本号的变化):有条目在后台下载时 3 秒一次,平时 10 秒;
// 页面隐藏时暂停,低优先级
usePolling(() => reload(true), () => (items.value.some((it) => it.download) ? 3000 : 10000)).start()

async function act(body: QueueAction): Promise<boolean> {
  if (busy.value) return false
  busy.value = true
  try {
    applyStatus(await postQueue(body))
    await reload()
    return true
  } catch {
    await reload()
    return false
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <section v-if="items.length" class="mx-auto w-full max-w-3xl px-4 pb-12">
    <div class="mb-3 flex items-center justify-between">
      <h2 class="text-sm font-semibold uppercase tracking-wider" :style="{ color: 'var(--c-text-muted)' }">
        {{ t('queue.title', { n: items.length }) }}
      </h2>
      <div class="flex items-center gap-1.5">
        <AddToPlaylist :source="{ source: 'all_queue' }" :label="t('queue.save')" />
        <button
          type="button"
          class="cursor-pointer rounded-full border-0 px-3 py-1 text-xs"
          :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text-muted)' }"
          @click="act({ action: 'clear' })"
        >{{ t('queue.clear') }}</button>
      </div>
    </div>

    <ul ref="listEl" role="list" class="@container flex flex-col gap-1.5">
      <template v-for="row in rows" :key="row.key">
        <QueueRow
          v-if="row.kind === 'item'"
          :data-key="row.key"
          :item="row.member.item"
          :index="row.member.index"
          :is-next="row.member.index === nextIndex"
          :is-last="row.member.index === items.length - 1"
          :drag-over="dragOver === row.member.index && dragFrom !== null && dragFrom !== row.member.index"
          :dragging="dragFrom === row.member.index"
          @act="act"
          @move="onMove(row.member.index, $event)"
          @dragstart="onDragStart(row.member.index, $event)"
          @dragover="onDragOver(row.member.index, $event)"
          @drop.prevent="onDrop(row.member.index)"
          @dragend="onDragEnd"
        />

        <!-- 一整张歌单:默认折叠成一行 -->
        <!-- 不加 overflow-hidden:里面每行的"加入歌单"弹层要能伸出分组底边 -->
        <li
          v-else
          class="rounded-xl"
          :style="{
            background: row.currentPos >= 0 ? 'var(--c-accent-soft)' : 'var(--c-surface)',
            boxShadow: 'var(--shadow-1)',
          }"
          :aria-current="row.currentPos >= 0 && !expanded.has(row.group.key) ? 'true' : undefined"
        >
          <div class="group flex items-center gap-3 px-3 py-2.5">
            <!-- 展开 / 收起是一个真正的按钮;播放、移除按钮是它的兄弟,不嵌套在里面 -->
            <button
              type="button"
              class="flex min-w-0 flex-1 cursor-pointer items-center gap-3 rounded-lg border-0 bg-transparent p-0 text-left"
              :style="{ color: 'inherit' }"
              :aria-expanded="expanded.has(row.group.key)"
              @click="toggleExpanded(row.group.key)"
            >
              <Icon
                :icon="expanded.has(row.group.key) ? 'chevron-down' : 'chevron-right'"
                class="w-3 shrink-0 text-xs"
                :style="{ color: 'var(--c-text-faint)' }"
              />
              <span
                class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
                :style="{ background: 'var(--c-surface-2)', color: 'var(--c-accent)' }"
              >
                <Icon :icon="row.group.kind === 'url_playlist' ? 'globe' : 'list-ul'" />
              </span>
              <span class="block min-w-0 flex-1">
                <span class="flex min-w-0 items-center gap-2 text-sm font-medium">
                  <span class="truncate" :title="row.group.name">{{ row.group.name || t('common.untitled') }}</span>
                  <span
                    class="shrink-0 rounded-full px-1.5 py-px text-[10px] font-medium"
                    :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text-muted)' }"
                  >{{ t(row.group.kind === 'url_playlist' ? 'queue.groupKindOnline' : 'queue.groupKindPlaylist') }}</span>
                </span>
                <span class="block truncate text-xs" :style="{ color: 'var(--c-text-muted)' }">
                  <template v-if="row.currentPos >= 0">
                    <Icon icon="caret-right" class="mr-1" :style="{ color: 'var(--c-accent)' }" />{{ t('queue.groupNow', {
                      i: row.currentPos + 1, n: row.members.length,
                      title: row.members[row.currentPos]!.item.title || t('common.untitled'),
                    }) }}
                  </template>
                  <template v-else>{{ t('queue.groupSongs', { n: row.members.length, time: formatTime(row.duration) }) }}</template>
                  <span v-if="row.members[0]!.item.requester" :title="t('queue.requestedBy', { name: row.members[0]!.item.requester })">
                    · <Icon icon="user" class="text-[10px]" /> {{ row.members[0]!.item.requester }}</span>
                </span>
              </span>
            </button>
            <div class="flex shrink-0 items-center gap-1 transition-opacity [@media(hover:hover)]:opacity-80 group-hover:opacity-100 group-focus-within:opacity-100">
              <button
                v-if="row.currentPos !== 0"
                type="button"
                class="cursor-pointer rounded-md border-0 px-2 py-1 text-xs"
                :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
                :title="t('queue.groupPlay')"
                :aria-label="t('common.itemAction', { action: t('queue.groupPlay'), title: row.group.name || t('common.untitled') })"
                @click="act({ action: 'play', index: row.members[0]!.index })"
              ><Icon icon="play" /></button>
              <button
                type="button"
                class="cursor-pointer rounded-md border-0 px-2 py-1 text-xs"
                :style="{ background: 'var(--c-surface-2)', color: 'var(--c-danger)' }"
                :title="t('queue.groupRemove')"
                :aria-label="t('common.itemAction', { action: t('queue.groupRemove'), title: row.group.name || t('common.untitled') })"
                @click="act({ action: 'remove_group', group: row.group.key })"
              ><Icon icon="xmark" /></button>
            </div>
          </div>

          <ul v-if="expanded.has(row.group.key)" role="list" class="@container flex flex-col gap-1 px-2 pb-2">
            <QueueRow
              v-for="m in visibleMembers(row)"
              :key="m.key"
              :data-key="m.key"
              nested
              :item="m.item"
              :index="m.index"
              :is-next="m.index === nextIndex"
              :is-last="m.index === items.length - 1"
              :drag-over="dragOver === m.index && dragFrom !== null && dragFrom !== m.index"
              :dragging="dragFrom === m.index"
              @act="act"
              @move="onMove(m.index, $event)"
              @dragstart="onDragStart(m.index, $event)"
              @dragover="onDragOver(m.index, $event)"
              @drop.prevent="onDrop(m.index)"
              @dragend="onDragEnd"
            />
            <li v-if="visibleMembers(row).length < row.members.length">
              <button
                type="button"
                class="w-full cursor-pointer rounded-lg border-0 bg-transparent py-1.5 text-xs"
                :style="{ color: 'var(--c-accent)' }"
                @click="toggleShowAll(row.group.key)"
              >{{ t('queue.showAll', { n: row.members.length }) }}</button>
            </li>
          </ul>
        </li>
      </template>
    </ul>
  </section>
</template>
