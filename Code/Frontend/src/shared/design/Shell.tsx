/**
 * The application shell: the rail, and the column the screens render into.
 *
 * The rail's brand mark and nav come from the v2 prototype; the corpus
 * footnote at its foot does not yet, because the figures in it — how many
 * calls were written of how many planned, and over what dates — are corpus
 * facts this application has to read rather than hard-code. The prototype
 * reads them from its generated `data.js`; here they arrive from
 * `scope.corpusPeriod` once a screen has loaded. Until then the slot stays
 * empty rather than carrying invented numbers.
 */

import { NavLink } from 'react-router-dom'
import type { ReactNode } from 'react'

import { useAuth } from '@/shared/auth/authContext'
import { Drawer } from '@/shared/design/drawer'
import { NAV_ITEMS } from '@/shared/design/navigation'
import { ThemeControl } from '@/shared/design/ThemeControl'
import { useSharedSearch } from '@/shared/filters/useFilters'
import '@/shared/design/shell.css'

export function Shell({ children }: { children: ReactNode }) {
  // The filter bar is shared, so the rail has to carry it. Without this a
  // reader who narrows to a region on the executive screen and then asks
  // "what are the risks?" arrives at the whole book, with the bar reading
  // "No filters applied" — their narrowing silently undone by the act of
  // following it up. The prototype's `NV.href` appends the same state to
  // every rail link for the same reason.
  //
  // Only the bar's own keys travel; see `sharedSearch`.
  const search = useSharedSearch()
  // Email-OTP login (feature/email-otp-login, not on main).
  const { email, logout } = useAuth()

  return (
    <div className="nv-shell">
      <aside className="nv-rail">
        <div className="nv-brandmark">
          <span className="nv-dot" aria-hidden="true">
            NV
          </span>
          <div>
            <b>NanoVox</b>
            <span>Account signals</span>
          </div>
        </div>

        <nav aria-label="Screens">
          {NAV_ITEMS.map((item) => (
            <NavLink key={item.to} to={{ pathname: item.to, search }} className="nv-nav">
              {item.label}
              <small>{item.hint}</small>
            </NavLink>
          ))}
        </nav>

        <div className="nv-foot">
          <ThemeControl />
          {email === null ? null : (
            <div className="nv-session">
              <span className="nv-session-email">{email}</span>
              <button type="button" className="nv-session-logout" onClick={logout}>
                Sign out
              </button>
            </div>
          )}
        </div>
      </aside>

      <main className="nv-main">{children}</main>

      {/* One drawer for the whole app: evidence opened from any screen
          stacks in the same place rather than each screen owning one. */}
      <Drawer />
    </div>
  )
}
