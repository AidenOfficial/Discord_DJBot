// App-wide screen reader announcements: one polite and one assertive live region,
// created once by mountAnnouncer() (main.ts calls it before the app mounts, so the
// regions exist before any text is written into them, which live regions need).
//
// announce('Saved') for results and status ("Added to X", "Saved", "3 results");
// announce(msg, { assertive: true }) only for failures the user must act on
// (server unreachable, a save that did not happen).
//
// Where document.ariaNotify() exists (Chromium 141+, Safari 27+) it is used instead
// of the regions; iOS WKWebView and older Discord desktop builds use the regions.
//
// Visible toasts stay as they are: call announce() alongside setting them, and do
// not also put aria-live / role="status" on the toast element (it would read twice).

export interface AnnounceOptions {
  /** Interrupts speech. Only for errors / connectivity loss. Default: polite. */
  assertive?: boolean
}

type Priority = 'polite' | 'assertive'

const DEBOUNCE_MS: Record<Priority, number> = { polite: 250, assertive: 50 }
// The same text again within this window is dropped (double clicks, repeated
// polling errors); after it, the same text is announced again.
const DEDUPE_MS = 1500
// Clear the region afterwards so stale text is not found when browsing the page.
const CLEAR_MS = 7000

const regions: Partial<Record<Priority, HTMLElement>> = {}
const pending: Record<Priority, string> = { polite: '', assertive: '' }
const timers: Partial<Record<Priority, ReturnType<typeof setTimeout>>> = {}
const clearTimers: Partial<Record<Priority, ReturnType<typeof setTimeout>>> = {}
const last: Record<Priority, { text: string; at: number }> = {
  polite: { text: '', at: 0 },
  assertive: { text: '', at: 0 },
}

type AriaNotifyDocument = Document & {
  ariaNotify?: (announcement: string, options?: { priority?: 'normal' | 'high' }) => void
}

function createRegion(priority: Priority): HTMLElement {
  const el = document.createElement('div')
  el.className = 'visually-hidden'
  if (priority === 'polite') el.setAttribute('role', 'status')
  else el.setAttribute('aria-live', 'assertive')
  el.setAttribute('aria-atomic', 'true')
  el.dataset.announcer = priority
  document.body.append(el)
  return el
}

/** Creates the two live regions at the end of <body>. Safe to call more than once. */
export function mountAnnouncer(): void {
  if (typeof document === 'undefined' || !document.body) return
  for (const p of ['polite', 'assertive'] as const) {
    if (!regions[p]?.isConnected) regions[p] = createRegion(p)
  }
}

/** The open modal <dialog>, if any. Everything outside it is inert, so a live
 *  region in <body> would not be read until it closes. */
function openModal(): HTMLDialogElement | null {
  try {
    return document.querySelector<HTMLDialogElement>('dialog:modal')
  } catch {
    return document.querySelector<HTMLDialogElement>('dialog[open]')
  }
}

function flush(priority: Priority) {
  const text = pending[priority]
  pending[priority] = ''
  if (!text) return

  const modal = openModal()
  if (modal) {
    pending[priority] = text
    modal.addEventListener('close', () => setTimeout(() => flush(priority), 100), { once: true })
    return
  }

  const now = Date.now()
  if (last[priority].text === text && now - last[priority].at < DEDUPE_MS) return
  last[priority] = { text, at: now }

  const doc = document as AriaNotifyDocument
  if (typeof doc.ariaNotify === 'function') {
    try {
      doc.ariaNotify(text, { priority: priority === 'assertive' ? 'high' : 'normal' })
      return
    } catch { /* fall through to the live region */ }
  }

  mountAnnouncer()
  const region = regions[priority]
  if (!region) return
  // Empty first, then write a moment later: an identical string written into a
  // region that already holds it is not re-announced. (A timer, not rAF, which
  // pauses while the tab or the Activity is in the background.)
  region.textContent = ''
  clearTimeout(clearTimers[priority])
  setTimeout(() => {
    region.textContent = text
    clearTimers[priority] = setTimeout(() => { region.textContent = '' }, CLEAR_MS)
  }, 50)
}

/** Queue a message for screen readers. Rapid calls collapse to the latest one. */
export function announce(message: string, options: AnnounceOptions = {}): void {
  const text = message.trim()
  if (!text || typeof document === 'undefined') return
  const priority: Priority = options.assertive ? 'assertive' : 'polite'
  pending[priority] = text
  clearTimeout(timers[priority])
  timers[priority] = setTimeout(() => flush(priority), DEBOUNCE_MS[priority])
}

export function useAnnounce() {
  return { announce }
}
