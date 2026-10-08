/**
 * Session state for the tree: who is signed in, and the three actions that
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

import { requestOtp as requestOtpRequest, verifyOtp as verifyOtpRequest } from '@/shared/api/auth'
import { setAuthToken, setUnauthorizedHandler } from '@/shared/api/client'
import { AuthContext } from '@/shared/auth/authContext'
import type { AuthContextValue } from '@/shared/auth/authContext'
import { clearStoredSession, readStoredSession, storeSession } from '@/shared/auth/session'

function restoredEmail(): string | null {
  const stored = readStoredSession()
  if (stored === null) return null
  setAuthToken(stored.token)
  return stored.email
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [email, setEmail] = useState<string | null>(restoredEmail)

  const requestOtp = useCallback(async (address: string) => {
    await requestOtpRequest(address)
  }, [])

  const verifyOtp = useCallback(async (address: string, code: string) => {
    const response = await verifyOtpRequest(address, code)
    setAuthToken(response.token)
    storeSession({ token: response.token, email: response.email })
    setEmail(response.email)
  }, [])

  const logout = useCallback(() => {
    setAuthToken(null)
    clearStoredSession()
    setEmail(null)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(logout)
    return () => {
      setUnauthorizedHandler(null)
    }
  }, [logout])

  const value = useMemo<AuthContextValue>(
    () => ({ email, isAuthenticated: email !== null, requestOtp, verifyOtp, logout }),
    [email, requestOtp, verifyOtp, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
