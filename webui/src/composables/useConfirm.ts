// Promise-based confirmation, replacing window.confirm(). Inside the Discord
// Activity (a cross-origin iframe) confirm() is headed with the proxy host on
// desktop and, on iOS WKWebView, silently returns false unless the host app
// implements the panel, so the guarded action never runs.
//
//   const { confirm } = useConfirm()
//   if (!(await confirm({ message: t('pl.confirmDelete', { name }), confirmLabel: t('common.delete'), destructive: true }))) return
//
// The dialog itself is ConfirmDialog.vue, rendered once next to the app by main.ts.
import { shallowRef } from 'vue'

export interface ConfirmOptions {
  /** The question. Shown as the dialog heading when there is no title. */
  message: string
  /** Optional short heading; the message then becomes the description. */
  title?: string
  /** Default: t('common.confirm'). Name the action, e.g. t('common.delete'). */
  confirmLabel?: string
  /** Default: t('common.cancel'). */
  cancelLabel?: string
  /** Danger-colored confirm button. Cancel always gets initial focus. */
  destructive?: boolean
}

export interface ConfirmRequest extends ConfirmOptions {
  id: number
  resolve: (ok: boolean) => void
}

/** The request ConfirmDialog.vue should show. Internal to the two files. */
export const confirmRequest = shallowRef<ConfirmRequest | null>(null)

let hosts = 0
let seq = 0

/** Called by ConfirmDialog.vue on mount / unmount. */
export function registerConfirmHost(): () => void {
  hosts++
  return () => { hosts-- }
}

function nativeConfirm(message: string): boolean {
  try {
    return window.confirm(message)
  } catch {
    return false
  }
}

/** Resolves true only when the user picks the confirm button. Esc, the back
 *  gesture and Cancel resolve false. A new call dismisses an open one (false). */
export function confirmDialog(options: ConfirmOptions | string): Promise<boolean> {
  const opts: ConfirmOptions = typeof options === 'string' ? { message: options } : options
  if (hosts === 0) return Promise.resolve(nativeConfirm(opts.message))
  confirmRequest.value?.resolve(false)
  return new Promise<boolean>((resolve) => {
    let settled = false
    const req: ConfirmRequest = {
      ...opts,
      id: ++seq,
      resolve: (ok) => {
        if (settled) return
        settled = true
        if (confirmRequest.value === req) confirmRequest.value = null
        resolve(ok)
      },
    }
    confirmRequest.value = req
  })
}

/** Fallback used by ConfirmDialog.vue when showModal() is unavailable. */
export { nativeConfirm as fallbackConfirm }

export function useConfirm() {
  return { confirm: confirmDialog }
}
