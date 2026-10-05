/**
 * `/risk` — account risk flags, and what could not be assessed.
 *
 * This is the screen **D12** was decided for, so the decision is visible in
 * three places rather than buried in a component:
 *
 * 1. **"Flagged" means metric 10 and nothing else.** The pill carries the
 *    flag; the indicator count sits beside it as a number.
 * 2. **The indicator count is never a level.** No colour ramp, no
 *    High/Elevated/Watch. It is styled as data, because turning a count
 *    into a band is how the second scoring system came back.
 * 3. **There is no band filter.** The row filters are `flagged` and
 *    `minIndicators`, which is what the API offers.
 *
 * ## Ineligible is a third state, never "not flagged"
 *
 * At batch-1 volume most employers have too few calls to assess. The API
 * keeps them in their own list for exactly this reason, and so does this
 * screen: folding ninety unassessable accounts into "not flagged" would be
 * ninety clean bills of health nobody can support.
 *
 * ## The row filters do not move the share
 *
 * `flaggedShare` and `exposure` are computed over every eligible employer,
 * whatever is filtered. That is enforced on the server and tested there;
 * the panel says so in words, because a reader who filters to "flagged
 * only" and sees a share that is not 100% deserves to know why.
 */

import { Link, useSearchParams } from 'react-router-dom'

import { useFilterOptions, useGeneratedInsights, useRisk } from '@/shared/api/insights'
import type { RiskScreen as RiskScreenData } from '@/shared/api/insights'
import { IssueCue, IssueValue } from '@/shared/actions/IssueLink'
import { issueHref } from '@/shared/actions/issueHref'
import { BarCell, VBars, VLine } from '@/shared/design/charts'
import { OUTCOME_COLOR } from '@/shared/design/outcome'
import type { IssueKey } from '@/shared/actions/issueHref'
import { ISSUE_KEYS, RENEW_SOON_MONTHS } from '@/shared/actions/issueHref'
import { useFilters } from '@/shared/filters/useFilters'
import { Screen } from '@/shared/screens/Screen'
import { InsightFeed } from '@/shared/insights/Insights'
import '@/app/screens/risk.css'
import {
  BigRow,
  DataTable,
  Delta,
  Empty,
  EpistemicChip,
  FigureValue,
  IndicatorCount,
  KpiTile,
  Panel,
  RiskPill,
  Tooltip,
} from '@/shared/design/primitives'

type AssessedAccount = RiskScreenData['assessed'][number]
type AccountContext = { name: string; broker: string; region: string }

/** Whether an account's renewal falls inside the shared soon-window — the
 * same test `/exec`'s needs-attention panel uses, so the two screens cannot
 * disagree on which accounts are "soon". */
function isRenewSoon(account: AssessedAccount): boolean {
  return (
    account.monthsToRenewal !== null &&
    account.monthsToRenewal !== undefined &&
    account.monthsToRenewal <= RENEW_SOON_MONTHS
  )
}

const percent = (value: number) => `${String(Math.round(value * 100))}%`

export function RiskScreen() {
  const filters = useFilters()
  // The two row filters live in the URL beside the corpus filters, but they
  // are not part of `useFilters`: that hook is the shared filter bar, and
  // these mean something on this screen alone. Reading them here keeps them
  // shareable in a link without pretending they narrow any other screen.
  const [params, setParams] = useSearchParams()
  const flagged = params.get('flagged')
  const minIndicators = params.get('minIndicators')

  const search = new URLSearchParams(filters.apiSearch)
  if (flagged !== null) search.set('flagged', flagged)
  if (minIndicators !== null) search.set('minIndicators', minIndicators)

  const { data, isPending, error } = useRisk(search.toString())
  // Deliberately the filter-bar search, not `search`: the row filters
  // above select rows, and every figure the insights read is computed
  // over all eligible employers regardless (D12). Keying on `search`
  // would make a new query for facts that had not moved.
  const insights = useGeneratedInsights('risk', filters.apiSearch)
  // The same query the filter bar already made, so React Query serves it
  // from cache rather than fetching twice. An employer reference is a code,
  // and `FilterBar` states the rule this screen has to keep too: codes
  // never reach a reader.
  const options = useFilterOptions(filters.apiSearch)
  const brokerNames = new Map(
    (options.data?.brokers ?? []).map((broker) => [broker.ref, broker.agency]),
  )
  const names = new Map(
    (options.data?.employers ?? []).map((employer) => [
      employer.ref,
      {
        name: employer.name,
        broker: brokerNames.get(employer.brokerRef) ?? '',
        region: employer.region,
      },
    ]),
  )

  const setRow = (key: string, value: string | null) => {
    // One write, like the period control. Two `setParams` calls in a handler
    // both navigate from the same router state and the second discards the
    // first — the bug the filter bar already carries a comment about.
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous)
        if (value === null || value === '') next.delete(key)
        else next.set(key, value)
        return next
      },
      { replace: false },
    )
  }

  return (
    <div className="nv-risk">
      <Screen
        title="What are the risks?"
        stickyHead
        scope={data?.scope}
        isPending={isPending}
        error={error}
      >
        <div className="nv-risk-insights">
          <InsightFeed data={insights.data} />
        </div>
        {data === undefined ? null : (
          <RiskBody
            data={data}
            names={names}
            flagged={flagged}
            minIndicators={minIndicators}
            onChange={setRow}
          />
        )}
      </Screen>
    </div>
  )
}

function RiskBody({
  data,
  names,
  flagged,
  minIndicators,
  onChange,
}: {
  data: RiskScreenData
  /** Employer context from filter options. Falls back to reference while
      the options are still loading. */
  names: Map<string, AccountContext>
  flagged: string | null
  minIndicators: string | null
  onChange: (key: string, value: string | null) => void
}) {
  // Optional on the wire, so each is read once with a default rather than
  // guarded at every use.
  const outcomes = data.outcomes ?? []
  const weeklyUnresolved = data.weeklyUnresolved ?? []
  const weeklyResolved = data.weeklyResolved ?? []
  const weeklyQuality = data.weeklyQuality ?? []
  const endedTotal = outcomes.reduce((total, entry) => total + entry.calls, 0)
  const unresolvedCount =
    outcomes.find((entry) => entry.outcome.code === 'UNRESOLVED')?.calls ?? 0
  const assessed = data.assessed
  const flaggedAccounts = assessed.filter((account) => account.flagged)
  const renewingSoon = flaggedAccounts.filter(
    (account) =>
      account.monthsToRenewal !== null &&
      account.monthsToRenewal !== undefined &&
      account.monthsToRenewal <= RENEW_SOON_MONTHS,
  )

  return (
    <div className="nv-grid">
      <section className="nv-c12 nv-risk-kpis" aria-label="Risk summary">
        <header>
          <div>
            <h2>Across the eligible accounts</h2>
          </div>
          <EpistemicChip kind="observed" />
        </header>
        <BigRow>
            <KpiTile
              label="Accounts flagged"
              value={String(flaggedAccounts.length)}
              tone={flaggedAccounts.length > 0 ? 'hot' : 'plain'}
              meta={
                <>
                  <FigureValue figure={data.flaggedShare} format={percent} /> of{' '}
                  {String(data.assessedCount)} assessed
                  {data.ineligibleCount > 0
                    ? ` · ${String(data.ineligibleCount)} could not be`
                    : null}
                  <br />
                  {flaggedAccounts.length > 0 ? <IssueCue issue="flagged" /> : null}
                </>
              }
            />
            <KpiTile
              label="Flagged & renewing soon"
              value={String(renewingSoon.length)}
              tone={renewingSoon.length > 0 ? 'hot' : 'plain'}
              meta={
                <>
                  <span className="nv-indcount">
                    renewal within {RENEW_SOON_MONTHS} months
                  </span>
                  <br />
                  {renewingSoon.length > 0 ? <IssueCue issue="renew_soon" /> : null}
                </>
              }
            />
            <KpiTile
              label="Unresolved calls"
              value={String(unresolvedCount)}
              tone={unresolvedCount > 0 ? 'hot' : 'plain'}
              meta={
                <>
                  <span className="nv-indcount">of {String(endedTotal)} calls</span>
                  <br />
                  {unresolvedCount > 0 ? <IssueCue issue="unresolved" /> : null}
                </>
              }
            />
            <KpiTile
              label="Escalations missed"
              info={
                <Tooltip>
                  Escalation integrity is handled ÷ warranted, never ÷ all calls.
                </Tooltip>
              }
              value={String(data.escalationsMissed)}
              tone={data.escalationsMissed > 0 ? 'hot' : 'plain'}
              meta={
                <>
                  <span className="nv-indcount">
                    {String(data.escalationsTriggered - data.escalationsMissed)} of{' '}
                    {String(data.escalationsTriggered)} handled
                  </span>
                  <br />
                  {data.escalationsMissed > 0 ? <IssueCue issue="escalation_missed" /> : null}
                </>
              }
            />
            <KpiTile
              label="Exit language"
              value={String(data.exitLanguageCalls)}
              tone={data.exitLanguageCalls > 0 ? 'warm' : 'plain'}
              meta={
                <>
                  <span className="nv-indcount">said on a call, verbatim</span>
                  <br />
                  {data.exitLanguageCalls > 0 ? <IssueCue issue="exit_language" /> : null}
                </>
              }
            />
            {/* The prototype's sixth tile. Absent rather than nought when the
                window is too short to slice: a window that cannot be cut has
                not told anyone that nobody is new. */}
            {data.newlyFlagged ? (
              <KpiTile
                label="Newly flagged"
                info={
                  <Tooltip>
                    Counted across the whole book. This is the one figure here the filter
                    bar does not touch: an account&rsquo;s first indicator is a fact about
                    the account, not about the slice you are looking through.
                  </Tooltip>
                }
                value={String(data.newlyFlagged.count)}
                meta={
                  <span className="nv-indcount">
                    first indicator in the last {String(data.newlyFlagged.weeks)} weeks
                  </span>
                }
              />
            ) : null}
        </BigRow>
      </section>

      <div className="nv-c12 nv-risk-accounts">
        <Panel
          title="Accounts at risk"
          info={
            <Tooltip>
              <p>
                Ranked by how many <b>unrelated</b> indicators the account&rsquo;s calls raise,
                then by how soon it renews.
              </p>
              <p>
                Risk movement per account (improving or worsening) is withheld: most accounts
                have one call in batch 1, so there is no earlier period to compare against.
              </p>
            </Tooltip>
          }
          chip={<EpistemicChip kind="observed" />}
          actions={
            <div className="nv-rowfilters">
              <label>
                <span>Flag</span>
                <select
                  value={flagged ?? ''}
                  onChange={(event) => {
                    onChange('flagged', event.target.value || null)
                  }}
                >
                  <option value="">Either</option>
                  <option value="true">Flagged</option>
                  <option value="false">Not flagged</option>
                </select>
              </label>
              <label>
                <span>Min indicators</span>
                <select
                  value={minIndicators ?? ''}
                  onChange={(event) => {
                    onChange('minIndicators', event.target.value || null)
                  }}
                >
                  <option value="">Any</option>
                  {[1, 2, 3, 4, 5].map((n) => (
                    <option key={n} value={String(n)}>
                      {n}+
                    </option>
                  ))}
                </select>
              </label>
            </div>
          }
        >
          {data.assessed.length === 0 ? (
            <Empty>
              {data.assessedCount === 0
                ? 'No employer reached the eligibility floor in this window. That is not a finding of low risk — there is not enough here to assess.'
                : 'No assessed account matches these row filters. Widen them to see the rest.'}
            </Empty>
          ) : (
            <DataTable
              caption="Accounts assessed for risk"
              columns={[
                { key: 'account', header: 'Account' },
                // The flag and the conditions it was met on are one metric,
                // so they share a cell -- the way `index.html` puts its band
                // and its count together. That frees the sixth column for
                // lives without blurring D12: the flag stays its own column,
                // the ten families stay theirs, and nothing suggests the
                // families set the flag.
                { key: 'flag', header: 'Flag' },
                { key: 'indicators', header: 'Indicators' },
                { key: 'calls', header: 'Calls', numeric: true },
                { key: 'lives', header: 'Lives', numeric: true },
                { key: 'renews', header: 'Renews' },
              ]}
              rows={data.assessed.map((account) => {
                const fired = account.observations.filter((o) => o.observed)
                const context = names.get(account.employerRef)
                return {
                  key: account.employerRef,
                  // The prototype's `data-href` on the row: the whole row
                  // navigates, and the links inside it (the flag, the fired
                  // indicators) still win over the row's own navigation.
                  href: `/accounts/${encodeURIComponent(account.employerRef)}`,
                  cells: [
                    <>
                      <span className="nv-risk-account-name">
                        {context?.name ?? account.employerRef}
                      </span>
                      {context ? (
                        <small>
                          {[context.broker, context.region].filter(Boolean).join(' · ')}
                        </small>
                      ) : null}
                    </>,
                    // A flagged account is the clearest case of a figure
                    // that should lead somewhere: the pill says what is
                    // true, the link says what to do.
                    <>
                      {account.flagged ? (
                        <IssueValue issue="flagged" scope={{ employer: account.employerRef }}>
                          <RiskPill eligible={account.eligible} flagged={account.flagged} />
                        </IssueValue>
                      ) : (
                        <RiskPill eligible={account.eligible} flagged={account.flagged} />
                      )}
                      <small className="nv-indcount">
                        {account.conditionsMet} of {account.conditions.length} conditions
                      </small>
                    </>,
                    <>
                      {/* A count and the names behind it. Never a level: the
                          families are informational and do not set the flag
                          (D2, D12).

                          `IndicatorCount`, not a bare number: this table
                          printed "0 of 10" beside "Flagged" for accounts
                          nobody had assessed, which reads as a flag with
                          nothing behind it. */}
                      <span className="nv-indcount">
                        <IndicatorCount
                          assessed={account.observations.every((o) => o.assessable)}
                          count={fired.length}
                          // Ten, fixed: `domain/aggregation/indicators.py`
                          // defines exactly ten families and the server
                          // returns all of them, the ones that cleared
                          // included. Not `observations.length`, which would
                          // quietly restate the denominator as whatever
                          // happened to arrive.
                          total={10}
                        />
                      </span>
                      {fired.length > 0 ? (
                        <div className="nv-fires">
                          {fired.map((observation) =>
                            // Only the families the action view has a
                            // playbook for become links. The rest stay
                            // chips rather than routing to a page that
                            // would shrug at them.
                            isIssue(observation.code) ? (
                              <IssueValue
                                key={observation.code}
                                issue={observation.code}
                                scope={{ employer: account.employerRef }}
                                tone="warm"
                              >
                                <span className="nv-fire">{observation.label}</span>
                              </IssueValue>
                            ) : (
                              <span key={observation.code} className="nv-fire">
                                {observation.label}
                              </span>
                            ),
                          )}
                        </div>
                      ) : null}
                    </>,
                    account.calls,
                    // `index.html` prints lives beside the flag: two flagged
                    // accounts are not the same finding when one covers 8
                    // lives and the other 800. Never totalled here — the
                    // exposure note under the tiles is the only sum.
                    //
                    // Said rather than left blank when reference data has no
                    // size: an empty cell reads as a rendering fault, and 0
                    // would read as an account covering nobody.
                    account.lives ?? <span className="nv-none">Not recorded</span>,
                    <span className="nv-indcount">
                      {account.renewalMonth ?? 'unknown'}
                      {account.monthsToRenewal === null || account.monthsToRenewal === undefined ? null : (
                        <span className={isRenewSoon(account) ? 'nv-renewsoon' : 'nv-renewlater'}>
                          {isRenewSoon(account) ? 'in ' : ''}
                          {account.monthsToRenewal} mo
                        </span>
                      )}
                    </span>,
                  ],
                }
              })}
            />
          )}
        </Panel>
      </div>

      {/* `index.html`'s order: the accounts, then what drives them. */}
      <div className="nv-c12">
        <DriversPanel drivers={data.drivers} />
      </div>

      {/* `index.html` pairs the weekly charts, then shows outcomes. */}
      <div className="nv-c6">
        <Panel
          title="Calls each week"
          chip={<EpistemicChip kind="observed" />}
        >
          <VBars
            ariaLabel="Calls and unresolved calls per week"
            height={250}
            labels={weeklyUnresolved.map((week) => week.start.slice(5))}
            series={[
              {
                name: 'Calls',
                values: weeklyUnresolved.map((week) => week.calls ?? null),
                color: 'var(--seq-1)',
              },
              {
                name: 'Unresolved',
                values: weeklyUnresolved.map((week) => week.matched ?? null),
                color: 'var(--seq-3)',
              },
            ]}
          />
        </Panel>
      </div>

      <div className="nv-c6">
        <Panel
          title="Resolved and good-quality calls"
          chip={<EpistemicChip kind="observed" />}
        >
          <VLine
            ariaLabel="Resolved and good-quality shares per week"
            height={250}
            suffix="%"
            yMax={100}
            labels={weeklyResolved.map((week) => week.start.slice(5))}
            series={[
              {
                name: 'Resolved',
                // Null here is two different facts — a silent week and a
                // week too small to carry a rate — and the chart draws
                // both as a gap, which is right: neither is a number.
                values: weeklyResolved.map((week) =>
                  week.share === null || week.share === undefined
                    ? null
                    : Math.round(week.share * 100),
                ),
                color: 'var(--s3)',
              },
              {
                name: 'Good quality',
                values: weeklyQuality.map((week) =>
                  week.share === null || week.share === undefined
                    ? null
                    : Math.round(week.share * 100),
                ),
                color: 'var(--s4)',
              },
            ]}
          />
        </Panel>
      </div>

      <div className="nv-c12">
        <Panel
          title="How calls ended"
          chip={<EpistemicChip kind="observed" />}
        >
          {/* The prototype splits this panel a second way, by handling
              archetype. A note used to sit here saying why that half is
              absent; it was withdrawn, and the panel now shows the outcome
              half without comment. The reasons are recorded at the foot of
              the risk router, not deleted with the sentence. */}
          {endedTotal === 0 ? (
            <Empty>No call in scope records an outcome.</Empty>
          ) : (
            <OutcomeBar outcomes={outcomes} />
          )}
        </Panel>
      </div>

    </div>
  )
}

/** "How calls ended" as one bar, segmented by count — the prototype's
 * shape. A segment's width is its own share of the total, so agreement or
 * disagreement with the corpus is visible without adding the numbers up.
 * Unresolved is the only segment with a playbook, so it is the only one
 * rendered as a link — the rest are plain, exactly as the prototype has it. */
function OutcomeBar({ outcomes }: { outcomes: NonNullable<RiskScreenData['outcomes']> }) {
  const total = outcomes.reduce((sum, entry) => sum + entry.calls, 0)
  return (
    <>
      <div className="nv-stackbar">
        {outcomes.map((entry) => {
          const color = OUTCOME_COLOR[entry.outcome.code] ?? 'var(--ink-3)'
          // A slice under 5% of the bar has no room for its own number
          // without the text overlapping the seam beside it — the
          // prototype leaves it blank rather than crowd it.
          const label = total > 0 && entry.calls / total >= 0.05 ? entry.calls : null
          const style = { flex: Math.max(entry.calls, 0.0001), background: color }
          return entry.outcome.code === 'UNRESOLVED' ? (
            <Link key={entry.outcome.code} to={issueHref('unresolved')} style={style}>
              {label}
            </Link>
          ) : (
            <div key={entry.outcome.code} style={style}>
              {label}
            </div>
          )
        })}
      </div>
      <ul className="nv-stackbar-legend">
        {outcomes.map((entry) => (
          <li key={entry.outcome.code}>
            <i style={{ background: OUTCOME_COLOR[entry.outcome.code] ?? 'var(--ink-3)' }} />
            {entry.outcome.label} {entry.calls}
          </li>
        ))}
      </ul>
    </>
  )
}

/** An indicator family the action view has a playbook for. */
function isIssue(code: string): code is IssueKey {
  return (ISSUE_KEYS as readonly string[]).includes(code)
}

/**
 * "Which problems drive the risk" — the ten indicator families, ranked.
 *
 * The prototype prints a percentage change beside each driver. This does
 * not: at the corpus's volume two calls becoming four is "+100%" and is
 * also a coin flip, so the server sends `beyondNoise` and the panel speaks
 * only when that is true. It is the same treatment the exec page's
 * movements already get.
 *
 * Three different absences, kept apart:
 *
 * - **Not available** — v9 carries no field for the family, so it is shown
 *   with its reason. Never a zero.
 * - **Zero calls** — a real answer, and kept in the list: these ten are the
 *   risk flag's own inputs, so "nobody raised this" is a finding.
 * - **No change** — the window was too short to split. The count stands.
 */
function DriversPanel({ drivers }: { drivers: RiskScreenData['drivers'] }) {
  const rows = drivers ?? []
  const max = Math.max(...rows.map((driver) => driver.calls), 0)

  return (
    <Panel
      title="Which problems drive the risk"
      chip={<EpistemicChip kind="observed" />}
    >
      {rows.length === 0 ? (
        <Empty title="No indicator has been assessed">
          Nothing in scope carries enough calls to read the families over.
        </Empty>
      ) : (
        <ul className="nv-drivers">
          {rows.map((driver, index) => (
            <li key={driver.code}>
              <span className="nv-rk">#{index + 1}</span>
              <span className="nv-drv-label">
                {isIssue(driver.code) ? (
                  <IssueValue issue={driver.code} tone="warm">
                    {driver.label}
                  </IssueValue>
                ) : (
                  driver.label
                )}
                <small>
                  {driver.available
                    ? [driver.topCategory, driver.topTouchpoint]
                        .filter((part) => part !== null && part !== undefined && part !== '')
                        .join(' · ') || 'no calls in scope'
                    : driver.unavailableBecause}
                </small>
              </span>
              {driver.available ? (
                <>
                  <BarCell value={driver.calls} max={max} />
                  <span className="nv-drv-change">
                    {driver.change === null || driver.change === undefined ? (
                      <span className="nv-indcount">no comparison</span>
                    ) : driver.change.beyondNoise ? (
                      <Delta now={driver.change.now} prior={driver.change.prior} />
                    ) : (
                      <span className="nv-indcount">
                        {driver.change.prior} → {driver.change.now}, within noise
                      </span>
                    )}
                  </span>
                </>
              ) : (
                <span className="nv-drv-none">Not available on v9 data</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}
