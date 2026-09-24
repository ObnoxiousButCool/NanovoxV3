/**
 * Theme state for the tree, and the redraw signal charts need.
 *
 * `themeVersion` exists because CSS cannot carry the whole job. Charts write
 * some colours into SVG attributes, so a live theme switch has to make them
 * redraw; a component that resolves a token at render time subscribes to
 * this number and re-renders when it changes. Anything expressible in CSS
 * should read a token and ignore it.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { applyTheme, isDark, readTheme, storeTheme, watchSystemTheme } from '@/shared/design/theme'
import type { ThemeMode } from '@/shared/design/theme'
import { ThemeContext } from '@/shared/design/themeContext'
import type { ThemeContextValue } from '@/shared/design/themeContext'

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>(readTheme)
  const [themeVersion, setThemeVersion] = useState(0)

  // The bootstrap script already stamped the attribute before first paint.
  // This re-applies it so the DOM still matches after a hot reload, or if
  // the script was stripped from the host page.
  useEffect(() => {
    applyTheme(mode)
  }, [mode])

  // Someone on Auto whose OS flips gets no React update otherwise, and
  // anything that cached a colour would keep the other theme's ink.
  useEffect(
    () =>
      watchSystemTheme(() => {
        setThemeVersion((n) => n + 1)
      }),
    [],
  )

  const setMode = useCallback((next: ThemeMode) => {
    storeTheme(next)
    setModeState(next)
    setThemeVersion((n) => n + 1)
  }, [])

  const value = useMemo<ThemeContextValue>(
    () => ({ mode, dark: isDark(mode), setMode, themeVersion }),
    // `themeVersion` is a dependency on purpose: on Auto, `isDark(mode)` can
    // change without `mode` changing, and that is exactly the case this
    // provider exists to catch.
    [mode, setMode, themeVersion],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
