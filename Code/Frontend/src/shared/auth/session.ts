/**
 * The session persisted across a reload: the bearer token and the username
 * it was issued to.
 *
 * Every storage access is wrapped, the same discipline `shared/design/theme`
 * uses for the same reason: `localStorage` throws in a private window and
 * when site data is blocked, and a login page that crashes on that is worse
 * than one that just asks the reader to sign in again.
 */

const SESSION_STORAGE_KEY = 'nvx-session'

export interface StoredSession {
  readonly token: string
  readonly username: string
}

function isStoredSession(value: unknown): value is StoredSession {
  return (
    typeof value === 'object' &&
    value !== null &&
    typeof (value as Partial<StoredSession>).token === 'string' &&
    typeof (value as Partial<StoredSession>).username === 'string'
  )
}

export function readStoredSession(): StoredSession | null {
  try {
    const raw = localStorage.getItem(SESSION_STORAGE_KEY)
    if (raw === null) return null
    const parsed: unknown = JSON.parse(raw)
    return isStoredSession(parsed) ? parsed : null
  } catch {
    return null
  }
}

export function storeSession(session: StoredSession): void {
  try {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(session))
  } catch {
    // Storage blocked. The session still applies for this page; it just
    // will not survive a reload.
  }
}

export function clearStoredSession(): void {
  try {
    localStorage.removeItem(SESSION_STORAGE_KEY)
  } catch {
    // Nothing to do if storage is blocked — there is nothing stored to clear.
  }
}
