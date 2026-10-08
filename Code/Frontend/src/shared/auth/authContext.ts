/**
 * The auth context and its hook, separate from the provider component.
 *
 * Split for the same reason `shared/design/themeContext` is: React Fast
 * Refresh only works on a module whose exports are all components, and a
 * mixed module silently loses hot reloading for the whole tree.
 */

import { createContext, useContext } from 'react'

export interface AuthContextValue {
  /** The signed-in address, or `null` before sign-in. */
  email: string | null
  isAuthenticated: boolean
  /** Always resolves, even for an unapproved or malformed address — see
   * `application.use_cases.auth.RequestOtp` on why the API answers the
   * same way either way. */
  requestOtp: (email: string) => Promise<void>
  /** Throws `ApiError` (401) for a wrong, used or expired code. */
  verifyOtp: (email: string, code: string) => Promise<void>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (!value) {
    throw new Error('useAuth must be used inside an AuthProvider.')
  }
  return value
}
