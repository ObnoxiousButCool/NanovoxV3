/**
 * The three-way theme control that sits at the foot of the rail.
 *
 * A radio group rather than a toggle, because there are three states and the
 * third — Auto — is not "neither of the other two". `aria-pressed` says which
 * is active, so the current choice is announced rather than only coloured.
 */

import { THEME_MODES } from '@/shared/design/theme'
import { useTheme } from '@/shared/design/themeContext'

export function ThemeControl() {
  const { mode, setMode } = useTheme()

  return (
    <div className="nv-themer" role="group" aria-label="Colour theme">
      {THEME_MODES.map(({ value, label }) => (
        <button
          key={value}
          type="button"
          aria-pressed={value === mode}
          onClick={() => {
            setMode(value)
          }}
        >
          {label}
        </button>
      ))}
    </div>
  )
}
