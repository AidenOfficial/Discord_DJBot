import { getCurrentScope, onScopeDispose } from 'vue'

export interface Poller {
  /** Start polling. runNow runs the task at once instead of after the first delay. */
  start(runNow?: boolean): void
  stop(): void
}

/**
 * setTimeout chain that pauses while the page is hidden (another tab, Discord
 * minimised; Electron often does not throttle background timers) and runs the
 * task at once when the page becomes visible again, so the view is fresh. The
 * next run is scheduled only after the previous one settles, so slow responses
 * never pile up. Stops by itself when the calling component or scope goes away.
 */
export function usePolling(task: () => unknown, delay: number | (() => number)): Poller {
  let timer: ReturnType<typeof setTimeout> | undefined
  let active = false
  let running = false

  const hidden = () => document.visibilityState === 'hidden'

  function clear() {
    clearTimeout(timer)
    timer = undefined
  }

  function schedule() {
    clear()
    if (active && !hidden()) timer = setTimeout(run, typeof delay === 'function' ? delay() : delay)
  }

  async function run() {
    timer = undefined
    if (!active || running) return
    running = true
    try {
      await task()
    } catch {
      /* the task reports its own errors; keep polling */
    } finally {
      running = false
    }
    schedule()
  }

  function onVisibility() {
    if (!active) return
    if (hidden()) clear()
    else if (!timer && !running) void run()
  }

  function start(runNow = false) {
    if (!active) {
      active = true
      document.addEventListener('visibilitychange', onVisibility)
    }
    if (runNow) {
      clear()
      void run()
    } else if (!timer && !running) {
      schedule()
    }
  }

  function stop() {
    active = false
    clear()
    document.removeEventListener('visibilitychange', onVisibility)
  }

  if (getCurrentScope()) onScopeDispose(stop)
  return { start, stop }
}
