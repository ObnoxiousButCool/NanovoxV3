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
import type { FilterOptions, RiskScreen as RiskScreenData } from '@/shared/api/insights'
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
  Note,
  Pager,
  Panel,
  RiskPill,
  StatusPill,
  Tooltip,
} from '@/shared/design/primitives'
import type { Row } from '@/shared/design/primitives'

type AssessedAccount = RiskScreenData['assessed'][number]
type AccountContext = { name: string; broker: string; brokerRef: string; region: string }

/** The four tabs the accounts list reads through, in reading order. Every
 * list here is derived from fields the API already returns — no score, no
 * band, and the ten informational observations never rank or flag anything
 * (§2A.4, D12). */
type AccountTab = 'soon' | 'flagged' | 'unflagged' | 'unassessed'

const TAB_ORDER: { key: AccountTab; label: string }[] = [
  { key: 'soon', label: 'Flagged, renewing soon' },
  { key: 'flagged', label: 'All flagged' },
  { key: 'unflagged', label: 'Not flagged' },
  { key: 'unassessed', label: 'Not assessed' },
]

const ACCOUNTS_PER_PAGE = 10

/** "Up to 2... plus a '+n' for the rest" — the row design's own cap on how
 * many of the ten informational observations show as chips. */
const CHIP_LIMIT = 2

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
  // The accounts-at-risk tab, its region/broker/quotable narrowing and its
  // page live in the URL beside the corpus filters, but are not part of
  // `useFilters`: that hook is the shared filter bar, and these mean
  // something on this screen alone. Reading them here keeps a view of "all
  // flagged accounts renewing in the West" shareable in a link.
  const [params, setParams] = useSearchParams()
  const tab = (params.get('accountTab') as AccountTab | null) ?? 'soon'
  const region = params.get('accountRegion')
  const broker = params.get('accountBroker')
  const quotableOnly = params.get('accountQuotable') === 'true'
  const page = Math.max(1, Number(params.get('accountPage') ?? '1') || 1)

  // Deliberately `filters.apiSearch` alone, with no `flagged`/`minIndicators`
  // appended: every account the window could assess arrives, and the four
  // tabs, the region/broker toggles and the pager all read it client-side.
  // That is what lets the tab counts update together without four fetches.
  const { data, isPending, error } = useRisk(filters.apiSearch)
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
        brokerRef: employer.brokerRef,
        region: employer.region,
      },
    ]),
  )

  const setAccountParam = (key: string, value: string | null) => {
    // One write, like the period control. Two `setParams` calls in a handler
    // both navigate from the same router state and the second discards the
    // first — the bug the filter bar already carries a comment about.
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous)
        if (value === null || value === '') next.delete(key)
        else next.set(key, value)
        // Any change other than turning the page itself goes back to page
        // 1 — staying on page 4 of a tab that now has two pages shows an
        // empty list, which reads as "no matches" rather than "past the end".
        if (key !== 'accountPage') next.delete('accountPage')
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
            options={options.data}
            tab={tab}
            region={region}
            broker={broker}
            quotableOnly={quotableOnly}
            page={page}
            onChange={setAccountParam}
          />
        )}
      </Screen>
    </div>
  )
}

function RiskBody({
  data,
  names,
  options,
  tab,
  region,
  broker,
  quotableOnly,
  page,
  onChange,
}: {
  data: RiskScreenData
  /** Employer context from filter options. Falls back to reference while
      the options are still loading. */
  names: Map<string, AccountContext>
  /** Undefined until the filter options land; the region/broker selects
      read the corpus-wide lists off it rather than only what this window's
      accounts happen to cover. */
  options: FilterOptions | undefined
  tab: AccountTab
  region: string | null
  broker: string | null
  quotableOnly: boolean
  page: number
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

  // Region and broker read off the same filter-options join `names` already
  // carries; quotable reads the field the server already computed (whether
  // there are enough calls to quote the account as a figure) rather than
  // re-deriving a call-count floor here.
  const matchesLocalFilters = (employerRef: string): boolean => {
    const context = names.get(employerRef)
    if (region !== null && context?.region !== region) return false
    if (broker !== null && context?.brokerRef !== broker) return false
    return true
  }
  const matchesQuotable = (account: AssessedAccount): boolean =>
    !quotableOnly || account.quotable

  const narrowedAssessed = assessed.filter(
    (account) => matchesLocalFilters(account.employerRef) && matchesQuotable(account),
  )
  const soonTab = narrowedAssessed.filter(
    (account) => account.flagged && isRenewSoon(account),
  )
  const flaggedTab = narrowedAssessed.filter((account) => account.flagged)
  const unflaggedTab = narrowedAssessed.filter((account) => !account.flagged)
  // Not assessed does not carry `quotable` — too few calls to assess is a
  // stronger statement than "not enough to quote" already, so the toggle
  // has nothing to add here and narrows only by region and broker.
  const unassessedTab = (quotableOnly ? [] : data.ineligible).filter(matchesLocalFilters)

  const tabCounts: Record<AccountTab, number> = {
    soon: soonTab.length,
    flagged: flaggedTab.length,
    unflagged: unflaggedTab.length,
    unassessed: unassessedTab.length,
  }
  const activeAssessed =
    tab === 'soon' ? soonTab : tab === 'flagged' ? flaggedTab : tab === 'unflagged' ? unflaggedTab : []
  const activeUnassessed = tab === 'unassessed' ? unassessedTab : []
  const activeTotal = tab === 'unassessed' ? activeUnassessed.length : activeAssessed.length

  const pageCount = Math.max(1, Math.ceil(activeTotal / ACCOUNTS_PER_PAGE))
  const currentPage = Math.min(page, pageCount)
  const pageStart = (currentPage - 1) * ACCOUNTS_PER_PAGE
  const pagedAssessed = activeAssessed.slice(pageStart, pageStart + ACCOUNTS_PER_PAGE)
  const pagedUnassessed = activeUnassessed.slice(pageStart, pageStart + ACCOUNTS_PER_PAGE)

  const hasAnyLocalFilter = region !== null || broker !== null || quotableOnly

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
            {/* The flagged count is the executive overview's tile, where it
                opens the page. Repeating it here as a second tile said the
                same thing twice in the same words; what this screen owns
                that the overview does not is the denominator and the
                accounts that could not be assessed, and those now sit on
                the table they qualify. */}
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
          meta={
            <>
              <span>
                {String(flaggedAccounts.length)} flagged of {String(data.assessedCount)}{' '}
                assessed, <FigureValue figure={data.flaggedShare} format={percent} />{' '}
                {flaggedAccounts.length > 0 ? <IssueCue issue="flagged" /> : null}
              </span>
              {/* Never folded into "not flagged": an account with too few
                  calls to assess has not been found clean, and this is the
                  only place that says so. */}
              <span>
                {data.ineligibleCount > 0
                  ? `${String(data.ineligibleCount)} could not be assessed`
                  : 'every account could be assessed'}
              </span>
            </>
          }
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
        >
          <div className="nv-risk-tabs" role="tablist" aria-label="Accounts at risk, by tab">
            {TAB_ORDER.map((entry) => (
              <button
                key={entry.key}
                type="button"
                role="tab"
                aria-selected={tab === entry.key}
                className="nv-risk-tab"
                onClick={() => {
                  onChange('accountTab', entry.key === 'soon' ? null : entry.key)
                }}
              >
                {entry.label}
                <span className="nv-risk-tabcount">{tabCounts[entry.key]}</span>
              </button>
            ))}
          </div>

          {tab === 'unassessed' ? (
            <Note>
              Not assessed does not mean not at risk. These accounts do not have enough calls
              yet.
            </Note>
          ) : null}

          <div className="nv-rowfilters">
            <label>
              <span>Region</span>
              <select
                value={region ?? ''}
                onChange={(event) => {
                  onChange('accountRegion', event.target.value || null)
                }}
              >
                <option value="">Any region</option>
                {(options?.regions ?? []).map((value) => (
                  <option key={value} value={value}>
                    {value}
                  </option>
                ))}
              </select>
            </label>
            <label>
              <span>Broker</span>
              <select
                value={broker ?? ''}
                onChange={(event) => {
                  onChange('accountBroker', event.target.value || null)
                }}
              >
                <option value="">Any broker</option>
                {(options?.brokers ?? []).map((entry) => (
                  <option key={entry.ref} value={entry.ref}>
                    {entry.agency}
                  </option>
                ))}
              </select>
            </label>
            <label className="nv-check">
              <input
                type="checkbox"
                checked={quotableOnly}
                onChange={(event) => {
                  onChange('accountQuotable', event.target.checked ? 'true' : null)
                }}
              />
              <span>Quotable only (10+ calls)</span>
            </label>
            <span className="nv-indcount nv-risk-orderedby">
              Ordered by conditions met, then soonest renewal
            </span>
          </div>

          {activeTotal === 0 && data.assessedCount === 0 && tab !== 'unassessed' ? (
            // Nothing in the whole book could be assessed — true regardless
            // of tab or filter, so it is said instead of "no matches",
            // which would read as a question worth narrowing further.
            <Empty>
              No employer reached the eligibility floor in this window. That is not a finding
              of low risk — there is not enough here to assess.
            </Empty>
          ) : activeTotal === 0 ? (
            <Empty title="No accounts match these filters">
              {hasAnyLocalFilter ? (
                <button
                  type="button"
                  className="nv-linkbtn"
                  onClick={() => {
                    onChange('accountRegion', null)
                    onChange('accountBroker', null)
                    onChange('accountQuotable', null)
                  }}
                >
                  Clear filters
                </button>
              ) : tab === 'unassessed' ? (
                'Every account in scope reached the eligibility floor.'
              ) : (
                'Widen the tab or the period to see the rest.'
              )}
            </Empty>
          ) : (
            <>
              <DataTable
                caption="Accounts assessed for risk"
                columns={[
                  { key: 'account', header: 'Account' },
                  { key: 'conditions', header: 'Conditions' },
                  { key: 'observed', header: 'What we saw' },
                  { key: 'renews', header: 'Renews' },
                  { key: 'calls', header: 'Calls & lives' },
                ]}
                rows={
                  tab === 'unassessed'
                    ? pagedUnassessed.map((employerRef) => ineligibleRow(employerRef, names))
                    : pagedAssessed.map((account) => assessedRow(account, names))
                }
              />
              <p className="nv-indcount nv-risk-pagesummary">
                Showing {String(pageStart + 1)}-{String(Math.min(pageStart + ACCOUNTS_PER_PAGE, activeTotal))}{' '}
                of {String(activeTotal)} accounts
              </p>
              <Pager
                page={currentPage}
                pageCount={pageCount}
                onChange={(next) => {
                  onChange('accountPage', next === 1 ? null : String(next))
                }}
              />
            </>
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

/** One assessed account, as a `DataTable` row. */
function assessedRow(account: AssessedAccount, names: Map<string, AccountContext>): Row {
  const fired = account.observations.filter((o) => o.observed)
  const shownChips = fired.slice(0, CHIP_LIMIT)
  const overflow = fired.length - shownChips.length
  const context = names.get(account.employerRef)

  return {
    key: account.employerRef,
    // The prototype's `data-href` on the row: the whole row navigates, and
    // the links inside it (the flag, the fired indicators) still win over
    // the row's own navigation.
    href: `/accounts/${encodeURIComponent(account.employerRef)}`,
    cells: [
      <>
        <span className="nv-risk-account-name">{context?.name ?? account.employerRef}</span>
        {context ? (
          <small>{[context.broker, context.region].filter(Boolean).join(' · ')}</small>
        ) : null}
      </>,
      // A flagged account is the clearest case of a figure that should lead
      // somewhere: the pill says what is true, the link says what to do.
      // The four pips are metric 10's own conditions (D12): a count a
      // reader can verify at a glance, never a band.
      <>
        {account.flagged ? (
          <IssueValue issue="flagged" scope={{ employer: account.employerRef }}>
            <RiskPill eligible={account.eligible} flagged={account.flagged} />
          </IssueValue>
        ) : (
          <RiskPill eligible={account.eligible} flagged={account.flagged} />
        )}
        <div className="nv-condpips" aria-hidden="true">
          {account.conditions.map((condition) => (
            <i
              key={condition.code}
              className={`nv-condpip${condition.met ? ' nv-condpip-met' : ''}`}
              title={condition.label}
            />
          ))}
        </div>
        <small className="nv-indcount">
          {account.conditionsMet} of {account.conditions.length} conditions
        </small>
      </>,
      <>
        {/* A count and the names behind it. Never a level: the families
            are informational and do not set the flag (D2, D12).

            `IndicatorCount`, not a bare number: this table printed "0 of
            10" beside "Flagged" for accounts nobody had assessed, which
            reads as a flag with nothing behind it. */}
        <span className="nv-indcount">
          <IndicatorCount
            assessed={account.observations.every((o) => o.assessable)}
            count={fired.length}
            // Ten, fixed: `domain/aggregation/indicators.py` defines
            // exactly ten families and the server returns all of them, the
            // ones that cleared included. Not `observations.length`, which
            // would quietly restate the denominator as whatever arrived.
            total={10}
          />
        </span>
        {shownChips.length > 0 ? (
          <div className="nv-fires">
            {shownChips.map((observation) =>
              // Only the families the action view has a playbook for
              // become links. The rest stay chips rather than routing to a
              // page that would shrug at them.
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
            {overflow > 0 ? (
              <span className="nv-fire nv-fire-more" title={`${String(overflow)} more observed`}>
                +{overflow}
              </span>
            ) : null}
          </div>
        ) : null}
      </>,
      <span className="nv-indcount">
        {account.renewalMonth ?? 'unknown'}
        {account.monthsToRenewal === null || account.monthsToRenewal === undefined ? null : (
          <span className={isRenewSoon(account) ? 'nv-renewsoon' : 'nv-renewlater'}>
            {isRenewSoon(account) ? 'in ' : ''}
            {account.monthsToRenewal} mo
          </span>
        )}
      </span>,
      <>
        <span className="nv-indcount">
          {String(account.calls)} calls ·{' '}
          {/* Said rather than left blank when reference data has no size:
              an empty cell reads as a rendering fault, and 0 would read as
              an account covering nobody. */}
          {account.lives === null || account.lives === undefined ? (
            <span className="nv-none">lives not recorded</span>
          ) : (
            `${String(account.lives)} lives`
          )}
        </span>
        {account.quotable ? null : (
          <span className="nv-quotetag">Too few calls to quote</span>
        )}
      </>,
    ],
  }
}

/** An ineligible employer, as a `DataTable` row -- no `AccountRiskResponse`
 * exists for it, so every cell beyond identity says so rather than
 * inventing a count, a renewal or a condition nobody tested. */
function ineligibleRow(employerRef: string, names: Map<string, AccountContext>): Row {
  const context = names.get(employerRef)
  return {
    key: employerRef,
    href: `/accounts/${encodeURIComponent(employerRef)}`,
    cells: [
      <>
        <span className="nv-risk-account-name">{context?.name ?? employerRef}</span>
        {context ? (
          <small>{[context.broker, context.region].filter(Boolean).join(' · ')}</small>
        ) : null}
      </>,
      <StatusPill tone="ineligible" />,
      <span className="nv-none">Too few calls to assess</span>,
      <span className="nv-none">—</span>,
      <span className="nv-none">—</span>,
    ],
  }
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
