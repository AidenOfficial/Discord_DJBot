<script setup lang="ts">
// The one confirmation dialog, driven by useConfirm(). Native <dialog> opened with
// showModal(): the browser makes the page inert, keeps focus inside, closes on Esc
// and the mobile back gesture, and returns focus to the opener on close.
import { nextTick, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'
import { t } from '../i18n'
import { confirmRequest, fallbackConfirm, registerConfirmHost, type ConfirmRequest } from '../composables/useConfirm'

const dlg = ref<HTMLDialogElement>()
const cancelBtn = ref<HTMLButtonElement>()
// What is on screen. Kept after the request settles so the text does not blank out while closing.
const shown = ref<ConfirmRequest | null>(null)
const titleId = useId()
const descId = useId()

let unregister: (() => void) | undefined
onMounted(() => { unregister = registerConfirmHost() })
onBeforeUnmount(() => {
  unregister?.()
  shown.value?.resolve(false)
})

watch(confirmRequest, async (req) => {
  if (!req) return
  shown.value = req
  await nextTick()
  const d = dlg.value
  if (!d) {
    req.resolve(fallbackConfirm(req.message))
    return
  }
  if (d.open) {
    // Replaced while open: new text, focus back on the safe action.
    cancelBtn.value?.focus()
    return
  }
  d.returnValue = ''
  try {
    d.showModal()
  } catch {
    req.resolve(fallbackConfirm(req.message))
  }
})

function onClose() {
  const d = dlg.value
  // Esc / back gesture set no returnValue; browsers differ on clearing an old one, so reset it.
  const ok = d?.returnValue === 'confirm'
  if (d) d.returnValue = ''
  shown.value?.resolve(ok)
}
</script>

<template>
  <dialog
    ref="dlg"
    class="m-auto w-[min(26rem,calc(100vw-2rem))] rounded-2xl border-0 p-0"
    :style="{ background: 'var(--c-surface)', color: 'var(--c-text)', boxShadow: 'var(--shadow-2)' }"
    :aria-labelledby="titleId"
    :aria-describedby="shown?.title ? descId : undefined"
    @close="onClose"
  >
    <form method="dialog" class="p-5">
      <h2 :id="titleId" class="text-base font-semibold leading-snug break-words">{{ shown?.title || shown?.message }}</h2>
      <p
        v-if="shown?.title"
        :id="descId"
        class="mt-2 text-sm leading-relaxed break-words"
        :style="{ color: 'var(--c-text-muted)' }"
      >{{ shown.message }}</p>
      <div class="mt-5 flex flex-wrap justify-end gap-2">
        <button
          ref="cancelBtn"
          value="cancel"
          autofocus
          class="min-h-10 cursor-pointer rounded-full border-0 px-4 text-sm font-medium"
          :style="{ background: 'var(--c-surface-2)', color: 'var(--c-text)' }"
        >{{ shown?.cancelLabel || t('common.cancel') }}</button>
        <button
          value="confirm"
          class="min-h-10 cursor-pointer rounded-full border-0 px-4 text-sm font-semibold"
          :style="shown?.destructive
            ? { background: 'var(--c-danger)', color: 'var(--c-on-danger)' }
            : { background: 'var(--c-accent)', color: 'var(--c-on-accent)' }"
        >{{ shown?.confirmLabel || t('common.confirm') }}</button>
      </div>
    </form>
  </dialog>
</template>
