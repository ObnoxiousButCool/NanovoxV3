/**
 * The three-state colour theme: Light, Dark, Auto.
 *
 * Ported from the prototype's `app.js`, including its reasoning.
 *
 * **Light is the default, not Auto.** These pages are read in meetings and
 * printed, where a dark ground is the wrong starting point however the
 * laptop is set. Auto is a deliberate choice a reader makes, not the
 * fallback for having made none.
 *
 * **All three values are stored, including `light`.** Removing the key for
 * light would make "chose light" and "never chose" the same state. That is
 * harmless today and stops being harmless the moment the default changes —
 * at which point every reader who had explicitly chosen light would be
 * silently moved off it.
 *
 * **Every storage access is wrapped.** `localStorage` throws in a private
 * window and when site data is blocked. A theme control that crashes the
 * page it sits on is worse than one that forgets.
 */

export type ThemeMode = 'light' | 'dark' | 'system'

/** The key the prototype uses. Kept so a reader's choice survives the port. */
export const THEME_STORAGE_KEY = 'nvx-theme'

export const THEME_MODES: ReadonlyArray<{ value: ThemeMode; label: string }> = [
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
  { value: 'system', label: 'Auto' },
]

/**
 * What is stored, or `light`.
 *
 * Anything unrecognised reads as `light` rather than throwing: the value can
 * be edited by hand, and a corrupt key should cost a reader their preference,
 * not their page.
 */
export function readTheme(): ThemeMode {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY)
    return stored === 'dark' || stored === 'system' ? stored : 'light'
  } catch {
    return 'light'
  }
}

/**
 * Put the mode on `<html>`.
 *
 * `system` *removes* the attribute rather than setting a third value, which
 * is what lets the `prefers-color-scheme` block in `tokens.css` apply. That
 * block is guarded by `:not([data-theme="light"])`, so an explicit light
 * choice still beats a dark OS.
 */
export function applyTheme(mode: ThemeMode): void {
  const root = document.documentElement
  if (mode === 'light' || mode === 'dark') {
    root.setAttribute('data-theme', mode)
  } else {
    root.removeAttribute('data-theme')
  }
}

/** Persist and apply. Storage failure still leaves the choice applied. */
export function storeTheme(mode: ThemeMode): void {
  try {
    localStorage.setItem(THEME_STORAGE_KEY, mode)
  } catch {
    // Storage blocked. The choice still applies for this page, which is
    // better than refusing to honour it at all.
  }
  applyTheme(mode)
}

/**
 * Whether the rendered theme is currently dark, resolving `system`.
 *
 * Charts bake some colours into SVG attributes rather than leaving them to
 * CSS, so they need to know this to redraw. Everything expressible in CSS
 * should read a token instead and never call this.
 */
export function isDark(mode: ThemeMode = readTheme()): boolean {
  if (mode === 'dark') return true
  if (mode === 'light') return false
  try {
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  } catch {
    return false
  }
}

/**
 * Call `onChange` when the OS flips and the reader is on Auto.
 *
 * Someone on Auto gets no React state change when their OS switches, so
 * anything that cached a colour — a chart, a canvas — would keep the other
 * theme's ink until something else happened to re-render it.
 *
 * Returns an unsubscribe function, or a no-op where `matchMedia` is missing.
 */
export function watchSystemTheme(onChange: () => void): () => void {
  try {
    const query = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = (): void => {
      if (readTheme() === 'system') onChange()
    }
    query.addEventListener('change', handler)
    return () => {
      query.removeEventListener('change', handler)
    }
  } catch {
    return () => {}
  }
}

/**
 * The script that stamps the theme before first paint.
 *
 * Inlined into `index.html` rather than run from the bundle: by the time a
 * module has loaded the ground colour has already been painted, and the
 * reader sees a white flash before their dark theme arrives. It is stringly
 * typed because it has to run before any of this file exists.
 *
 * Exported so a test can assert it stays in step with `readTheme`.
 */
export const THEME_BOOTSTRAP_SCRIPT = `try{var t=localStorage.getItem('${THEME_STORAGE_KEY}');if(t!=='system')document.documentElement.setAttribute('data-theme',t==='dark'?'dark':'light')}catch(e){}`
