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
  aiInsightsOpen,
  insightsContent,
  onToggleAIInsights,
  onCloseAIInsights,
}: {
  title: string
  children: ReactNode
  aiInsightsOpen: boolean
  insightsContent: ReactNode
  onToggleAIInsights: () => void
  onCloseAIInsights: () => void
}) {
  return (
    <div className={`nv2-shell${aiInsightsOpen ? ' nv2-insights-open' : ''}`}>
      <aside className="nv2-rail">
        <div className="nv2-brand">
          <span className="nv2-brandmark" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
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
            {/* Static for this first page: no query below is filtered by a
                period yet, so a working dropdown would narrow nothing. */}
            <span className="nv2-period" title="Not yet wired to a filtered query">
              Last 30 days
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <path d="M6 9l6 6 6-6" strokeLinecap="round" strokeLinejoin="round" />
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
