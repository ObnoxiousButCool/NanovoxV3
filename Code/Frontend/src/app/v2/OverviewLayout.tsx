/**
 * The v2 shell for the designer's new "Overview" perspective.
 *
 * Deliberately separate from `shared/design/Shell.tsx`: that rail carries
 * the seven questions the existing screens answer, plus the shared filter
 * bar every one of them reads from the URL. The designer's mockup has
 * neither — a different rail, no filter bar, its own top bar — so reusing
 * `Shell` would mean bending one frame to serve two designs badly rather
 * than building the second one. The old screens keep `Shell` under
 * `LegacyApp` in `App.tsx`; this is additive, not a replacement.
 */

import { NavLink } from 'react-router-dom'
import type { ReactNode } from 'react'

import { NavIcon } from '@/app/v2/navIcons'
import type { NavIconName } from '@/app/v2/navIcons'
import { PERIOD_PRESETS } from '@/app/v2/periods'
import '@/app/v2/overview.css'

interface V2NavItem {
  to: string
  label: string
  icon: NavIconName
  /**
   * Whether this screen exists yet. The mockup's rail names seven; only
   * Overview is built. The rest are drawn in place rather than dropped —
   * removing them would be exactly the "missing" the brief ruled out — but
   * rendered unclickable rather than linked to a page that is not there.
   */
  live: boolean
}

const NAV_ITEMS: readonly V2NavItem[] = [
  { to: '/v2/overview', label: 'Overview', icon: 'overview', live: true },
  { to: '/v2/accounts-risk', label: 'Accounts & Risk', icon: 'accounts', live: false },
  { to: '/v2/actions', label: 'Actions', icon: 'actions', live: false },
  { to: '/v2/calls-quality', label: 'Calls & Quality', icon: 'calls', live: false },
  { to: '/v2/agents', label: 'Agents', icon: 'agents', live: false },
  { to: '/v2/brokers', label: 'Brokers', icon: 'brokers', live: false },
  { to: '/v2/emerging-issues', label: 'Emerging Issues', icon: 'emerging', live: false },
]

export function OverviewLayout({
  title,
  children,
  period,
  onPeriodChange,
  aiInsightsOpen,
  insightsContent,
  onToggleAIInsights,
  onCloseAIInsights,
}: {
  title: string
  children: ReactNode
  /** The selected preset's key (`periods.ts`). */
  period: string
  onPeriodChange: (key: string) => void
  aiInsightsOpen: boolean
  insightsContent: ReactNode
  onToggleAIInsights: () => void
  onCloseAIInsights: () => void
}) {
  return (
    <div className={`nv2-shell${aiInsightsOpen ? ' nv2-insights-open' : ''}`}>
      <aside className="nv2-rail">
        <div className="nv2-brand">
          <svg className="nv2-brandmark" width="23" height="20" viewBox="0 0 23 20" fill="none" aria-hidden="true">
            <rect y="6" width="3.5" height="14" rx="1.75" fill="#2563EB" />
            <rect x="6.5" width="3.5" height="20" rx="1.75" fill="#2563EB" />
            <rect x="13" y="10" width="3.5" height="10" rx="1.75" fill="#2563EB" />
            <rect x="19.5" y="4" width="3.5" height="16" rx="1.75" fill="#2563EB" />
          </svg>
          <b>NanoVox</b>
        </div>

        <nav aria-label="Screens" className="nv2-nav">
          {NAV_ITEMS.map((item) =>
            item.live ? (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => `nv2-navitem${isActive ? ' nv2-active' : ''}`}
              >
                <NavIcon name={item.icon} />
                {item.label}
              </NavLink>
            ) : (
              // Not yet built. `aria-disabled` rather than omitting the
              // entry, so a screen reader hears what the sighted mockup
              // shows: seven names, one of them live.
              <span key={item.to} className="nv2-navitem nv2-navitem-soon" aria-disabled="true">
                <NavIcon name={item.icon} />
                {item.label}
              </span>
            ),
          )}
        </nav>

        <div className="nv2-profile">
          <span className="nv2-avatar" aria-hidden="true">
            SK
          </span>
          <div>
            <b>First name</b>
            <span>Portfolio Manager</span>
          </div>
        </div>
      </aside>

      <div className="nv2-main">
        <header className="nv2-topbar">
          <h1>{title}</h1>
          <div className="nv2-topbar-actions">
            <span className="nv2-period">
              <select
                aria-label="Period"
                value={period}
                onChange={(event) => {
                  onPeriodChange(event.target.value)
                }}
              >
                {PERIOD_PRESETS.map((preset) => (
                  <option key={preset.key} value={preset.key}>
                    {preset.label}
                  </option>
                ))}
              </select>
              <svg width="24" height="24" viewBox="0 0 24 24" fill="#64748B" aria-hidden="true">
                <g transform="translate(-113 -9)">
                  <path d="M125 21.9462L129.073 17.873C129.211 17.7347 129.386 17.6638 129.595 17.6605C129.805 17.6573 129.982 17.7282 130.127 17.873C130.272 18.018 130.344 18.1937 130.344 18.4C130.344 18.6063 130.272 18.782 130.127 18.927L125.633 23.4212C125.539 23.5147 125.44 23.5808 125.336 23.6193C125.233 23.6578 125.12 23.677 125 23.677C124.879 23.677 124.767 23.6578 124.663 23.6193C124.56 23.5808 124.461 23.5147 124.367 23.4212L119.873 18.927C119.735 18.7885 119.664 18.6144 119.660 18.4048C119.657 18.1953 119.728 18.018 119.873 17.873C120.018 17.7282 120.194 17.6558 120.4 17.6558C120.606 17.6558 120.782 17.7282 120.927 17.873L125 21.9462Z" />
                </g>
              </svg>
            </span>
            <button
              type="button"
              className="nv2-ai-btn"
              aria-expanded={aiInsightsOpen}
              aria-controls="nv2-insights-panel"
              onClick={onToggleAIInsights}
            >
              AI Insights
            </button>
          </div>
        </header>
        <div className="nv2-body">{children}</div>
        {aiInsightsOpen ? (
          <aside className="nv2-insights-drawer" id="nv2-insights-panel" aria-label="AI Insights">
            <header className="nv2-insights-head">
              <h2>AI Insights</h2>
              <button type="button" aria-label="Close AI insights" onClick={onCloseAIInsights}>
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="m6 6 12 12M18 6 6 18" />
                </svg>
              </button>
            </header>
            <div className="nv2-insights-content">{insightsContent}</div>
          </aside>
        ) : null}
      </div>
    </div>
  )
}
