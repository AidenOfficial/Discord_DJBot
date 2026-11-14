<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useId } from 'vue'
import { DISCORD_LOGIN_URL, createBindCode, fetchMe, logout, saveAlias, unbindDiscord } from '../api'
import { useAnnounce } from '../composables/useAnnounce'
import { useConfirm } from '../composables/useConfirm'
import { useGuilds } from '../composables/useGuilds'
import { useMe } from '../composables/useMe'
import { embedded } from '../activity'
import { t, tParts } from '../i18n'
import type { Key } from '../i18n/en'

const { me } = useMe()
const { announce } = useAnnounce()
const { confirm } = useConfirm()

const open = ref(false)
const draft = ref('')
const saving = ref(false)
const message = ref('')
const messageOk = ref(false) // 成功时显示勾和绿色
const aliasRejected = ref(false) // 服务端拒了这个名字(重名 / 不合法):输入框标成 invalid
const root = ref<HTMLElement | null>(null)
const trigger = ref<HTMLButtonElement | null>(null)
const aliasInput = ref<HTMLInputElement | null>(null)
const copyBtn = ref<HTMLButtonElement | null>(null)
const linkBtn = ref<HTMLButtonElement | null>(null)
const unlinkBtn = ref<HTMLButtonElement | null>(null)

const uid = useId()
const ids = {
  trigger: `${uid}-trigger`,
  panel: `${uid}-panel`,
  alias: `${uid}-alias`,
  hint: `${uid}-hint`,
  msg: `${uid}-msg`,
}

const { reloadGuilds } = useGuilds()

const initial = computed(() => (me.value?.display_name || '?').trim().charAt(0).toUpperCase())
const signedIn = computed(() => !!me.value?.identity)
const viaDiscord = computed(() => me.value?.source === 'discord')
// 配置了 Discord 登录、现在不是用 Discord 登录的:给个入口(登录完回到当前页面)
const discordLoginHref = computed(() => !embedded && me.value?.discord_login_available && !viaDiscord.value
  ? `${DISCORD_LOGIN_URL}?next=${encodeURIComponent(location.pathname + location.search)}`
  : null)

async function signOut() {
  try {
    await logout()
  } catch { /* 会话可能已经没了,照样去退出页 */ }
  // 退出页不会自动跳回 Discord(门禁模式下直接刷新会被 prompt=none 立刻登录回来)
  location.href = '../auth/logout'
}

// ---- 弹层位置 ----
// 弹层右对齐头像按钮。窄屏时按钮靠左(头部换行)或右边还有别的按钮,w-72 会从屏幕左边出去,
// 而负方向的溢出没法滚动查看。打开时按视口把宽度和水平位置夹在 16px 边距内,高度不超过视口。
// 锚点定位 + position-try-fallbacks 在 Chromium / Android WebView 上还不支持,所以用脚本算。
const panelStyle = ref<Record<string, string>>({})
const GUTTER = 16
function place() {
  const el = root.value
  if (!el) return
  const r = el.getBoundingClientRect()
  const vw = document.documentElement.clientWidth
  const width = Math.min(288, vw - 2 * GUTTER)
  const shift = Math.min(0, r.right - width - GUTTER) // 负数:往右挪,让左边缘留在屏幕里
  panelStyle.value = {
    width: `${width}px`,
    right: `${shift}px`,
    maxHeight: `${Math.max(160, window.innerHeight - r.bottom - 8 - GUTTER)}px`,
  }
}

function openPanel() {
  open.value = true
  draft.value = me.value?.alias ?? ''
  message.value = ''
  aliasRejected.value = false
  place()
  window.addEventListener('resize', place)
}

function close(returnFocus = false) {
  if (!open.value) return
  // 先把焦点还给按钮再移除弹层,否则焦点会掉到 <body>
  if (returnFocus) trigger.value?.focus()
  open.value = false
  window.removeEventListener('resize', place)
}

function toggle() {
  if (open.value) close()
  else openPanel()
}

/** 操作后原来的按钮被 v-if 换掉了:焦点丢了就放到新出现的控件上 */
function keepFocus(next: () => HTMLElement | null | undefined) {
  void nextTick(() => {
    const active = document.activeElement
    if (open.value && (!active || active === document.body)) next()?.focus()
  })
}

async function save(alias: string) {
  if (saving.value) return
  saving.value = true
  message.value = ''
  try {
    me.value = await saveAlias(alias.trim())
    message.value = t(alias.trim() ? 'me.saved' : 'me.cleared')
    messageOk.value = true
    aliasRejected.value = false
    draft.value = me.value.alias
    announce(message.value)
    keepFocus(() => aliasInput.value)
  } catch (e) {
    const reason = e instanceof Error ? e.message : ''
    message.value = t(reason === 'taken' ? 'me.taken' : reason === 'invalid' ? 'me.invalid' : 'common.saveFailed')
    messageOk.value = false
    aliasRejected.value = reason === 'taken' || reason === 'invalid'
    announce(message.value, { assertive: true })
  } finally {
    saving.value = false
  }
}

// ---- Discord 绑定:生成一次性码,等用户在 Discord 里发 /bind ----
const bind = ref<{ code: string; command: string; expires_at: number } | null>(null)
const bindMsg = ref('')
const bindOk = ref(false)
const copied = ref(false)
let bindPoll: ReturnType<typeof setInterval> | undefined

function setBindMsg(text: string, ok: boolean, assertive = false) {
  bindMsg.value = text
  bindOk.value = ok
  announce(text, { assertive })
}

async function startBind() {
  bindMsg.value = ''
  bindOk.value = false
  try {
    bind.value = await createBindCode()
    keepFocus(() => copyBtn.value)
    clearInterval(bindPoll)
    bindPoll = setInterval(async () => {
      if (!bind.value || Date.now() / 1000 > bind.value.expires_at) {
        clearInterval(bindPoll)
        if (bind.value) setBindMsg(t('me.codeExpired'), false)
        bind.value = null
        keepFocus(() => linkBtn.value)
        return
      }
      try {
        const fresh = await fetchMe()
        if (fresh.discord) {
          me.value = fresh
          bind.value = null
          setBindMsg(t('me.linked', { name: fresh.discord.discord_name }), true)
          clearInterval(bindPoll)
          keepFocus(() => unlinkBtn.value)
          reloadGuilds()  // 绑定后能操作的服务器变了
        }
      } catch { /* 下一轮再试 */ }
    }, 3000)
  } catch {
    setBindMsg(t('me.codeFailed'), false, true)
  }
}

async function copyCommand() {
  if (!bind.value) return
  try {
    await navigator.clipboard.writeText(bind.value.command)
    copied.value = true
    announce(t('me.copied'))
    setTimeout(() => (copied.value = false), 1500)
  } catch { /* 不支持剪贴板就手动抄 */ }
}

async function unlink() {
  if (!(await confirm({ message: t('me.confirmUnlink'), confirmLabel: t('me.unlink'), destructive: true }))) return
  try {
    me.value = await unbindDiscord()
  } catch {
    setBindMsg(t('common.failed'), false, true)
    return
  }
  setBindMsg(t('me.unlinked'), false)
  keepFocus(() => linkBtn.value)
  reloadGuilds()
}

onBeforeUnmount(() => clearInterval(bindPoll))

// 确认框(<dialog>)不在 root 里,但它是从弹层里打开的:在里面点击 / 按 Esc 不算离开弹层
function inDialog(target: EventTarget | null) {
  return target instanceof Element && !!target.closest('dialog')
}

// 捕获阶段监听:别的组件的 @click.stop 拦不住它,点开别的弹层时这个也会关
function onDocClick(e: MouseEvent) {
  if (!open.value || !root.value || inDialog(e.target)) return
  if (!root.value.contains(e.target as Node)) close()
}
function onKey(e: KeyboardEvent) {
  if (e.key !== 'Escape' || !open.value || e.defaultPrevented || inDialog(e.target)) return
  close(!!root.value?.contains(document.activeElement))
}
// Tab 出弹层就关掉。relatedTarget 为空(iOS 上点了不可聚焦的地方、焦点去了浏览器外壳)时不关
function onFocusOut(e: FocusEvent) {
  const next = e.relatedTarget
  if (!open.value || !(next instanceof Node) || inDialog(next)) return
  if (root.value && !root.value.contains(next)) close()
}
onMounted(() => {
  document.addEventListener('click', onDocClick, true)
  document.addEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick, true)
  document.removeEventListener('keydown', onKey)
  window.removeEventListener('resize', place)
})

const SOURCE_LABEL: Record<string, Key> = {
  'discord': 'me.src.discord',
  'cloudflare': 'me.src.cloudflare',
  'cloudflare-jwt': 'me.src.cloudflareJwt',
  'web-user': 'me.src.webUser',
  'anonymous': 'me.src.anonymous',
}
</script>

<template>
  <div ref="root" class="relative" @focusout="onFocusOut">
    <button
      :id="ids.trigger"
      ref="trigger"
      type="button"
      class="flex h-9 max-w-[9rem] cursor-pointer items-center gap-2 rounded-full border-0 py-1 pr-3 pl-1 text-xs font-medium"
      :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
      :title="me?.email || t('me.whoami')"
      :aria-expanded="open"
      :aria-controls="open ? ids.panel : undefined"
      @click="toggle"
    >
      <span
        class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold"
        :style="signedIn
          ? { background: 'var(--c-accent)', color: 'var(--c-on-accent)' }
          : { background: 'var(--c-border)', color: 'var(--c-text-muted)' }"
        aria-hidden="true"
      >{{ signedIn ? initial : '?' }}</span>
      <span class="truncate">{{ signedIn ? me?.display_name : t('me.guest') }}</span>
    </button>

    <div
      v-if="open"
      :id="ids.panel"
      role="group"
      :aria-labelledby="ids.trigger"
      class="absolute top-full right-0 z-30 mt-2 w-72 max-w-[calc(100vw-2rem)] overflow-y-auto overscroll-contain rounded-2xl p-4 text-sm"
      :style="{ background: 'var(--c-surface)', boxShadow: 'var(--shadow-2)', border: '1px solid var(--c-border)', ...panelStyle }"
    >
      <template v-if="signedIn">
        <p class="text-xs" :style="{ color: 'var(--c-text-muted)' }">{{ t('me.signedInAs') }}</p>
        <p class="truncate font-medium" :title="me?.email || me?.identity || ''">{{ me?.email || me?.identity }}</p>
        <p class="mt-0.5 text-[11px]" :style="{ color: 'var(--c-text-faint)' }">{{ t('me.via', { source: t(SOURCE_LABEL[me?.source ?? 'anonymous'] ?? 'me.src.anonymous') }) }}</p>

        <label class="mt-4 block text-xs font-medium" :style="{ color: 'var(--c-text-muted)' }" :for="ids.alias">
          {{ t('me.displayName') }}
        </label>
        <p :id="ids.hint" class="text-[11px]" :style="{ color: 'var(--c-text-faint)' }">
          {{ t('me.displayNameHint') }}
        </p>
        <form class="mt-2 flex gap-2" @submit.prevent="save(draft)">
          <input
            :id="ids.alias"
            ref="aliasInput"
            v-model="draft"
            maxlength="24"
            :placeholder="me?.email?.split('@')[0] ?? t('me.aliasPlaceholder')"
            class="min-w-0 flex-1 rounded-lg border px-3 py-1.5 text-sm"
            :style="{ background: 'var(--c-bg)', borderColor: aliasRejected ? 'var(--c-danger)' : 'var(--c-border)', color: 'var(--c-text)' }"
            :aria-invalid="aliasRejected ? 'true' : undefined"
            :aria-describedby="aliasRejected ? `${ids.msg} ${ids.hint}` : ids.hint"
          />
          <button
            type="submit"
            class="cursor-pointer rounded-lg border-0 px-3 py-1.5 text-xs font-semibold"
            :style="{ background: 'var(--c-accent)', color: 'var(--c-on-accent)' }"
            :aria-disabled="saving ? 'true' : undefined"
          >{{ t('common.save') }}</button>
        </form>
        <div class="mt-2 flex items-center justify-between">
          <span :id="ids.msg" class="text-xs" :style="{ color: messageOk ? 'var(--c-success)' : 'var(--c-danger)' }"><Icon v-if="messageOk" icon="check" class="mr-1" aria-hidden="true" />{{ message }}</span>
          <button
            v-if="me?.alias"
            type="button"
            class="cursor-pointer border-0 bg-transparent p-0 text-xs underline"
            :style="{ color: 'var(--c-text-muted)' }"
            @click="save('')"
          >{{ t('me.clear') }}</button>
        </div>

        <!-- Discord 账号绑定 -->
        <div class="mt-4 border-t pt-3" :style="{ borderColor: 'var(--c-border)' }">
          <p class="text-xs font-medium" :style="{ color: 'var(--c-text-muted)' }">{{ t('me.discord') }}</p>
          <template v-if="me?.discord">
            <div class="mt-1 flex items-center justify-between">
              <span class="text-sm"><Icon icon="headphones" class="mr-1.5" aria-hidden="true" :style="{ color: 'var(--c-accent)' }" />{{ me.discord.discord_name }}</span>
              <button ref="unlinkBtn" type="button" class="cursor-pointer border-0 bg-transparent p-0 text-xs underline"
                      :style="{ color: 'var(--c-text-muted)' }" @click="unlink">{{ t('me.unlink') }}</button>
            </div>
            <p class="mt-1 text-[11px]" :style="{ color: 'var(--c-text-faint)' }">
              <template v-for="(p, i) in tParts('me.discordHint', { mylist: '/mylist', fav: '/fav' })" :key="i"><b
                v-if="p.param">{{ p.text }}</b><template v-else>{{ p.text }}</template></template>
            </p>
          </template>
          <template v-else-if="bind">
            <p class="mt-1 text-[11px]" :style="{ color: 'var(--c-text-faint)' }">{{ t('me.sendThis') }}</p>
            <button
              ref="copyBtn"
              type="button"
              class="mt-1.5 flex w-full cursor-pointer items-center justify-between rounded-lg border-0 px-3 py-2 font-mono text-base tracking-wider"
              :style="{ background: 'var(--c-bg)', color: 'var(--c-text)' }"
              :title="t('me.copy')"
              @click="copyCommand"
            >{{ bind.command }}<span class="font-sans text-[11px]" :style="{ color: 'var(--c-text-faint)' }"><Icon v-if="copied" icon="check" class="mr-1" aria-hidden="true" />{{ t(copied ? 'me.copied' : 'me.copy') }}</span></button>
            <p class="mt-1 text-[11px]" :style="{ color: 'var(--c-text-faint)' }">{{ t('me.validFor') }}</p>
          </template>
          <button
            v-else
            ref="linkBtn"
            type="button"
            class="mt-1.5 w-full cursor-pointer rounded-lg border-0 px-3 py-1.5 text-xs font-medium"
            :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
            @click="startBind"
          >{{ t('me.link') }}</button>
          <p v-if="bindMsg" class="mt-1 text-xs" :style="{ color: bindOk ? 'var(--c-success)' : 'var(--c-text-muted)' }"><Icon v-if="bindOk" icon="check" class="mr-1" aria-hidden="true" />{{ bindMsg }}</p>
        </div>
      </template>
      <template v-else>
        <p class="font-medium">{{ t('me.guestTitle') }}</p>
        <p class="mt-1 text-xs leading-relaxed" :style="{ color: 'var(--c-text-muted)' }">{{ t('me.guestHint') }}</p>
      </template>

      <!-- Discord 登录 / 退出 -->
      <a
        v-if="discordLoginHref"
        :href="discordLoginHref"
        class="mt-4 flex w-full items-center justify-center rounded-lg px-3 py-1.5 text-xs font-semibold no-underline"
        :style="{ background: 'var(--c-accent)', color: 'var(--c-on-accent)' }"
      ><Icon icon="headphones" class="mr-1.5" aria-hidden="true" />{{ t('me.loginDiscord') }}</a>
      <!-- Activity 里登录跟着 Discord,关掉 Activity 就退出 -->
      <button
        v-if="viaDiscord && !embedded"
        type="button"
        class="mt-4 w-full cursor-pointer rounded-lg border-0 px-3 py-1.5 text-xs font-medium"
        :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
        @click="signOut"
      ><Icon icon="right-from-bracket" class="mr-1.5" aria-hidden="true" />{{ t('me.logout') }}</button>
    </div>
  </div>
</template>
