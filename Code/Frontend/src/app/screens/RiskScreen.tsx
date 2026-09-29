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
import type { IssueKey } from '@/shared/actions/issueHref'
import { ISSUE_KEYS, RENEW_SOON_MONTHS } from '@/shared/actions/issueHref'
import { useFilters } from '@/shared/filters/useFilters'
import { Screen } from '@/shared/screens/Screen'
import { InsightFeed } from '@/shared/insights/Insights'
import {
  BigRow,
  Delta,
  Empty,
  EpistemicChip,
  FigureValue,
  KpiTile,
  Note,
  Panel,
  RiskPill,
  Tooltip,
} from '@/shared/design/primitives'

type AssessedAccount = RiskScreenData['assessed'][number]

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
      {/* The prototype's `.aistrip` sits right under the filter bar, above
          the KPI tiles — the same reading order this feed keeps here,
          rather than after every computed panel on the page. */}
      <InsightFeed data={insights.data} />
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
      <div className="nv-c12">
        <Panel
          title="Across the eligible accounts"
          sub={`Metric 10 over ${String(data.windowWeeks)} weeks, as at ${data.asOf}.`}
          chip={<EpistemicChip kind="observed" />}
        >
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
          </BigRow>
          <Note>{data.exposure.caveat}</Note>
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
                  <th scope="col">Renews</th>
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
                      <td className="nv-indcount">
                        {account.renewalMonth ?? 'unknown'}
                        {account.monthsToRenewal === null || account.monthsToRenewal === undefined ? null : (
                          <span
                            className={isRenewSoon(account) ? 'nv-renewsoon' : 'nv-renewlater'}
                          >
                            {isRenewSoon(account) ? 'in ' : ''}
                            {account.monthsToRenewal} mo
                          </span>
                        )}
                      </td>
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
          been shaped by its endpoint rather than by the page it mirrors.
          `index.html`'s own order: "How calls ended" stands full width on
          its own, then the two weekly charts pair up beside each other —
          not the other way around. */}
      <div className="nv-c12">
        <Panel
          title="How calls ended"
          sub={`${String(unresolvedCount)} of ${String(endedTotal)} calls ended unresolved.`}
          chip={<EpistemicChip kind="observed" />}
        >
          {endedTotal === 0 ? (
            <Empty>No call in scope records an outcome.</Empty>
          ) : (
            <OutcomeBar outcomes={outcomes} />
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
          sub="Shape, not level. A week under five calls is left blank rather than drawn as a swing."
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

      <div className="nv-c12">
        <BandCalibrationPanel panel={data.bandCalibration} />
      </div>
    </div>
  )
}

/** Insight 9, withheld unconditionally — no gate unlocks it, only a schema
 * change (a termination/renewal outcome per employer) nobody has made. */
function BandCalibrationPanel({
  panel,
}: {
  panel: RiskScreenData['bandCalibration']
}) {
  return (
    <Panel title={panel.question} chip={<EpistemicChip kind="inference" />}>
      <Note>{panel.why}</Note>
      <Note>{panel.unlockedBy}</Note>
    </Panel>
  )
}

/** The workbook's own order for an outcome — the legend and the bar read
 * left to right in the order a call resolves worse, matching the prototype
 * rather than whatever order the API happens to list them in. Colours are
 * the prototype's own outcome set (`--s3`/`--s4`/`--seq-2`), not the general
 * good/warning ramp: `--good` and `--warning` already mean something else
 * elsewhere on this screen (tile tone), and reusing them here would make
 * this one bar look like a status readout rather than a distribution. */
const OUTCOME_COLOR: Record<string, string> = {
  RESOLVED: 'var(--s3)',
  PARTIALLY_RESOLVED: 'var(--s4)',
  ESCALATED: 'var(--seq-2)',
  UNRESOLVED: 'var(--critical)',
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
