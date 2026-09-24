import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  applyTheme,
  isDark,
  readTheme,
  storeTheme,
  THEME_BOOTSTRAP_SCRIPT,
  THEME_STORAGE_KEY,
  watchSystemTheme,
} from '@/shared/design/theme'

afterEach(() => {
  localStorage.clear()
  document.documentElement.removeAttribute('data-theme')
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('readTheme', () => {
  it('defaults to light, not to the operating system', () => {
    // These pages are read in meetings and printed. Auto is a choice a
    // reader makes, never the fallback for having made none.
    expect(readTheme()).toBe('light')
  })

  it('reads back each stored mode', () => {
    for (const mode of ['light', 'dark', 'system'] as const) {
      localStorage.setItem(THEME_STORAGE_KEY, mode)
      expect(readTheme()).toBe(mode)
    }
  })

  it('treats a corrupt value as light rather than throwing', () => {
    localStorage.setItem(THEME_STORAGE_KEY, 'chartreuse')

    expect(readTheme()).toBe('light')
  })

  it('survives storage being blocked', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('site data blocked')
    })

    expect(readTheme()).toBe('light')
  })
})

describe('applyTheme', () => {
  it('stamps an explicit choice onto the document', () => {
    applyTheme('dark')

    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })

  it('removes the attribute for Auto so the OS media query can apply', () => {
    // Setting a third value would leave the prefers-color-scheme block
    // unmatched and Auto would silently mean light.
    applyTheme('dark')
    applyTheme('system')

    expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
  })
})

describe('storeTheme', () => {
  it('persists light explicitly rather than clearing the key', () => {
    // "Chose light" and "never chose" must stay distinguishable, or every
    // reader who picked light is silently moved when the default changes.
    storeTheme('light')

    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('light')
  })

  it('still applies the choice when storage throws', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('site data blocked')
    })

    storeTheme('dark')

    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })
})

describe('isDark', () => {
  it('answers from the explicit modes without consulting the OS', () => {
    const matchMedia = vi.fn()
    vi.stubGlobal('matchMedia', matchMedia)

    expect(isDark('dark')).toBe(true)
    expect(isDark('light')).toBe(false)
    expect(matchMedia).not.toHaveBeenCalled()
  })

  it('resolves Auto against the OS', () => {
    vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: true }))

    expect(isDark('system')).toBe(true)
  })

  it('falls back to light where matchMedia is missing', () => {
    vi.stubGlobal('matchMedia', undefined)

    expect(isDark('system')).toBe(false)
  })
})

describe('watchSystemTheme', () => {
  it('fires only while the reader is on Auto', () => {
    let fire = (): void => {}
    vi.stubGlobal(
      'matchMedia',
      vi.fn().mockReturnValue({
        matches: false,
        addEventListener: (_: string, handler: () => void) => {
          fire = handler
        },
        removeEventListener: () => {},
      }),
    )
    const onChange = vi.fn()
    watchSystemTheme(onChange)

    localStorage.setItem(THEME_STORAGE_KEY, 'dark')
    fire()
    expect(onChange).not.toHaveBeenCalled()

    localStorage.setItem(THEME_STORAGE_KEY, 'system')
    fire()
    expect(onChange).toHaveBeenCalledTimes(1)
  })

  it('returns a no-op where matchMedia is missing', () => {
    vi.stubGlobal('matchMedia', undefined)

    const unsubscribe = watchSystemTheme(vi.fn())

    expect(() => {
      unsubscribe()
    }).not.toThrow()
  })
})

describe('the before-first-paint stamp', () => {
  const html = readFileSync(resolve(__dirname, '../../../index.html'), 'utf-8')

  it('is inlined in index.html exactly as the module defines it', () => {
    // The stamp is duplicated by necessity — it has to run before any module
    // loads. Duplication that drifts is the failure mode, and it is silent:
    // the page keeps working and merely flashes the wrong ground colour on
    // every navigation, which nobody files a bug for.
    expect(html).toContain(THEME_BOOTSTRAP_SCRIPT)
  })

  it('carries a real storage key rather than an uninterpolated placeholder', () => {
    expect(html).toContain(`'${THEME_STORAGE_KEY}'`)
    expect(html).not.toContain('${')
  })

  it('runs before the module bundle', () => {
    expect(html.indexOf(THEME_BOOTSTRAP_SCRIPT)).toBeLessThan(html.indexOf('/src/main.tsx'))
  })

  it('agrees with readTheme about what each stored value means', () => {
    // The stamp has to run before any module exists, so it is a string to
    // every other tool in the build. Executing it is the only way to assert
    // it agrees with `readTheme`; asserting on its text would pass for a
    // stamp that reads the key and then does the wrong thing with it.
    // eslint-disable-next-line @typescript-eslint/no-implied-eval
    const stamp = new Function(THEME_BOOTSTRAP_SCRIPT) as () => void

    for (const [stored, expected] of [
      ['dark', 'dark'],
      ['light', 'light'],
      ['chartreuse', 'light'],
    ] as const) {
      localStorage.setItem(THEME_STORAGE_KEY, stored)
      document.documentElement.removeAttribute('data-theme')
      stamp()
      expect(document.documentElement.getAttribute('data-theme')).toBe(expected)
    }

    localStorage.setItem(THEME_STORAGE_KEY, 'system')
    document.documentElement.removeAttribute('data-theme')
    stamp()
    expect(document.documentElement.hasAttribute('data-theme')).toBe(false)
  })
})
