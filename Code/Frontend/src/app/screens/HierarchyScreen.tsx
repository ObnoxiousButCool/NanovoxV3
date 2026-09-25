/**
 * `/hierarchy` — region, broker, employer, and where friction concentrates.
 *
 * ## The pattern test, not a per-broker rate
 *
 * The prototype is explicit about why: a broker with three employer groups
 * has roughly ten calls, which is too few for a rate. So a broker is
 * ranked by whether the **pattern test** fires — three adverse mentions
 * across two of its employers — and `ratePerHundredLives` is shown only
 * where the server publishes one. Where it is withheld, the withheld
 * reason appears instead of a dash.
 *
 * ## The heatmap is counts of calls by **category**, and says so
 *
 * At about eight calls a week a share would be two or three calls. The
 * matrix carries counts, and the panel says they are counts, because a
 * reader who assumes percentages will read a cell of 3 as catastrophic.
 *
 * Zero is a real value here and is rendered as one: call volume has no min
 * n, so an empty cell means no calls rather than too few to publish. That
 * is the opposite of the rule everywhere else on these screens, which is
 * exactly why it is written down.
 */

import { Link } from 'react-router-dom'

import { useFilterOptions, useHierarchy } from '@/shared/api/insights'
import type { Hierarchy } from '@/shared/api/insights'
import { useFilters } from '@/shared/filters/useFilters'
import { Screen } from '@/shared/screens/Screen'
import { Heatmap } from '@/shared/design/charts'
import type { HeatmapCell } from '@/shared/design/charts'
import {
  Empty,
  EpistemicChip,
  FigureValue,
  Note,
  Panel,
  StatusPill,
} from '@/shared/design/primitives'

export function HierarchyScreen() {
  const filters = useFilters()
  const { data, isPending, error } = useHierarchy(filters.apiSearch)
  const options = useFilterOptions(filters.apiSearch)
  const brokerNames = new Map(
    (options.data?.brokers ?? []).map((broker) => [broker.ref, broker.agency]),
  )

  return (
    <Screen
      title="Isolated or systemic?"
      lede="Whether a problem sits with one account, one broker, or the channel."
      scope={data?.scope}
      isPending={isPending}
      error={error}
    >
      {data === undefined ? null : <HierarchyBody data={data} brokerNames={brokerNames} />}
    </Screen>
  )
}

function HierarchyBody({
  data,
  brokerNames,
}: {
  data: Hierarchy
  brokerNames: Map<string, string>
}) {
  // The union of every category any region recorded. The server already
  // sends every category in every row for exactly this reason — the
  // dark-column reading only works if the columns line up — so this is a
  // belt-and-braces union rather than a fix for a ragged response.
  const categories = [
    ...new Set(data.matrix.flatMap((row) => Object.keys(row.counts))),
  ].sort()

  const cells: HeatmapCell[] = data.matrix.flatMap((row) =>
    categories.map((category) => ({
      row: row.region,
      column: category,
      value: (row.counts as Record<string, number>)[category] ?? 0,
    })),
  )

  return (
    <div className="nv-grid">
      {data.systemic.length > 0 ? (
        <div className="nv-c12">
          <Panel
            title="Reaching across the channel"
            sub="These met the pattern test rather than appearing on one account."
            chip={<EpistemicChip kind="pattern" />}
          >
            <ul className="nv-emerging">
              {data.systemic.map((finding) => (
                <li key={finding}>{finding}</li>
              ))}
            </ul>
          </Panel>
        </div>
      ) : null}

      <div className="nv-c12">
        <Panel
          title="Where friction lands"
          sub={`Calls by region and category. Counts, not shares — at this volume a share would be two or three calls. ${String(data.windowWeeks)} weeks to ${data.asOf}.`}
          chip={<EpistemicChip kind="pattern" />}
        >
          {cells.length === 0 ? (
            <Empty>No region has a call in scope, so there is nothing to map.</Empty>
          ) : (
            <Heatmap
              ariaLabel="Calls by region and category"
              cells={cells}
              rows={data.matrix.map((row) => row.region)}
              columns={categories}
            />
          )}
        </Panel>
      </div>

      <div className="nv-c6">
        <Panel
          title="Brokers, by the pattern test"
          sub="Three adverse mentions across two of its employers. No per-broker rate: a three-group broker has about ten calls."
          chip={<EpistemicChip kind="pattern" />}
        >
          {data.rankedBrokers.length === 0 ? (
            <Empty>No broker was named adversely in this scope.</Empty>
          ) : (
            <table className="nv-risktable">
              <thead>
                <tr>
                  <th scope="col">Broker</th>
                  <th scope="col">Pattern</th>
                  <th scope="col">Mentions</th>
                  <th scope="col">Per 100 lives</th>
                </tr>
              </thead>
              <tbody>
                {data.rankedBrokers.map((broker) => (
                  <tr key={broker.brokerRef}>
                    <th scope="row">
                      {brokerNames.get(broker.brokerRef) ?? broker.brokerRef}
                    </th>
                    <td>
                      {broker.pattern.fires ? (
                        <StatusPill tone="flagged">Fires</StatusPill>
                      ) : (
                        <span className="nv-indcount">{broker.pattern.reached}</span>
                      )}
                    </td>
                    <td className="nv-indcount">
                      {broker.pattern.adverseMentions} across{' '}
                      {broker.pattern.distinctEmployers} employer(s)
                    </td>
                    <td>
                      {/* Null means the server published no rate for this
                          broker at all — not a rate of zero. */}
                      {broker.ratePerHundredLives === null ||
                      broker.ratePerHundredLives === undefined ? (
                        <span className="nv-indcount">Not published</span>
                      ) : (
                        <FigureValue
                          figure={broker.ratePerHundredLives}
                          format={(value) => value.toFixed(2)}
                        />
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>

      <div className="nv-c6">
        <Panel
          title="The book"
          sub="Region, then broker, then the accounts under it."
          chip={<EpistemicChip kind="observed" />}
        >
          {data.tree.length === 0 ? (
            <Empty>No region has a call in this scope.</Empty>
          ) : (
            <ul className="nv-tree">
              {data.tree.map((region) => (
                <li key={region.region}>
                  <b>{region.region}</b>
                  <span className="nv-indcount"> {region.calls} calls</span>
                  <ul>
                    {region.brokers.map((broker) => (
                      <li key={broker.brokerRef}>
                        {brokerNames.get(broker.brokerRef) ?? broker.brokerRef}
                        <span className="nv-indcount"> {broker.calls} calls</span>
                        <ul>
                          {broker.employers.map((employer) => (
                            <li key={employer.employerRef}>
                              <Link
                                to={`/accounts/${encodeURIComponent(employer.employerRef)}`}
                              >
                                {employer.name}
                              </Link>
                              <span className="nv-indcount"> {employer.calls} calls</span>
                            </li>
                          ))}
                        </ul>
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <div className="nv-c12">
        <Note>
          A dark cell in one region is local, which points at an account or a broker. A dark
          column across regions is the channel. Neither claims a cause — see{' '}
          <Link to="/risk">the risk screen</Link> for what has been assessed against metric
          10.
        </Note>
      </div>
    </div>
  )
}
