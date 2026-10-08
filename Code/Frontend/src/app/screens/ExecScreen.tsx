/**
 * `/exec` — the executive scorecard.
 *
 * Follows the v2 prototype's order: needs-attention, the headline counts, a
 * risk-and-follow-through summary row, what moved and what emerged, then
 * what is being done about it. The prototype's four "lenses" (`InsightLenses`)
 * are wired through and rendered last, below the figures they read — see the
 * comment at that call site for why the position differs from the
 * prototype's mid-page placement.
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
import { InsightFeed, InsightLenses } from '@/shared/insights/Insights'
import { IssueCue } from '@/shared/actions/IssueLink'
import { RENEW_SOON_MONTHS } from '@/shared/actions/issueHref'
import { Gauge, MiniBars } from '@/shared/design/charts'
import { findLane } from '@/app/screens/actions/lifecycle'
import { laneColors } from '@/app/screens/actions/format'
import '@/app/screens/actions/actionsBoard.css'
import '@/app/screens/exec.css'
import {
  BigRow,
  Empty,
  EpistemicChip,
  FigureValue,
  IndicatorCount,
  KpiTile,
  Skeleton,
  SkeletonBlock,
  SkeletonTiles,
  Note,
  Panel,
} from '@/shared/design/primitives'

const percent = (value: number) => `${String(Math.round(value * 100))}%`

type AssessedAccount = RiskScreenData['assessed'][number]
type MovementEntry = ExecScorecard['trends']['movements'][number]
type EmergingEntry = ExecScorecard['trends']['emerging'][number]


export function ExecScreen() {
  const filters = useFilters()
  const { data, isPending, error } = useExec(filters.apiSearch)
  const risk = useRisk(filters.apiSearch)
  // The filter bar applies here as it does everywhere else, so the board
  // this screen counts from is the one the bar describes.
  const board = useActionBoard(filters.apiSearch)
  // The same query the filter bar already made, so React Query serves it
  // from cache. An employer reference is a code, and the needs-attention
  // panel names accounts — codes never reach a reader.
  const options = useFilterOptions(filters.apiSearch)
  const insights = useGeneratedInsights('exec', filters.apiSearch)

  const names = new Map(
    (options.data?.employers ?? []).map((employer) => [employer.ref, employer.name]),
  )

  return (
    <div className="nv-exec">
      <Screen
        title="Executive overview"
        compactFilters
        stickyHead
        scope={data?.scope}
        isPending={isPending || risk.isPending || board.isPending}
        error={error ?? risk.error ?? board.error}
        skeleton={<ExecSkeleton />}
      >
        {data === undefined || risk.data === undefined || board.data === undefined ? null : (
          <ExecBody data={data} risk={risk.data} board={board.data} names={names} insights={insights.data} />
        )}
      </Screen>
    </div>
  )
}

/**
 * The exec layout, before its figures arrive.
 *
 * Shaped like `ExecBody` on purpose — two columns, the attention panel and
 * insight feed on the left, tiles and panels on the right — so the page does
 * not rearrange itself when the data lands. Three queries gate this screen
 * (`/exec`, `/risk`, `/insights/actions/board`) and the slowest decides, so
 * the wait is the sum of nobody's expectations.
 *
 * It is not pixel-exact and should not be: matching panel heights would mean
 * duplicating every panel's content rules here, and they would drift apart on
 * the first change. Matching the *arrangement* is what stops the reflow.
 */
function ExecSkeleton() {
  return (
    <Skeleton>
      <div className="nv-withai">
        <div className="nv-feedcol">
          <SkeletonBlock lines={6} />
          <SkeletonBlock lines={4} />
        </div>
        <div className="nv-maincol nv-grid">
          <div className="nv-c12">
            <SkeletonTiles count={4} />
          </div>
          <div className="nv-c6">
            <SkeletonBlock lines={2} />
          </div>
          <div className="nv-c6">
            <SkeletonBlock lines={2} />
          </div>
          <div className="nv-c12">
            <SkeletonBlock lines={4} />
          </div>
          <div className="nv-c12">
            <SkeletonBlock lines={5} />
          </div>
        </div>
      </div>
    </Skeleton>
  )
}

function ExecBody({
  data,
  risk,
  board,
  names,
  insights,
}: {
  data: ExecScorecard
  risk: RiskScreenData
  board: ActionBoard
  names: Map<string, string>
  insights: Parameters<typeof InsightFeed>[0]['data']
}) {
  const { trends } = data

  return (
    <div className="nv-withai">
      <div className="nv-feedcol">
        {/* The flagged accounts lead the column. `exec.html` opens its feed
            with this card — it is the first `.aiitem` and the only one open
            by default — because it is the one thing on the page that names
            an account somebody has to do something about. The generated
            sentences follow it. */}
        <NeedsAttentionPanel risk={risk} names={names} />
        <InsightFeed
          data={insights}
          title="Attention insights"
          badgeLabel="Needs attention now"
        />
      </div>
      <div className="nv-maincol nv-grid">
      <div className="nv-c12">
        <SummaryTilesPanel data={data} risk={risk} board={board} />
      </div>

      <WellAndConcernPanels movements={trends.movements} windowWeeks={trends.windowWeeks} concern={data.areaOfConcern ?? null} />

      <div className="nv-c12 nv-exec-lenses">
        <InsightLenses data={insights} />
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
 * ## Soonest renewal first, not most indicators
 *
 * `risk.assessed` arrives in D12's order: the flag, then the indicator
 * count, then the renewal. That is the right order for `/risk`, where the
 * question is which accounts are in trouble. It is the wrong one here.
 *
 * `exec.html` sorts this list by renewal and then by indicator count —
 * Kelso (3, Oct), Kingsley (2, Oct), Sandpiper (5, Dec) — and it is right
 * to. Every account in this list is already flagged, so the count no longer
 * separates them by whether they need attention, only by how much; what
 * separates them on an executive page is how long there is left to do
 * anything about it. The panel's own subtitle counts renewals for the same
 * reason.
 *
 * D12 is not touched by this. It fixes what "flagged" means and how `/risk`
 * ranks; this is one panel choosing which of two flagged accounts to print
 * first, and §3.0 gives the prototype presentation.
 *
 * A renewal nobody can read sorts last rather than first, the same 99 the
 * server's own key uses: `null` would otherwise read as "renewing now".
 */
function NeedsAttentionPanel({
  risk,
  names,
}: {
  risk: RiskScreenData
  names: Map<string, string>
}) {
  const flagged = [...risk.assessed]
    .filter((account) => account.flagged)
    .sort(
      (a, b) =>
        monthsOrLast(a) - monthsOrLast(b) ||
        indicatorCount(b) - indicatorCount(a) ||
        a.employerRef.localeCompare(b.employerRef),
    )
  // Six, as `exec.html` prints.
  const top = flagged.slice(0, 6)

  return (
    // `exec.html` writes this as a card: the count sits opposite a label,
    // and the two actions are a filled button and a ghost at the foot.
    <Panel
      title="Flagged accounts"
      className="nv-flagcard"
      meta={
        <>
          <span className="nv-flagcard-lens">
            <EpistemicChip kind="observed" /> Account risk
          </span>
          <span className="nv-flagcard-count">
            {flagged.length} {flagged.length === 1 ? 'account' : 'accounts'}
          </span>
        </>
      }
      footer={
        <div className="nv-ai-act">
          {flagged.length > 0 ? <IssueCue issue="flagged" /> : null}
          <Link className="nv-btn" to="/risk">
            Show in overview
          </Link>
        </div>
      }
    >
      {top.length === 0 ? (
        <Empty title="Nothing flagged">No account meets metric 10's flag in this scope.</Empty>
      ) : (
        <ul className="nv-attn" aria-label="Flagged accounts">
          {top.map((account) => (
            <li key={account.employerRef}>
              <Link to={`/accounts/${encodeURIComponent(account.employerRef)}`}>
                <span
                  className="nv-dot"
                  style={{ background: withinRenewSoon(account) ? 'var(--critical)' : 'var(--serious)' }}
                />
                <span className="nv-attn-who">
                  <b>{names.get(account.employerRef) ?? account.employerRef}</b>
                </span>
                {/* One compact meta, the way `exec.html` writes it — "3
                    indicators · Oct". The five-column row this list borrows
                    from `/actions` was built for a full-width panel; in the
                    330px feed column its fixed tracks came to more than the
                    row was wide, so the account's name was allotted 0px.

                    A dash, not a nought, below the families' own floor:
                    Junipero and Blue Mesa are flagged on 3 and 4 calls and
                    were never assessed on the ten, and "0 of 10" beside their
                    names reads as a flag with nothing behind it. */}
                <span className="nv-attn-meta" title={renewalText(account)}>
                  <IndicatorCount
                    assessed={assessedOnFamilies(account)}
                    count={indicatorCount(account)}
                    unassessed="not assessed"
                  />
                  {assessedOnFamilies(account) ? ' indicators' : null} ·{' '}
                  {account.renewalMonth ?? 'renewal unknown'}
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

/** False below `indicators.min_employer_calls`, where none were tested. */
function assessedOnFamilies(account: AssessedAccount): boolean {
  return account.observations.every((observation) => observation.assessable)
}

/** Months to renewal, with an unreadable one sorting last rather than now. */
function monthsOrLast(account: AssessedAccount): number {
  const months = account.monthsToRenewal
  return months === null || months === undefined ? 99 : months
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
    // The prototype renders these four tiles bare, with no enclosing panel
    // or title — they sit directly beside "Needs attention now" (`exec.html`'s
    // own layout). `BigRow` already carries its own border, so no wrapper
    // is needed to match that.
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
    <section className="nv-panel nv-wellbad" aria-label="What went well and area of concern">
      <div>
        <h3><span className="nv-exec-icon nv-good-icon" aria-hidden="true">✓</span>What went well</h3>
        {best === undefined ? (
          <p>No measure improved beyond noise in the last {windowWeeks} weeks.</p>
        ) : (
          <p><b>{best.label}</b> fell from {best.prior} to {best.now} in the last {windowWeeks} weeks.</p>
        )}
      </div>
      <div>
        <h3><span className="nv-exec-icon nv-concern-icon" aria-hidden="true">!</span>Area of concern</h3>
        {concern === null || concern === undefined ? (
          <p>No category carried an unresolved call in this scope.</p>
        ) : (
          <p>
            <b>{concern.category}</b> carries the most unresolved calls ({concern.unresolved}){' '}
            {concern.escalationsTriggered > concern.escalationsHandled
              ? `, and only ${String(concern.escalationsHandled)} of ${String(concern.escalationsTriggered)} escalations there were handled.`
              : '.'}
          </p>
        )}
      </div>
    </section>
  )
}

/** Production measures that have no top-level counterpart in the prototype. */
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
 * How many more calls a thing must have gained across the window to be worth a
 * card. A threshold rather than a fixed count of cards, because the tail is
 * mostly an artefact: touchpoints arrive as free text, so `Claim processing`,
 * `Claims process` and `Claims status` are three rows, and a single call in
 * the last slice makes each of them "rising" by one. At batch-1 volume more
 * than half the risers are a single call in total. Five is the point where a
 * rise is several calls rather than a wording difference.
 *
 * A fixed count hides a different number of real items every window and always
 * shows the same number of rows; a threshold shows what cleared the bar, and
 * the note says what did not.
 */
const MIN_RISE = 5

/**
 * Curated "Emerging issues" — every item that rose by at least `MIN_RISE` as a
 * card with its own chart, and the falling items in an "Easing" sidebar.
 * Replaces a flat dump of every tracked category, touchpoint, signal and
 * product line.
 *
 * `rising` is the server's, and it is not `delta > 0`: a row that spiked and
 * is subsiding is net up without emerging, and ranking on `delta` alone used
 * to seat one of those second on this panel. Those rows are counted under the
 * cards rather than dropped — a reader who cannot see that a cut happened has
 * no reason to look for what is under it.
 */
function EmergingPanel({ emerging }: { emerging: EmergingEntry[] }) {
  const allRising = emerging.filter((item) => item.rising).sort((a, b) => b.delta - a.delta)
  const rising = allRising.filter((item) => item.delta >= MIN_RISE)
  const spiked = emerging.filter((item) => item.delta > 0 && item.receded).length
  const easing = emerging
    .filter((item) => item.delta < 0)
    .sort((a, b) => a.delta - b.delta)
    .slice(0, 5)

  const notes = [
    allRising.length > rising.length
      ? `${String(allRising.length)} items rose; the ${String(allRising.length - rising.length)} that rose by fewer than ${String(MIN_RISE)} calls are not shown.`
      : null,
    spiked > 0
      ? `${String(spiked)} rose earlier in the window and are now below their peak.`
      : null,
  ].filter((line): line is string => line !== null)

  return (
    <Panel
      title="Emerging issues"
      chip={<EpistemicChip kind="pattern" />}
    >
      <div className="nv-emgrid">
        <div>
          {rising.length === 0 ? (
            allRising.length === 0 ? (
              <Empty title="Nothing rising">No tracked item rose across this window.</Empty>
            ) : (
              // Things rose, none by enough to call emerging. Saying "nothing
              // rose" here would be false, and the note below gives the count.
              <Empty title="Nothing rose far enough">
                {`No tracked item gained ${String(MIN_RISE)} or more calls across this window.`}
              </Empty>
            )
          ) : (
            rising.map((item) => <EmergingCard key={`${item.kind}:${item.key}`} item={item} />)
          )}
          {notes.length > 0 && <Note suppressed>{notes.join(' ')}</Note>}
        </div>
        <aside className="nv-easing">
          <h3>Easing</h3>
          {easing.length === 0 ? (
            <Empty title="Nothing easing">Nothing fell across this window.</Empty>
          ) : (
            <ul>
              {easing.map((item) => (
                <li key={`${item.kind}:${item.key}`}>
                  <span>
                    <b>{item.label}</b>
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
        {/* This card only ever shows a rising item (see `EmergingPanel`
            above), so the most recent bucket — the one being claimed
            about — is coloured critical red rather than the default
            brand blue: it is the bar that says "this is what rose". */}
        <MiniBars
          values={item.buckets.map((bucket) => bucket.hits)}
          color="var(--critical)"
          label={`${item.label} across the window: ${item.buckets.map((bucket) => bucket.hits).join(', ')}`}
        />
      </div>
      <div className="nv-emtext">
        <div className="nv-emtop">
          <b>{item.label}</b>
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

  return (
    <Panel
      title="What is being done"
      sub={
        board.actions.length > 0 ? undefined : 'No actions have been raised on this board yet.'
      }
      chip={<EpistemicChip kind="observed" />}
    >
      <ActionBar lanes={board.lanes} counts={counts} colors={colors} />
      <p className="nv-cta">
        <Link to="/actions">Open the action board →</Link>{' '}
        <Link to="/risk">See every risk and driver →</Link>
      </p>
    </Panel>
  )
}

/** The colored status bar plus its legend, using the board's actual counts. */
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
