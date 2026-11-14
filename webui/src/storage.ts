// localStorage that never throws. Inside the Discord Activity the page is a
// third-party iframe (*.discordsays.com inside discord.com), and with site data
// blocked or in private modes even reading `window.localStorage` throws a
// SecurityError. Callers get null / false instead and should still apply the
// setting for this session, just without persisting it.

function store(): Storage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}

/** The stored string, or null when missing or storage is unavailable. */
export function getItem(key: string): string | null {
  try {
    return store()?.getItem(key) ?? null
  } catch {
    return null
  }
}

/** true when the value was persisted. Quota errors and blocked storage give false. */
export function setItem(key: string, value: string): boolean {
  try {
    const s = store()
    if (!s) return false
    s.setItem(key, value)
    return true
  } catch {
    return false
  }
}

/** true when storage was reachable (whether or not the key existed). */
export function removeItem(key: string): boolean {
  try {
    const s = store()
    if (!s) return false
    s.removeItem(key)
    return true
  } catch {
    return false
  }
}
