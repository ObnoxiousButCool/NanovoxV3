/**
 * `/hierarchy` — "Is it isolated or systemic?", as `hierarchy.html` has it.
 *
 * One question: is this one unhappy client or something structural? The
 * answer decides the fix, which is why the page is four views of the same
 * calls rather than one ranking — a conversation with one account, a
 * conversation with one broker, and a change to a process are different
 * pieces of work, and nothing here picks between them for the reader.
 *
 * ## The pattern test, not a per-broker rate
 *
 * The prototype is explicit about why: a broker with three employer groups
 * has roughly ten calls, which is too few for a rate. So the broker table
 * carries counts and the pattern test — three adverse mentions across two
 * of its employers — and no rate at all. `rankedBrokers` on the same
 * response does publish one, over the books big enough to carry it; it is
 * a different question and is not what this table shows.
 *
 * ## The heatmap is counts of calls by category, and says so
 *
 * At about eight calls a week a share would be two or three calls. The
 * matrix carries counts, and the panel says they are counts, because a
 * reader who assumes percentages will read a cell of 3 as catastrophic.
 *
 * Zero is a real value here and is rendered as one: call volume has no min
 * n, so an empty cell means no calls rather than too few to publish. That
 * is the opposite of the rule everywhere else on these screens, which is
 * exactly why it is written down.
 *
 * ## Selecting a row filters every page
 *
 * A region or broker row writes the filter rather than navigating. That is
 * the prototype's behaviour and the reason the tables are worth having
 * side by side: the reading is comparative, and a click narrows the whole
 * cockpit to the thing being compared.
 */

import { useState } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

import { useFilterOptions, useGeneratedInsights, useHierarchy } from '@/shared/api/insights'
import type { Hierarchy } from '@/shared/api/insights'
import { useFilters } from '@/shared/filters/useFilters'
import type { Filters } from '@/shared/filters/useFilters'
import { Screen } from '@/shared/screens/Screen'
import { Heatmap } from '@/shared/design/charts'
import type { HeatmapCell } from '@/shared/design/charts'
import { IssueCue, IssueValue } from '@/shared/actions/IssueLink'
import { InsightStrip } from '@/shared/insights/Insights'
import { Empty, EpistemicChip, KpiTile, Panel, Tooltip } from '@/shared/design/primitives'

type RegionRow = Hierarchy['regions'][number]
type BrokerRow = Hierarchy['brokers'][number]

/** The prototype's own cut of the broker table before "show all". */
const TOP_BROKERS = 10

export function HierarchyScreen() {
  const filters = useFilters()
  const { data, isPending, error } = useHierarchy(filters.apiSearch)
  const options = useFilterOptions(filters.apiSearch)
  // `hierarchy.html` opens with the strip. It is its own query so the
  // figures never wait on a model: the page paints, and the sentences
  // arrive after.
  const insights = useGeneratedInsights('hierarchy', filters.apiSearch)
  const brokerNames = new Map(
    (options.data?.brokers ?? []).map((broker) => [broker.ref, broker.agency]),
  )

  return (
    <Screen
      title="Is it isolated or systemic?"
      lede="Whether a problem sits with one account, one broker, or runs across a region or the whole book. The answer decides the fix: a conversation with one account, one broker, or a change to a process."
      scope={data?.scope}
      isPending={isPending}
      error={error}
    >
      {data === undefined ? null : (
        <HierarchyBody
          data={data}
          brokerNames={brokerNames}
          filters={filters}
          insights={insights}
        />
      )}
    </Screen>
  )
}

function HierarchyBody({
  data,
  brokerNames,
  filters,
  insights,
}: {
  data: Hierarchy
  brokerNames: Map<string, string>
  filters: Filters
  insights: ReturnType<typeof useGeneratedInsights>
}) {
  // The union of every category any region recorded. The server already
  // sends every category in every row for exactly this reason — the
  // dark-column reading only works if the columns line up — so this is a
  // belt-and-braces union rather than a fix for a ragged response.
  const categories = [...new Set(data.matrix.flatMap((row) => Object.keys(row.counts)))].sort()

  const cells: HeatmapCell[] = data.matrix.flatMap((row) =>
    categories.map((category) => ({
      row: row.region,
      column: category,
      value: (row.counts as Record<string, number>)[category] ?? 0,
    })),
  )

  return (
    <div className="nv-grid">
      <div className="nv-c12">
        <InsightStrip data={insights.data} pending={insights.isFetching} />
      </div>

      <div className="nv-c12">
        <HierarchyTiles data={data} />
      </div>

      <div className="nv-c7">
        <Panel
          title="Which topics show up where"
          info={
            <Tooltip>
              <p>
                Darker means more calls. A column dark across every row is a book-wide topic,
                which points at a process. One dark cell is local, which points at an account
                or broker.
              </p>
              <p>
                Counts, not shares — at this volume a share would be two or three calls.{' '}
                {data.windowWeeks} weeks to {data.asOf}.
              </p>
              {data.systemic.length > 0 ? (
                <p>
                  Present in every region: {data.systemic.join(', ')}. A presence test, not a
                  volume threshold.
                </p>
              ) : null}
            </Tooltip>
          }
          chip={<EpistemicChip kind="pattern" />}
        >
          {cells.length === 0 ? (
            <Empty>No region has a call in scope, so there is nothing to map.</Empty>
          ) : (
            <Heatmap
              ariaLabel="Calls by region and topic"
              cells={cells}
              rows={data.matrix.map((row) => row.region)}
              columns={categories}
            />
          )}
        </Panel>
      </div>

      <div className="nv-c5">
        <RegionPanel rows={data.regions} filters={filters} />
      </div>

      <div className="nv-c12">
        <BrokerPanel rows={data.brokers} filters={filters} />
      </div>

      <div className="nv-c12">
        <DrillDown data={data} brokerNames={brokerNames} />
      </div>
    </div>
  )
}

/**
 * The four tiles, all of them derived from the tables below them.
 *
 * Deliberately: a tile that disagreed with the table it summarises is
 * worse than no tile, and the only way to be sure it cannot is to compute
 * it from the same rows the table renders.
 */
function HierarchyTiles({ data }: { data: Hierarchy }) {
  const adverse = data.brokers.filter((broker) => broker.adverseMentions > 0)
  const mentions = data.brokers.reduce((total, broker) => total + broker.adverseMentions, 0)
  const firing = data.brokers.filter((broker) => broker.patternFires).length
  const withFlagged = data.regions.filter((region) => region.flagged > 0).length

  return (
    <div className="nv-bigrow">
      <KpiTile
        label="Complaints about us"
        value={String(data.complaints.ours)}
        meta={<span className="nv-indcount">of {data.complaints.total} complaints</span>}
        tone={data.complaints.ours > 0 ? 'warm' : 'plain'}
        todo={data.complaints.ours > 0 ? <IssueCue issue="complaint_choice" /> : undefined}
      />
      <KpiTile
        label="Brokers named adversely"
        value={String(adverse.length)}
        meta={
          <span className="nv-indcount">
            {mentions} {mentions === 1 ? 'call' : 'calls'}
          </span>
        }
        tone={mentions > 0 ? 'warm' : 'plain'}
        todo={mentions > 0 ? <IssueCue issue="broker_adverse" /> : undefined}
      />
      <KpiTile
        label="Broker pattern alerts"
        value={`${String(firing)} of ${String(data.brokers.length)}`}
        meta={<span className="nv-indcount">needs 3 mentions from 2 employers</span>}
        info={
          <Tooltip>
            <p>
              At batch-1 volume the test is unlikely to fire; it is sized for the full 600
              calls.
            </p>
          </Tooltip>
        }
      />
      <KpiTile
        label="Regions with flagged accounts"
        value={`${String(withFlagged)} of ${String(data.regions.length)}`}
        meta={<span className="nv-indcount">flagged in every region = book-wide</span>}
      />
    </div>
  )
}

function RegionPanel({ rows, filters }: { rows: RegionRow[]; filters: Filters }) {
  const selected = new Set(filters.multi.region)

  return (
    <Panel
      title="By region"
      info={
        <Tooltip>
          <p>
            Six regions of about sixteen employers each. Counts, not rates: a region holds
            about sixteen calls in batch 1.
          </p>
          <p>Accounts is every employer in the region, not every one that called.</p>
        </Tooltip>
      }
      chip={<EpistemicChip kind="observed" />}
    >
      {rows.length === 0 ? (
        <Empty>No region has an account in this scope.</Empty>
      ) : (
        <div className="nv-tblwrap">
          <table>
            <caption className="nv-visually-hidden">Accounts and calls by region</caption>
            <thead>
              <tr>
                <th scope="col">Region</th>
                <th className="nv-num" scope="col">
                  Accounts
                </th>
                <th className="nv-num" scope="col">
                  Flagged
                </th>
                <th className="nv-num" scope="col">
                  Calls
                </th>
                <th className="nv-num" scope="col">
                  Unresolved
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <FilterRow
                  key={row.region}
                  selected={selected.has(row.region)}
                  label={`Filter to ${row.region}`}
                  onSelect={() => { filters.toggleMulti('region', row.region) }}
                >
                  <th scope="row">
                    <span className="nv-nm">{row.region}</span>
                  </th>
                  <td className="nv-num">{row.accounts}</td>
                  <td className="nv-num">
                    <Count
                      value={row.flagged}
                      issue="flagged"
                      scope={{ region: row.region }}
                    />
                  </td>
                  <td className="nv-num">{row.calls}</td>
                  <td className="nv-num">
                    <Count
                      value={row.unresolved}
                      issue="unresolved"
                      scope={{ region: row.region }}
                    />
                  </td>
                </FilterRow>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  )
}

function BrokerPanel({ rows, filters }: { rows: BrokerRow[]; filters: Filters }) {
  const [all, setAll] = useState(false)
  const selected = new Set(filters.multi.broker)
  const shown = all ? rows : rows.slice(0, TOP_BROKERS)

  return (
    <Panel
      title="By broker"
      info={
        <Tooltip>
          <p>
            <b>Groups in book</b> comes from the broker sheet, never from call counts, so the
            denominator is not built from the numerator.
          </p>
          <p>
            The pattern test fires when one broker is named adversely three times across two
            of its employers. No per-broker rate is shown: a three-group broker has about ten
            calls, too few for a rate.
          </p>
          {/* Field 14, not the signal of the same name. The two disagree,
              and a reader comparing this column with the actions screen
              should be able to find out which one they are looking at. */}
          <p>
            Named adversely counts only where a caller said that broker&rsquo;s name aloud
            and L1 could corroborate it in their own words. The broker-conduct signal on the
            calls and actions screens is a different field and can carry a different number.
          </p>
        </Tooltip>
      }
      chip={<EpistemicChip kind="observed" />}
    >
      {rows.length === 0 ? (
        <Empty>No broker holds an account in this scope.</Empty>
      ) : (
        <>
          <div className="nv-tblwrap">
            <table>
              <caption className="nv-visually-hidden">Brokers, by adverse mentions</caption>
              <thead>
                <tr>
                  <th scope="col">Broker</th>
                  <th scope="col">Region</th>
                  <th className="nv-num" scope="col">
                    Groups
                  </th>
                  <th className="nv-num" scope="col">
                    Calls
                  </th>
                  <th className="nv-num" scope="col">
                    Named adversely
                  </th>
                  <th className="nv-num" scope="col">
                    Flagged accounts
                  </th>
                </tr>
              </thead>
              <tbody>
                {shown.map((row) => (
                  <FilterRow
                    key={row.brokerRef}
                    selected={selected.has(row.brokerRef)}
                    label={`Filter to ${row.agency}`}
                    onSelect={() => { filters.toggleMulti('broker', row.brokerRef) }}
                  >
                    <th scope="row">
                      <span className="nv-nm">{row.agency}</span>
                      <small>{row.name}</small>
                    </th>
                    <td>{row.region}</td>
                    <td className="nv-num">{row.groupsInBook}</td>
                    <td className="nv-num">{row.calls}</td>
                    {/* §9 asks for the pattern test shown fired and unfired
                        with what it reached. The mentions and the employers
                        behind them are the two numbers the test takes, the
                        threshold is in the panel's (i), and the sentence
                        spelling it out is the cell's title — printed down
                        thirty rows it would be the page's longest text and
                        the same words each time. */}
                    <td className="nv-num" title={row.patternReached}>
                      {row.adverseMentions === 0 ? (
                        <span className="nv-nd">–</span>
                      ) : (
                        <>
                          <IssueValue
                            issue="broker_adverse"
                            tone={row.patternFires ? 'hot' : 'warm'}
                            scope={{ broker: row.brokerRef }}
                          >
                            {row.adverseMentions}
                          </IssueValue>
                          <small>
                            {row.adverseEmployers} employer
                            {row.adverseEmployers === 1 ? '' : 's'}
                          </small>
                        </>
                      )}
                    </td>
                    <td className="nv-num">
                      <Count
                        value={row.flaggedAccounts}
                        issue="flagged"
                        scope={{ broker: row.brokerRef }}
                        blank
                      />
                    </td>
                  </FilterRow>
                ))}
              </tbody>
            </table>
          </div>
          {rows.length > TOP_BROKERS ? (
            <p className="nv-cta">
              <button type="button" className="nv-btn" onClick={() => { setAll(!all) }}>
                {all ? 'Show top 10' : `Show all ${String(rows.length)} brokers`}
              </button>
            </p>
          ) : null}
        </>
      )}
    </Panel>
  )
}

/**
 * A number that links to what to do about it, or a plain nought.
 *
 * `blank` renders a dash instead of a nought, which is the prototype's own
 * choice in the broker table: a dash in a column of exceptions reads as
 * "nothing here", where a nought in a column of counts reads as a count.
 * Neither is a withheld figure — every one of these is observed.
 */
function Count({
  value,
  issue,
  scope,
  blank = false,
}: {
  value: number
  issue: 'flagged' | 'unresolved'
  scope: { region?: string; broker?: string }
  blank?: boolean
}) {
  if (value === 0) return <span className="nv-nd">{blank ? '–' : '0'}</span>
  return (
    <IssueValue issue={issue} tone="warm" scope={scope}>
      {value}
    </IssueValue>
  )
}

/**
 * A table row that writes a filter rather than navigating.
 *
 * Not `DataTable`: that primitive's rows go to a route, and these do not
 * go anywhere — they narrow the cockpit in place. The click and keyboard
 * handling is the same shape it uses internally, and `aria-pressed` says
 * which rows are on, because a highlighted row is not something a screen
 * reader can see.
 */
function FilterRow({
  selected,
  label,
  onSelect,
  children,
}: {
  selected: boolean
  label: string
  onSelect: () => void
  children: ReactNode
}) {
  return (
    <tr
      className={`nv-clickable${selected ? ' nv-selected' : ''}`}
      tabIndex={0}
      role="button"
      aria-pressed={selected}
      aria-label={label}
      onClick={(event) => {
        if ((event.target as HTMLElement).closest('a, button')) return
        onSelect()
      }}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onSelect()
        }
      }}
    >
      {children}
    </tr>
  )
}

/**
 * Region → broker → account, folded away.
 *
 * Folded because it is the answer to "show me", not to "what is wrong":
 * nothing in it is ranked and nothing in it fires. Employers with no calls
 * are in it, at nought, because "this account has not called" is
 * information and a tree that dropped them would make a quiet region look
 * like a small one.
 */
function DrillDown({
  data,
  brokerNames,
}: {
  data: Hierarchy
  brokerNames: Map<string, string>
}) {
  return (
    <section className="nv-panel">
      <details className="nv-more nv-drill">
        <summary>Drill down: region → broker → account</summary>
        {data.tree.length === 0 ? (
          <Empty>No region has an account in this scope.</Empty>
        ) : (
          <div className="nv-tree">
            {data.tree.map((region) => {
              const accounts = region.brokers.reduce(
                (total, broker) => total + broker.employers.length,
                0,
              )
              return (
              <details key={region.region}>
                <summary>
                  <span className="nv-nm">
                    <b>{region.region}</b>
                  </span>
                  <span className="nv-indcount">
                    {accounts} account{accounts === 1 ? '' : 's'} · {region.brokers.length}{' '}
                    broker{region.brokers.length === 1 ? '' : 's'} · {region.calls} call
                    {region.calls === 1 ? '' : 's'}
                  </span>
                </summary>
                {region.brokers.map((broker) => (
                  <details className="nv-lv2" key={broker.brokerRef}>
                    <summary>
                      <span className="nv-nm">
                        {brokerNames.get(broker.brokerRef) ?? broker.brokerRef}
                      </span>
                      <span className="nv-indcount">
                        {broker.employers.length} account
                        {broker.employers.length === 1 ? '' : 's'}
                      </span>
                    </summary>
                    {broker.employers.map((employer) => (
                      <div className="nv-lv3" key={employer.employerRef}>
                        <Link to={`/accounts/${encodeURIComponent(employer.employerRef)}`}>
                          {employer.name}
                        </Link>
                        <span className="nv-indcount">
                          {employer.calls} call{employer.calls === 1 ? '' : 's'}
                        </span>
                      </div>
                    ))}
                  </details>
                ))}
              </details>
              )
            })}
          </div>
        )}
      </details>
    </section>
  )
}
