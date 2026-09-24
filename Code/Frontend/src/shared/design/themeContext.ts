/**
 * The theme context and its hook, separate from the provider component.
 *
 * Split purely so `ThemeProvider.tsx` exports a component and nothing else:
 * React Fast Refresh only works on a module whose exports are all components,
 * and a mixed module silently loses hot reloading for the whole tree.
 */

import { createContext, useContext } from 'react'

import type { ThemeMode } from '@/shared/design/theme'

export interface ThemeContextValue {
  mode: ThemeMode
  /** The mode resolved against the OS, so `system` becomes a real answer. */
  dark: boolean
  setMode: (mode: ThemeMode) => void
  /** Increments whenever the rendered theme changes. Charts key off it. */
  themeVersion: number
}

export const ThemeContext = createContext<ThemeContextValue | null>(null)

export function useTheme(): ThemeContextValue {
  const value = useContext(ThemeContext)
  if (!value) {
    throw new Error('useTheme must be used inside a ThemeProvider.')
  }
  return value
}
