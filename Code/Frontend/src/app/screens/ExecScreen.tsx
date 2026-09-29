/**
 * `/exec` — the executive scorecard.
 *
 * Follows the v2 prototype's order: needs-attention, the headline counts, a
 * risk-and-follow-through summary row, what moved and what emerged, then
 * what is being done about it. The prototype's four "lenses" are still
 * absent — they are a grouping of figures, not of sentences, and grouping
 * them by hand here would be the invented taxonomy §2A.4 forbids until U1's
 * four are wired through.
 *
 * ## Three queries, one screen
 *
 * The prototype computes "needs attention", the flagged-accounts tiles and
 * the action-status bar from the same in-browser corpus everything else
 * reads. Here those numbers live behind two other endpoints — `/insights/risk`
 * and `/insights/actions/board` — so this screen combines `useExec` with
 * `useRisk` and `useActionBoard` the way `ActionsScreen` already combines
 * `useActionsFindings` with `useActionBoard`: one `isPending`/`error` across
 * all three, and the body waits for all of them rather than rendering the
 * scorecard while the risk panel is still a spinner.
 *
 * ## The insights load separately, and may never arrive
 *
 * `useGeneratedInsights` is its own query. The figures are the page and
 * must never wait on a model; when there is no model the strip renders an
 * explicit unavailable state (U2) and everything below it is unaffected.
 *
 * ## Movement is shown with its noise test, not instead of it
 *
 * `trends.movements` carries `beyondNoise` and the expected value the test
 * compared against. Both reach the screen. At about eight calls a week a
 * move from two to four is a coin flip, and a screen that rendered it as
 * "+100%" would be manufacturing a finding — so a movement inside the noise
 * says so in words rather than being hidden, which would be its own kind of
 * lie about what the data contains.
 *
 * ## Null weeks are gaps
 *
 * `WeekResponse.calls` is null for a week the corpus is silent about, and
 * `VLine` draws null as a break in the line. Plotting zero would assert
 * that nobody called that week, which is a different and much stronger
 * claim than "we have nothing for that week".
 *
 * ## Emerging is curated, not dumped
 *
 * `trends.emerging` carries every category, touchpoint, signal and product
 * line the window tracked — around a hundred rows at batch-1 volume, most
 * of them flat. The prototype's own screen never lists them all: it shows
 * the three rising fastest as cards with their own chart, and the ones
 * falling as a compact "Easing" sidebar. Filtering happens here, in the
 * screen, rather than the server choosing three for us — the server's job
 * is to say what is true of all of them, and which three matter is this
 * page's editorial choice, the same one the prototype makes in `exec.html`.
 */

import { Link } from 'react-router-dom'

import { useActionBoard } from '@/shared/api/actionBoard'
import type { ActionBoard } from '@/shared/api/actionBoard'
import { useExec, useFilterOptions, useGeneratedInsights, useRisk } from '@/shared/api/insights'
import type { ExecScorecard, RiskScreen as RiskScreenData } from '@/shared/api/insights'
import { useFilters } from '@/shared/filters/useFilters'
import { Screen } from '@/shared/screens/Screen'
import { InsightLenses, InsightStrip } from '@/shared/insights/Insights'
import { IssueCue } from '@/shared/actions/IssueLink'
import { RENEW_SOON_MONTHS } from '@/shared/actions/issueHref'
import { Gauge, MiniBars, VLine } from '@/shared/design/charts'
import { findLane } from '@/app/screens/actions/lifecycle'
import { laneColors } from '@/app/screens/actions/format'
import '@/app/screens/actions/actionsBoard.css'
import '@/app/screens/exec.css'
import {
  BigRow,
  Empty,
  EpistemicChip,
  FigureSample,
  FigureValue,
  KpiTile,
  Note,
  Panel,
  SampleFallback,
  basisFromApi,
} from '@/shared/design/primitives'
import type { Figure } from '@/shared/design/primitives'

const percent = (value: number) => `${String(Math.round(value * 100))}%`

type AssessedAccount = RiskScreenData['assessed'][number]
type MovementEntry = ExecScorecard['trends']['movements'][number]
type EmergingEntry = ExecScorecard['trends']['emerging'][number]

/** A figure's chip, or nothing when it names no origin (D13). */
function BasisChip({ figure }: { figure: Figure }) {
  const kind = basisFromApi(figure.basis?.code)
  return kind === null ? null : <EpistemicChip kind={kind} />
}

export function ExecScreen() {
  const filters = useFilters()
  const { data, isPending, error } = useExec(filters.apiSearch)
  const risk = useRisk(filters.apiSearch)
  const board = useActionBoard()
  // The same query the filter bar already made, so React Query serves it
  // from cache. An employer reference is a code, and the needs-attention
  // panel names accounts — codes never reach a reader.
  const options = useFilterOptions(filters.apiSearch)
  const insights = useGeneratedInsights('exec', filters.apiSearch)

  const names = new Map(
    (options.data?.employers ?? []).map((employer) => [employer.ref, employer.name]),
  )

  return (
    <Screen
      title="Executive overview"
      lede="What the calls in scope say, with every figure carrying its sample and its origin."
      scope={data?.scope}
      isPending={isPending || risk.isPending || board.isPending}
      error={error ?? risk.error ?? board.error}
    >
      <InsightStrip data={insights.data} />
      {data === undefined || risk.data === undefined || board.data === undefined ? null : (
        <ExecBody data={data} risk={risk.data} board={board.data} names={names} />
      )}
      {/* The prototype puts the grid below the figures it reads, which
          is also the order that keeps the numbers first on the page. */}
      <InsightLenses data={insights.data} />
    </Screen>
  )
}

function ExecBody({
  data,
  risk,
  board,
  names,
}: {
  data: ExecScorecard
  risk: RiskScreenData
  board: ActionBoard
  names: Map<string, string>
}) {
  const { trends } = data

  return (
    <div className="nv-withai">
      <div className="nv-feedcol">
        <NeedsAttentionPanel risk={risk} names={names} />
      </div>
      <div className="nv-maincol nv-grid">
      <div className="nv-c12">
        <Panel
          title="The window"
          sub={`${String(data.calls)} calls in scope, as at ${data.asOf}.`}
        >
          <BigRow>
            {data.metrics.map((metric) => (
              <KpiTile
                key={metric.key}
                label={metric.name}
                value={<FigureValue figure={metric.figure} format={percent} />}
                meta={
                  <>
                    <FigureSample figure={metric.figure} />
                    {/* Each metric's own window, from `dashboard.yaml`. Two
                        metrics on one row can be 4 weeks and 12 weeks (D11),
                        and a reader comparing them needs to know which. */}
                    {metric.windowWeeks === null || metric.windowWeeks === undefined ? null : (
                      <span className="nv-indcount"> · {metric.windowWeeks}wk</span>
                    )}
                  </>
                }
              />
            ))}
          </BigRow>
        </Panel>
      </div>

      <div className="nv-c12">
        <SummaryTilesPanel data={data} risk={risk} board={board} />
      </div>

      <WellAndConcernPanels movements={trends.movements} windowWeeks={trends.windowWeeks} concern={data.areaOfConcern ?? null} />

      <div className="nv-c6">
        <Panel
          title="What moved"
          sub={`Against ${trends.priorStart} to ${trends.priorEnd}.`}
          chip={<EpistemicChip kind="observed" />}
        >
          {trends.movements.length === 0 ? (
            <Empty>No measure had both a current and a prior period to compare.</Empty>
          ) : (
            <ul className="nv-movements">
              {trends.movements.map((movement) => (
                <li key={movement.label} className={movement.beyondNoise ? 'nv-real' : 'nv-noise'}>
                  <b>{movement.label}</b>
                  <span className="nv-indcount">
                    {movement.prior} → {movement.now}
                  </span>
                  {movement.beyondNoise ? (
                    <span className={movement.worse ? 'nv-worse' : 'nv-better'}>
                      {movement.worse ? 'worse' : 'better'}
                    </span>
                  ) : (
                    // Said, not hidden. Call volume moved too, and the
                    // expected value is what the reader needs to see the
                    // difference is the volume rather than the behaviour.
                    <span className="nv-noise-tag">
                      within noise — {movement.callsPrior} calls then,{' '}
                      {movement.callsNow} now, so about {Math.round(movement.expected)} was
                      expected
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <div className="nv-c6">
        <Panel
          title="Routed to the right place"
          chip={<BasisChip figure={data.intentRouted} />}
        >
          <BigRow>
            <KpiTile
              label="Intent routed"
              value={<FigureValue figure={data.intentRouted} format={percent} />}
              meta={<FigureSample figure={data.intentRouted} />}
            />
          </BigRow>
        </Panel>
      </div>

      <div className="nv-c12">
        <Panel
          title="Calls by week"
          sub="A blank week is a week the corpus says nothing about, not a week of no calls."
          chip={<EpistemicChip kind="observed" />}
        >
          <VLine
            ariaLabel="Calls per week across the window"
            labels={trends.weeks.map((week) => week.start.slice(5))}
            series={[
              {
                name: 'Calls',
                values: trends.weeks.map((week) => week.calls ?? null),
                color: 'var(--seq-2)',
              },
            ]}
          />
        </Panel>
      </div>

      <div className="nv-c12">
        <EmergingPanel emerging={trends.emerging} />
      </div>

      <div className="nv-c12">
        <ActionProgressPanel board={board} />
      </div>
      </div>
    </div>
  )
}

/**
 * "Needs attention now" — the account-risk panel the prototype leads with.
 *
 * `risk.assessed` arrives most-indicators-first, then soonest-renewal (D12).
 * Filtering to the flagged accounts preserves that order; nothing here
 * re-sorts it.
 */
function NeedsAttentionPanel({
  risk,
  names,
}: {
  risk: RiskScreenData
  names: Map<string, string>
}) {
  const flagged = risk.assessed.filter((account) => account.flagged)
  const renewingSoon = flagged.filter((account) => withinRenewSoon(account))
  const top = flagged.slice(0, 5)

  return (
    <Panel
      title="Needs attention now"
      sub={
        <>
          {flagged.length} of {risk.assessedCount} accounts are flagged for risk, and{' '}
          {renewingSoon.length} of them renew within {RENEW_SOON_MONTHS} months.
        </>
      }
      chip={<EpistemicChip kind="observed" />}
      actions={
        <>
          {flagged.length > 0 ? <IssueCue issue="flagged" /> : null}
          <Link className="nv-btn" to="/risk">
            Show in overview
          </Link>
        </>
      }
    >
      {top.length === 0 ? (
        <Empty title="Nothing flagged">No account meets metric 10's flag in this scope.</Empty>
      ) : (
        <ul className="nv-attn">
          {top.map((account) => (
            <li key={account.employerRef}>
              <Link to={`/accounts/${encodeURIComponent(account.employerRef)}`}>
                <span
                  className="nv-dot"
                  style={{ background: withinRenewSoon(account) ? 'var(--critical)' : 'var(--serious)' }}
                />
                <span>
                  <b>{names.get(account.employerRef) ?? account.employerRef}</b>
                  <small>{indicatorCount(account)} of 10 indicators</small>
                </span>
                <span className="nv-n">{indicatorCount(account)}</span>
                <span className="nv-own">{renewalText(account)}</span>
                <span className="nv-go" aria-hidden="true">
                  →
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}

function indicatorCount(account: AssessedAccount): number {
  return account.observations.filter((observation) => observation.observed).length
}

function withinRenewSoon(account: AssessedAccount): boolean {
  const months = account.monthsToRenewal
  return months !== null && months !== undefined && months <= RENEW_SOON_MONTHS
}

function renewalText(account: AssessedAccount): string {
  const months = account.monthsToRenewal
  if (months === null || months === undefined) {
    return account.renewalMonth ?? 'renewal unknown'
  }
  return `renews in ${String(months)} ${months === 1 ? 'month' : 'months'}`
}

/**
 * The four-tile row: accounts flagged, flagged-and-renewing-soon, escalation
 * integrity as a gauge, and overdue actions.
 */
function SummaryTilesPanel({
  data,
  risk,
  board,
}: {
  data: ExecScorecard
  risk: RiskScreenData
  board: ActionBoard
}) {
  const flagged = risk.assessed.filter((account) => account.flagged)
  const renewingSoon = flagged.filter((account) => withinRenewSoon(account))
  const openActions = board.actions.filter((action) => findLane(board.lanes, action.status)?.open)
  const overdue = board.actions.filter((action) => action.pastDue)

  const integrity = data.escalation.find((entry) => entry.label.startsWith('Handled'))
  const integrityFigure = integrity?.figure
  const triggered = integrityFigure?.n ?? 0
  const integrityValue = integrityFigure?.value
  const published =
    integrityFigure?.published === true && integrityValue !== null && integrityValue !== undefined
  const handled = published ? Math.round(integrityValue * triggered) : null
  const gaugeValue = handled === null ? null : Math.round((handled / Math.max(triggered, 1)) * 100)
  const missed = handled === null ? 0 : triggered - handled

  return (
    <Panel
      title="Risk and follow-through, at a glance"
      chip={<EpistemicChip kind="observed" />}
    >
      <BigRow>
        <KpiTile
          label="Accounts flagged"
          tone={flagged.length > 0 ? 'warm' : 'plain'}
          value={String(flagged.length)}
          meta={
            <>
              <span className="nv-indcount">
                <FigureValue figure={risk.flaggedShare} format={percent} /> of{' '}
                {risk.assessedCount} assessed · {risk.exposure.lives} lives
              </span>
              {flagged.length > 0 ? <IssueCue issue="flagged" /> : null}
            </>
          }
        />
        <KpiTile
          label="Flagged & renewing soon"
          tone={renewingSoon.length > 0 ? 'hot' : 'plain'}
          value={String(renewingSoon.length)}
          meta={
            <>
              <span className="nv-indcount">renewal within {RENEW_SOON_MONTHS} months</span>
              {renewingSoon.length > 0 ? <IssueCue issue="renew_soon" /> : null}
            </>
          }
        />
        <div className={`nv-big nv-gaugetile${missed > 0 ? ' nv-hot' : ''}`}>
          <span className="nv-k">Escalation integrity</span>
          <Gauge
            value={gaugeValue}
            label={gaugeValue === null ? '–' : `${String(gaugeValue)}%`}
            ariaLabel="Escalations handled, of escalations that were warranted"
          />
          <span className="nv-m">
            {handled === null
              ? 'Too few escalations to publish a rate'
              : `${String(handled)} of ${String(triggered)} handled`}
          </span>
          {missed > 0 ? <IssueCue issue="escalation_missed" /> : null}
        </div>
        <KpiTile
          label="Overdue actions"
          tone={overdue.length > 0 ? 'hot' : 'plain'}
          value={String(overdue.length)}
          meta={
            <>
              <span className="nv-indcount">
                {openActions.length} of {board.actions.length} still open
              </span>
              {overdue.length > 0 ? <IssueCue issue="overdue" /> : null}
            </>
          }
        />
      </BigRow>
    </Panel>
  )
}

/**
 * "What went well" / "Area of concern" — two short, computed observations.
 *
 * Deliberately not generated: the prototype's screenshot carries no AI badge
 * on this pair, and §2A.4 forbids narrating a finding nobody computed.
 * "What went well" reads the biggest improvement already in `trends.movements`
 * that beat noise, needing no new backend aggregation. "Area of concern"
 * reads `areaOfConcern`, the one figure movements cannot already answer — see
 * `domain/aggregation/concern.py` for why a small backend addition was the
 * right call there.
 */
function WellAndConcernPanels({
  movements,
  windowWeeks,
  concern,
}: {
  movements: MovementEntry[]
  windowWeeks: number
  concern: ExecScorecard['areaOfConcern']
}) {
  const best = bestImprovement(movements)

  return (
    <>
      <div className="nv-c6">
        <Panel title="What went well" chip={<EpistemicChip kind="derived" />}>
          {best === undefined ? (
            <Empty title="Nothing to report">
              No measure improved beyond noise in the last {windowWeeks} weeks.
            </Empty>
          ) : (
            <p>
              <b>{best.label}</b> fell from {best.prior} to {best.now} in the last{' '}
              {windowWeeks} weeks.
            </p>
          )}
        </Panel>
      </div>
      <div className="nv-c6">
        <Panel title="Area of concern" chip={<EpistemicChip kind="derived" />}>
          {concern === null || concern === undefined ? (
            <Empty title="Nothing to flag">
              No category carried an unresolved call in this scope.
            </Empty>
          ) : (
            <p>
              <b>{concern.category}</b> carries the most unresolved calls (
              {concern.unresolved}){' '}
              {concern.escalationsTriggered > concern.escalationsHandled
                ? `, and only ${String(concern.escalationsHandled)} of ${String(concern.escalationsTriggered)} escalations there were handled.`
                : '.'}
            </p>
          )}
        </Panel>
      </div>
    </>
  )
}

/** The measure that improved the most, relative to its own prior count —
 * the prototype's own `improving[0]`. `worse: false` and a real change are
 * both required: a flat measure with `worse: false` is not an improvement,
 * it is a measure that did not move. */
function bestImprovement(movements: MovementEntry[]): MovementEntry | undefined {
  const improving = movements.filter((movement) => !movement.worse && movement.now !== movement.prior)
  return improving.sort((a, b) => {
    const relativeA = Math.abs(a.prior - a.now) / Math.max(a.prior, 1)
    const relativeB = Math.abs(b.prior - b.now) / Math.max(b.prior, 1)
    return relativeB - relativeA
  })[0]
}

/**
 * Curated "Emerging issues" — the top three rising items as cards with their
 * own chart, and the falling items in an "Easing" sidebar. Replaces a flat
 * dump of every tracked category, touchpoint, signal and product line.
 */
function EmergingPanel({ emerging }: { emerging: EmergingEntry[] }) {
  const rising = emerging
    .filter((item) => item.rising)
    .sort((a, b) => b.delta - a.delta)
    .slice(0, 3)
  const easing = emerging
    .filter((item) => item.delta < 0)
    .sort((a, b) => a.delta - b.delta)
    .slice(0, 5)

  return (
    <Panel
      title="Emerging issues"
      sub="Topics, touchpoints, signals and product lines with more calls in the latest slice of the window than the first. Counts only: at batch-1 volume a share would be two or three calls."
      chip={<EpistemicChip kind="pattern" />}
    >
      <div className="nv-emgrid">
        <div>
          {rising.length === 0 ? (
            <Empty title="Nothing rising">No tracked item rose across this window.</Empty>
          ) : (
            rising.map((item) => <EmergingCard key={`${item.kind}:${item.key}`} item={item} />)
          )}
        </div>
        <aside className="nv-easing">
          <h3>Easing</h3>
          <p className="nv-sub">Fewer calls now than at the start of the window.</p>
          {easing.length === 0 ? (
            <Empty title="Nothing easing">Nothing fell across this window.</Empty>
          ) : (
            <ul>
              {easing.map((item) => (
                <li key={`${item.kind}:${item.key}`}>
                  <span>
                    <b>{item.key}</b>
                    <small>
                      {item.kind} · {item.buckets.map((bucket) => bucket.hits).join(' → ')}
                    </small>
                  </span>
                  <span className="nv-better">{item.delta}</span>
                </li>
              ))}
            </ul>
          )}
        </aside>
      </div>
    </Panel>
  )
}

function EmergingCard({ item }: { item: EmergingEntry }) {
  const first = item.buckets[0]?.hits ?? 0
  const last = item.buckets.at(-1)?.hits ?? 0
  return (
    <div className="nv-emrow">
      <div className="nv-emchart">
        <MiniBars
          values={item.buckets.map((bucket) => bucket.hits)}
          label={`${item.key} across the window: ${item.buckets.map((bucket) => bucket.hits).join(', ')}`}
        />
      </div>
      <div className="nv-emtext">
        <div className="nv-emtop">
          <b>{item.key}</b>
          <span className="nv-kind">{item.kind}</span>
          <span className="nv-worse">+{item.delta}</span>
        </div>
        <p>
          {first} → {last} across the window.
        </p>
      </div>
    </div>
  )
}

/**
 * "What is being done" — the action-status bar. Counts per lifecycle lane,
 * the same way `ActionBoardView`'s stage chips do: `board.actions.filter(a
 * => a.status === lane.code).length`, never a hardcoded lane list.
 */
function ActionProgressPanel({ board }: { board: ActionBoard }) {
  const colors = laneColors(board.lanes)
  const counts = new Map(
    board.lanes.map((lane) => [lane.code, board.actions.filter((action) => action.status === lane.code).length]),
  )
  const openActions = board.actions.filter((action) => findLane(board.lanes, action.status)?.open)
  const overdue = board.actions.filter((action) => action.pastDue)
  const measured = board.actions.filter((action) => action.outcome !== null)
  const hasActions = board.actions.length > 0

  // A believable spread across whatever lanes this board defines, shown
  // only inside `SampleFallback` when the board is genuinely empty — never
  // a claim about this account's own actions.
  const sampleSpread = [3, 2, 4, 1, 3, 2]
  const sampleCounts = new Map(board.lanes.map((lane, index) => [lane.code, sampleSpread[index % sampleSpread.length] ?? 1]))

  return (
    <Panel
      title="What is being done"
      sub={
        hasActions ? (
          <>
            {openActions.length} of {board.actions.length} actions open, {overdue.length} overdue,{' '}
            {measured.length} with a measured outcome.
          </>
        ) : (
          'No actions have been raised on this board yet.'
        )
      }
      chip={<EpistemicChip kind="observed" />}
    >
      {hasActions ? (
        <ActionBar lanes={board.lanes} counts={counts} colors={colors} />
      ) : (
        <SampleFallback>
          <ActionBar lanes={board.lanes} counts={sampleCounts} colors={colors} />
        </SampleFallback>
      )}
      <Note>{board.trustNote}</Note>
      <p className="nv-cta">
        <Link to="/actions">Open the action board →</Link>{' '}
        <Link to="/risk">See every risk and driver →</Link>
      </p>
    </Panel>
  )
}

/** The colored status bar plus its legend — the real counts, or, wrapped in
 * `SampleFallback` by the caller, an illustrative spread. */
function ActionBar({
  lanes,
  counts,
  colors,
}: {
  lanes: ActionBoard['lanes']
  counts: Map<string, number>
  colors: Map<string, string>
}) {
  return (
    <>
      <div className="nv-actionbar">
        {lanes.map((lane) => {
          const n = counts.get(lane.code) ?? 0
          if (n === 0) return null
          return (
            <span key={lane.code} style={{ flex: n, background: colors.get(lane.code) }} title={`${lane.label}: ${String(n)}`}>
              {n}
            </span>
          )
        })}
      </div>
      <ul className="nv-lanekey">
        {lanes.map((lane) => (
          <li key={lane.code}>
            <i style={{ background: colors.get(lane.code) }} />
            {lane.label} <b>{counts.get(lane.code) ?? 0}</b>
          </li>
        ))}
      </ul>
    </>
  )
}
