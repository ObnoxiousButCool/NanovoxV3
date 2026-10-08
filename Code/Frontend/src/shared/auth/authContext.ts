/**
 * The auth context and its hook, separate from the provider component.
 *
 * Split for the same reason `shared/design/themeContext` is: React Fast
 * Refresh only works on a module whose exports are all components, and a
 * mixed module silently loses hot reloading for the whole tree.
 */

import { createContext, useContext } from 'react'

export interface AuthContextValue {
  /** The signed-in username, or `null` before sign-in. */
  username: string | null
  isAuthenticated: boolean
  /** Throws `ApiError` (401) for a wrong username, wrong password, or both. */
  login: (username: string, password: string) => Promise<void>
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
