/**
 * `/v2/overview` — the designer's new "Overview" perspective.
 *
 * The first of several planned v2 pages (chat, 2026-10-12): a complete
 * restyle of the executive view, built additively beside the seven existing
 * screens rather than replacing `/exec` — see `App.tsx` for how the two
 * trees coexist, and `OverviewLayout` for why this does not reuse `Shell`.
 *
 * ## No filter bar, no scope line
 *
 * The mockup carries neither, so every query below is called unfiltered
 * (`''`) instead of through `useFilters`. "Last 30 days" is drawn as a
 * static label in `OverviewLayout` until a later page decides what it
 * narrows.
 *
 * ## Every number here is a real query, never invented
 *
 * The mockup's own wording sometimes has no backend match at that exact
 * grain, and each of those is relabelled to what the corpus actually
 * supports rather than quietly supplying the mockup's exact words over a
 * number that does not mean them:
 *
 * - "N unresolved interactions" per account does not exist; the panel shows
 *   `conditionsMet` instead — how many of the ten indicator families fired —
 *   the same figure `/exec`'s own attention panel already reads.
 * - "Renewal in N days" is `monthsToRenewal`, which the corpus carries in
 *   whole months.
 * - The donut's five illustrative category names ("Billing disputes",
 *   "Provider issues", …) are not a grouping anything computes. The ring
 *   instead breaks calls down by the ten indicator families `/risk` already
 *   ranks — the book's real "what is driving risk" answer — with the
 *   smallest folded into "Others" per the dataviz skill's rule against a
 *   ninth hand-picked hue.
 * - Each emerging issue's "+12%" is a share `domain/aggregation/trends.py`
 *   deliberately never computes ("a percentage would imply a precision the
 *   corpus cannot support"); this shows the real call count instead.
 */

import { Link } from 'react-router-dom'
import { useState } from 'react'

import { laneColors } from '@/app/screens/actions/format'
import { OverviewLayout } from '@/app/v2/OverviewLayout'
import { useActionBoard } from '@/shared/api/actionBoard'
import type { ActionBoard } from '@/shared/api/actionBoard'
import { useCalls, useExec, useFilterOptions, useGeneratedInsights, useRisk } from '@/shared/api/insights'
import type { ExecScorecard, RiskScreen as RiskScreenData } from '@/shared/api/insights'
import { Donut } from '@/shared/design/charts'
import type { DonutSlice } from '@/shared/design/charts'
import { Empty, Skeleton, SkeletonBlock, SkeletonTiles } from '@/shared/design/primitives'
import { InsightLenses } from '@/shared/insights/Insights'
import '@/shared/screens/screen.css'
import '@/app/v2/overview.css'

type AssessedAccount = RiskScreenData['assessed'][number]
type EmergingEntry = ExecScorecard['trends']['emerging'][number]
type Driver = NonNullable<RiskScreenData['drivers']>[number]

/** Matches `/exec`'s own bar for "emerging" — see `ExecScreen.tsx`'s own
 * note on why five is a threshold rather than a fixed row count. */
const MIN_RISE = 5

/** The mockup's risk-driver palette: red, brand blue, then two lighter blues. */
const DRIVER_COLORS = ['#c9143f', '#1b4f98', '#7f96b7', '#c2d3e8']

export function OverviewScreen() {
  const [aiInsightsOpen, setAiInsightsOpen] = useState(false)
  const options = useFilterOptions('')
  const exec = useExec('')
  const risk = useRisk('')
  const board = useActionBoard('')
  // The one query this page makes that no other v2 panel needs, purely for
  // `unresolvedCount` — the only honest corpus-wide reading of the mockup's
  // "Unresolved interactions" tile (`CallsPageResponse`'s own docstring:
  // "over every matching call, not only the page shown").
  const calls = useCalls('')
  const aiInsights = useGeneratedInsights('exec', '', undefined, { enabled: aiInsightsOpen })

  const insightsContent = aiInsights.isPending ? (
    <p className="nv2-insights-state">Generating insights…</p>
  ) : aiInsights.error ? (
    <p className="nv2-insights-state" role="alert">AI insights could not be loaded.</p>
  ) : aiInsights.data?.status.code === 'UNAVAILABLE' ? (
    <p className="nv2-insights-state">
      Insights are unavailable: {aiInsights.data.reason?.label ?? 'no reason provided'}.
    </p>
  ) : aiInsights.data?.insights.length ? (
    <InsightLenses data={aiInsights.data} />
  ) : (
    <p className="nv2-insights-state">No insights were generated for this overview.</p>
  )

  const error = options.error ?? exec.error ?? risk.error ?? board.error ?? calls.error
  const ready =
    options.data !== undefined &&
    exec.data !== undefined &&
    risk.data !== undefined &&
    board.data !== undefined &&
    calls.data !== undefined

  return (
    <OverviewLayout
      title="Overview"
      aiInsightsOpen={aiInsightsOpen}
      insightsContent={insightsContent}
      onToggleAIInsights={() => setAiInsightsOpen((open) => !open)}
      onCloseAIInsights={() => setAiInsightsOpen(false)}
    >
      {error !== null ? (
        <div className="nv-screenstate" role="alert">
          <b>This screen could not be loaded.</b>
          <p>{error instanceof Error ? error.message : `Unexpected ${typeof error} thrown.`}</p>
        </div>
      ) : !ready ? (
        <OverviewSkeleton />
      ) : (
        <OverviewBody
          totalAccounts={options.data.employers.length}
          names={new Map(options.data.employers.map((employer) => [employer.ref, employer.name]))}
          trends={exec.data.trends}
          risk={risk.data}
          board={board.data}
          unresolvedCalls={calls.data.unresolvedCount}
        />
      )}
    </OverviewLayout>
  )
}

function OverviewSkeleton() {
  return (
    <Skeleton>
      <SkeletonTiles count={4} />
      <div className="nv-grid nv2-row">
        <div className="nv-c8">
          <SkeletonBlock lines={5} />
        </div>
        <div className="nv-c4">
          <SkeletonBlock lines={5} />
        </div>
        <div className="nv-c6">
          <SkeletonBlock lines={5} />
        </div>
        <div className="nv-c6">
          <SkeletonBlock lines={5} />
        </div>
      </div>
    </Skeleton>
  )
}

function OverviewBody({
  totalAccounts,
  names,
  trends,
  risk,
  board,
  unresolvedCalls,
}: {
  totalAccounts: number
  names: Map<string, string>
  trends: ExecScorecard['trends']
  risk: RiskScreenData
  board: ActionBoard
  unresolvedCalls: number
}) {
  const flagged = risk.assessed.filter((account) => account.flagged)
  const openActions = board.actions.filter(
    (action) => board.lanes.find((lane) => lane.code === action.status)?.open ?? false,
  )

  return (
    <>
      <div className="nv2-stats">
        <StatTile label="Total accounts" value={totalAccounts} />
        <StatTile label="Flagged accounts" value={flagged.length} />
        <StatTile label="Unresolved interactions" value={unresolvedCalls} />
        <StatTile label="Open actions" value={openActions.length} />
      </div>

      <div className="nv-grid nv2-row">
        <div className="nv-c8">
          <AttentionPanel flagged={flagged} names={names} />
        </div>
        <div className="nv-c4">
          <DriversPanel drivers={risk.drivers ?? []} totalAccounts={totalAccounts} />
        </div>
      </div>

      <div className="nv-grid nv2-row">
        <div className="nv-c6">
          <RecentActionsPanel board={board} names={names} />
        </div>
        <div className="nv-c6">
          <EmergingPanel emerging={trends.emerging} />
        </div>
      </div>
    </>
  )
}

function StatTile({ label, value }: { label: string; value: number }) {
  return (
    <div className="nv2-stat">
      <span className="nv2-stat-value">{value}</span>
      <span className="nv2-stat-label">{label}</span>
    </div>
  )
}

/**
 * "Accounts that need attention" — the same flagged accounts, the same
 * renewal-first ordering, as `/exec`'s own `NeedsAttentionPanel`. Five
 * rather than six, matching the mockup's row count.
 */
function AttentionPanel({ flagged, names }: { flagged: AssessedAccount[]; names: Map<string, string> }) {
  const top = [...flagged]
    .sort(
      (a, b) =>
        monthsOrLast(a) - monthsOrLast(b) ||
        indicatorCount(b) - indicatorCount(a) ||
        a.employerRef.localeCompare(b.employerRef),
    )
    .slice(0, 5)

  return (
    <section className="nv2-panel">
      <header className="nv2-panel-head">
        <h2>Accounts that need attention</h2>
        <Link to="/accounts">View all accounts</Link>
      </header>
      {top.length === 0 ? (
        <Empty title="Nothing flagged">No account meets metric 10's flag.</Empty>
      ) : (
        <ul className="nv2-attn" aria-label="Flagged accounts">
          {top.map((account) => {
            const name = names.get(account.employerRef) ?? account.employerRef
            const count = indicatorCount(account)
            return (
              <li key={account.employerRef}>
                <span className="nv2-avatar-sm" aria-hidden="true">
                  {avatarInitials(name)}
                </span>
                <span className="nv2-attn-main">
                  <b>{name}</b>
                  <small>
                    {count} indicator{count === 1 ? '' : 's'} flagged
                  </small>
                </span>
                <span className="nv2-flagged">Flagged</span>
                <Renewal account={account} />
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}

function indicatorCount(account: AssessedAccount): number {
  return account.observations.filter((observation) => observation.observed).length
}

function monthsOrLast(account: AssessedAccount): number {
  const months = account.monthsToRenewal
  return months === null || months === undefined ? 99 : months
}

/** The mockup's two-line "Renewal in / 42 days" treatment, over the
 * corpus's own grain: whole months, never days. */
function Renewal({ account }: { account: AssessedAccount }) {
  const months = account.monthsToRenewal
  if (months === null || months === undefined) {
    return (
      <span className="nv2-renewal">
        <b>{account.renewalMonth ?? 'Renewal unknown'}</b>
      </span>
    )
  }
  return (
    <span className="nv2-renewal">
      <small>Renewal in</small>
      <b>
        {months} {months === 1 ? 'month' : 'months'}
      </b>
    </span>
  )
}

function avatarInitials(name: string): string {
  const letters = name
    .split(' ')
    .map((part) => part[0])
    .filter((letter): letter is string => letter !== undefined)
    .join('')
  return (letters.slice(0, 2) || '–').toUpperCase()
}

/**
 * "Risk Overview" — the ten indicator families `/risk` already ranks,
 * not the mockup's illustrative categories (no aggregation groups calls by
 * `Category` into a ranked breakdown). Top four keep their own hue; the
 * rest fold into one "Others" slice, the dataviz skill's rule for a series
 * beyond a fixed categorical order.
 */
function DriversPanel({ drivers, totalAccounts }: { drivers: Driver[]; totalAccounts: number }) {
  const available = [...drivers].filter((driver) => driver.available).sort((a, b) => b.calls - a.calls)
  const top = available.slice(0, 4)
  const rest = available.slice(4)
  const othersCalls = rest.reduce((sum, driver) => sum + driver.calls, 0)

  const slices: DonutSlice[] = top.map((driver, index) => ({
    key: driver.code,
    value: driver.calls,
    color: DRIVER_COLORS[index] ?? '#e9edf3',
  }))
  if (rest.length > 0) {
    slices.push({ key: 'others', value: othersCalls, color: '#e9edf3' })
  }

  return (
    <section className="nv2-panel">
      <header className="nv2-panel-head">
        <h2>Risk Overview</h2>
        <Link to="/risk">View all</Link>
      </header>
      {available.length === 0 ? (
        <Empty title="Nothing to drive">No indicator family fired in this scope.</Empty>
      ) : (
        <div className="nv2-donutwrap">
          <Donut
            slices={slices}
            centerValue={String(totalAccounts)}
            centerLabel="Accounts"
            ariaLabel="Calls by indicator family, the ten drivers behind the risk flag"
            rounded={false}
          />
          <ul className="nv2-legend">
            {top.map((driver, index) => (
              <li key={driver.code}>
                <i style={{ background: DRIVER_COLORS[index] ?? '#e9edf3' }} />
                <span>{driver.label}</span>
                <b>{driver.calls}</b>
              </li>
            ))}
            {rest.length > 0 ? (
              <li>
                <i style={{ background: '#e9edf3' }} />
                <span>Others ({rest.length} families)</span>
                <b>{othersCalls}</b>
              </li>
            ) : null}
          </ul>
        </div>
      )}
    </section>
  )
}

/** "Recent actions" — the board's own newest-first order, five rows, each
 * coloured by the lifecycle lane it actually sits in (`laneColors`, the
 * same rule `/exec`'s action bar and `/actions` both use). */
function RecentActionsPanel({ board, names }: { board: ActionBoard; names: Map<string, string> }) {
  const colors = laneColors(board.lanes)
  const top = board.actions.slice(0, 5)

  return (
    <section className="nv2-panel">
      <header className="nv2-panel-head">
        <h2>Recent actions</h2>
        <Link to="/actions">View all actions</Link>
      </header>
      {top.length === 0 ? (
        <Empty title="Nothing raised">No action has been raised on this board yet.</Empty>
      ) : (
        <ul className="nv2-actions">
          {top.map((action) => (
            <li key={action.id}>
              <span className="nv2-action-main">
                <b>{action.label ?? action.title}</b>
                <small>
                  {action.employerRef !== null
                    ? (names.get(action.employerRef) ?? action.employerRef)
                    : 'Not scoped to one account'}
                </small>
              </span>
              <StatusChip label={action.statusLabel} color={colors.get(action.status) ?? 'var(--ink-3)'} />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

/** A lane's own colour (`laneColors`, server-driven — never a hardcoded
 * lane table), rendered as a pastel fill rather than a solid one to match
 * the mockup's chip style. `color-mix` over the lane's single colour, not a
 * second palette: the hue is still the one `/exec`'s action bar uses. */
function StatusChip({ label, color }: { label: string; color: string }) {
  return (
    <span className="nv2-pill" style={{ background: `color-mix(in srgb, ${color} 16%, white)`, color }}>
      {label}
    </span>
  )
}

/**
 * "Emerging issues" — `/exec`'s own rising-beyond-noise filter
 * (`MIN_RISE = 5`), five rows. Each row's call count stands in for the
 * mockup's percentage, which `domain/aggregation/trends.py` refuses to
 * compute at this volume.
 */
function EmergingPanel({ emerging }: { emerging: EmergingEntry[] }) {
  const rising = emerging
    .filter((item) => item.rising && item.delta >= MIN_RISE)
    .sort((a, b) => b.delta - a.delta)
    .slice(0, 5)

  return (
    <section className="nv2-panel">
      <header className="nv2-panel-head">
        <h2>Emerging issues</h2>
        <Link to="/risk">View all</Link>
      </header>
      {rising.length === 0 ? (
        <Empty title="Nothing rising">{`No tracked item gained ${String(MIN_RISE)} or more calls across the window.`}</Empty>
      ) : (
        <ul className="nv2-emerging">
          {rising.map((item) => (
            <li key={`${item.kind}:${item.key}`}>
              <span className="nv2-emerging-main">
                <b>{item.label}</b>
                <small>{item.kind}</small>
              </span>
              <span className="nv2-worse">+{item.delta} calls</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
