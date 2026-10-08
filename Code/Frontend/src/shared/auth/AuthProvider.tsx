/**
 * Session state for the tree: who is signed in, and the two actions that
 * change it.
 *
 * The token lives in two places on purpose. `shared/api/client` holds it in
 * memory, because that is what every request actually reads. This provider
 * additionally persists it to `localStorage` (`shared/auth/session`) so a
 * reload does not sign the reader out — read back once, synchronously, at
 * construction, the same way `ThemeProvider` restores `readTheme()`.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { login as loginRequest } from '@/shared/api/auth'
import { setAuthToken, setUnauthorizedHandler } from '@/shared/api/client'
import { AuthContext } from '@/shared/auth/authContext'
import type { AuthContextValue } from '@/shared/auth/authContext'
import { clearStoredSession, readStoredSession, storeSession } from '@/shared/auth/session'

function restoredUsername(): string | null {
  const stored = readStoredSession()
  if (stored === null) return null
  setAuthToken(stored.token)
  return stored.username
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [username, setUsername] = useState<string | null>(restoredUsername)

  const login = useCallback(async (candidateUsername: string, password: string) => {
    const response = await loginRequest(candidateUsername, password)
    setAuthToken(response.token)
    storeSession({ token: response.token, username: response.username })
    setUsername(response.username)
  }, [])

  const logout = useCallback(() => {
    setAuthToken(null)
    clearStoredSession()
    setUsername(null)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(logout)
    return () => {
      setUnauthorizedHandler(null)
    }
  }, [logout])

  const value = useMemo<AuthContextValue>(
    () => ({ username, isAuthenticated: username !== null, login, logout }),
    [username, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
