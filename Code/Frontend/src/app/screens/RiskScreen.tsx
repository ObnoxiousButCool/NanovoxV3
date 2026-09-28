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
import { BarCell, VBars, VLine } from '@/shared/design/charts'
import type { IssueKey } from '@/shared/actions/issueHref'
import { ISSUE_KEYS } from '@/shared/actions/issueHref'
import { useFilters } from '@/shared/filters/useFilters'
import { Screen } from '@/shared/screens/Screen'
import { InsightFeed } from '@/shared/insights/Insights'
import {
  BigRow,
  Delta,
  Empty,
  EpistemicChip,
  FigureSample,
  FigureValue,
  KpiTile,
  Note,
  Panel,
  RiskPill,
} from '@/shared/design/primitives'

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
  const names = new Map(
    (options.data?.employers ?? []).map((employer) => [employer.ref, employer.name]),
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
    <Screen
      // The rail's wording, which is the prototype's own. A screen whose
      // title disagrees with the link that reached it reads as the wrong page.
      title="What are the risks?"
      lede="Metric 10's flag, the conditions behind it, and the accounts there was not enough evidence to assess."
      scope={data?.scope}
      isPending={isPending}
      error={error}
    >
      {data === undefined ? null : (
        <RiskBody
          data={data}
          names={names}
          flagged={flagged}
          minIndicators={minIndicators}
          onChange={setRow}
        />
      )}
      <InsightFeed data={insights.data} />
    </Screen>
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
  /** Employer reference to name. Falls back to the reference, which is
      better than an empty cell while the options are still loading. */
  names: Map<string, string>
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

  return (
    <div className="nv-grid">
      <div className="nv-c12">
        <Panel
          title="Across the eligible accounts"
          sub={`Metric 10 over ${String(data.windowWeeks)} weeks, as at ${data.asOf}.`}
          chip={<EpistemicChip kind="observed" />}
        >
          <BigRow>
            <KpiTile
              label="Flagged, of those assessable"
              value={<FigureValue figure={data.flaggedShare} format={percent} />}
              meta={<FigureSample figure={data.flaggedShare} />}
            />
            <KpiTile
              label="Assessed"
              value={String(data.assessedCount)}
              meta={<span className="nv-indcount">had enough calls</span>}
            />
            <KpiTile
              label="Could not be assessed"
              value={String(data.ineligibleCount)}
              meta={<span className="nv-indcount">too few calls</span>}
            />
            <KpiTile
              label="Lives behind the flagged"
              value={String(data.exposure.lives)}
              meta={<span className="nv-indcount">exposure, not expected loss</span>}
            />
          </BigRow>
          <Note>{data.exposure.caveat}</Note>
          {data.exposure.employers.length > 0 ? <IssueCue issue="flagged" /> : null}
        </Panel>
      </div>

      <div className="nv-c12">
        <Panel
          title="Accounts assessed"
          sub={
            <>
              Most indicators first, then soonest renewal. Showing{' '}
              {data.assessed.length} of {data.assessedCount} assessed — the share and
              exposure above are over all {data.assessedCount}, whatever is filtered here.
            </>
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
            <table className="nv-risktable">
              <thead>
                <tr>
                  <th scope="col">Account</th>
                  <th scope="col">Flag</th>
                  <th scope="col">Indicators</th>
                  <th scope="col">Conditions</th>
                  <th scope="col">Calls</th>
                </tr>
              </thead>
              <tbody>
                {data.assessed.map((account) => {
                  const fired = account.observations.filter((o) => o.observed)
                  return (
                    <tr key={account.employerRef}>
                      <th scope="row">
                        <Link to={`/accounts/${encodeURIComponent(account.employerRef)}`}>
                          {names.get(account.employerRef) ?? account.employerRef}
                        </Link>
                      </th>
                      <td>
                        {/* A flagged account is the clearest case of a
                            figure that should lead somewhere: the pill
                            says what is true, the link says what to do. */}
                        {account.flagged ? (
                          <IssueValue issue="flagged" scope={{ employer: account.employerRef }}>
                            <RiskPill eligible={account.eligible} flagged={account.flagged} />
                          </IssueValue>
                        ) : (
                          <RiskPill eligible={account.eligible} flagged={account.flagged} />
                        )}
                      </td>
                      <td>
                        {/* A count and the names behind it. Never a level:
                            the families are informational and do not set the
                            flag (D2, D12). */}
                        <span className="nv-indcount">{fired.length} of 10</span>
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
                      </td>
                      <td className="nv-indcount">
                        {account.conditionsMet} of {account.conditions.length}
                      </td>
                      <td className="nv-indcount">{account.calls}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          )}
        </Panel>
      </div>

      {/* `index.html`'s order: the accounts, then what drives them. */}
      <div className="nv-c12">
        <DriversPanel drivers={data.drivers} />
      </div>

      {/* The three corpus-shape panels V2 puts on this page. They were on
          /exec or nowhere until conflict C9 was recorded: each screen had
          been shaped by its endpoint rather than by the page it mirrors. */}
      <div className="nv-c6">
        <Panel
          title="How calls ended"
          sub={`${String(unresolvedCount)} of ${String(endedTotal)} calls ended unresolved.`}
          chip={<EpistemicChip kind="observed" />}
        >
          {endedTotal === 0 ? (
            <Empty>No call in scope records an outcome.</Empty>
          ) : (
            <VBars
              ariaLabel="Calls by outcome"
              labels={outcomes.map((entry) => entry.outcome.label)}
              series={[
                {
                  name: 'Calls',
                  // Counts, so a zero is a real bar on the baseline rather
                  // than a gap. Call volume has no minimum.
                  values: outcomes.map((entry) => entry.calls),
                  color: 'var(--seq-2)',
                },
              ]}
            />
          )}
          <Note>{data.handlingUnavailable}</Note>
        </Panel>
      </div>

      <div className="nv-c6">
        <Panel
          title="Calls each week"
          sub="Counts. A blank week is a week the corpus says nothing about."
          chip={<EpistemicChip kind="observed" />}
        >
          <VLine
            ariaLabel="Calls and unresolved calls per week"
            labels={weeklyUnresolved.map((week) => week.start.slice(5))}
            series={[
              {
                name: 'Calls',
                values: weeklyUnresolved.map((week) => week.calls ?? null),
                color: 'var(--seq-2)',
              },
              {
                name: 'Unresolved',
                values: weeklyUnresolved.map((week) => week.matched ?? null),
                color: 'var(--serious)',
              },
            ]}
          />
        </Panel>
      </div>

      <div className="nv-c12">
        <Panel
          title="Resolved and good-quality calls"
          sub="Shape, not level. A week under five calls is left blank rather than drawn as a swing."
          chip={<EpistemicChip kind="observed" />}
        >
          <VLine
            ariaLabel="Resolved and good-quality shares per week"
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
                color: 'var(--good)',
              },
              {
                name: 'Good quality',
                values: weeklyQuality.map((week) =>
                  week.share === null || week.share === undefined
                    ? null
                    : Math.round(week.share * 100),
                ),
                color: 'var(--seq-3)',
              },
            ]}
          />
        </Panel>
      </div>

      <div className="nv-c12">
        <Panel
          title="Not enough calls to assess"
          sub="Kept apart on purpose. Too few calls to assess is not a finding of low risk."
          chip={<EpistemicChip kind="observed" />}
        >
          {data.ineligible.length === 0 ? (
            <Empty>Every employer in scope had enough calls to assess.</Empty>
          ) : (
            <div className="nv-fires">
              {data.ineligible.map((ref) => (
                <Link
                  key={ref}
                  className="nv-fire"
                  to={`/accounts/${encodeURIComponent(ref)}`}
                >
                  {names.get(ref) ?? ref}
                </Link>
              ))}
            </div>
          )}
        </Panel>
      </div>
    </div>
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
      sub="Each driver is one of the ten indicators, counted in calls. Most common first."
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
