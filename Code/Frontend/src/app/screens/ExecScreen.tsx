/**
 * `/exec` — the executive scorecard.
 *
 * Follows the v2 prototype's order: the insight strip, then the headline
 * counts, then what moved, then the weekly shape, then what is emerging.
 * The prototype's four "lenses" are still absent — they are a grouping of
 * figures, not of sentences, and grouping them by hand here would be the
 * invented taxonomy §2A.4 forbids until U1's four are wired through.
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
 */

import { Link } from 'react-router-dom'

import { useExec, useGeneratedInsights } from '@/shared/api/insights'
import type { ExecScorecard } from '@/shared/api/insights'
import { useFilters } from '@/shared/filters/useFilters'
import { Screen } from '@/shared/screens/Screen'
import { InsightStrip } from '@/shared/insights/Insights'
import { VLine } from '@/shared/design/charts'
import {
  BigRow,
  Empty,
  EpistemicChip,
  FigureSample,
  FigureValue,
  KpiTile,
  Note,
  Panel,
  basisFromApi,
} from '@/shared/design/primitives'
import type { Figure } from '@/shared/design/primitives'

const percent = (value: number) => `${String(Math.round(value * 100))}%`

/** A figure's chip, or nothing when it names no origin (D13). */
function BasisChip({ figure }: { figure: Figure }) {
  const kind = basisFromApi(figure.basis?.code)
  return kind === null ? null : <EpistemicChip kind={kind} />
}

export function ExecScreen() {
  const filters = useFilters()
  const { data, isPending, error } = useExec(filters.apiSearch)
  const insights = useGeneratedInsights('exec', filters.apiSearch)

  return (
    <Screen
      title="Executive overview"
      lede="What the calls in scope say, with every figure carrying its sample and its origin."
      scope={data?.scope}
      isPending={isPending}
      error={error}
    >
      <InsightStrip data={insights.data} />
      {data === undefined ? null : <ExecBody data={data} />}
    </Screen>
  )
}

function ExecBody({ data }: { data: ExecScorecard }) {
  const { trends } = data

  return (
    <div className="nv-grid">
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
          title="Emerging"
          sub="Rising across the window. Early signals to watch, not proven trends."
          chip={<EpistemicChip kind="pattern" />}
        >
          {trends.emerging.length === 0 ? (
            <Empty>Nothing rose across the window in a way the sample could support.</Empty>
          ) : (
            <ul className="nv-emerging">
              {trends.emerging.map((item) => (
                <li key={`${item.kind}:${item.key}`}>
                  <b>{item.key}</b>
                  <span className="nv-indcount">
                    {item.kind} · {item.delta > 0 ? '+' : ''}
                    {item.delta} across {item.buckets.length} parts of the window
                  </span>
                </li>
              ))}
            </ul>
          )}
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

      <div className="nv-c6">
        <Panel title="Escalation" chip={<EpistemicChip kind="observed" />}>
          {data.escalation.length === 0 ? (
            <Empty>No escalation figures in this scope.</Empty>
          ) : (
            <BigRow>
              {data.escalation.map((entry) => (
                <KpiTile
                  key={entry.label}
                  label={entry.label}
                  value={<FigureValue figure={entry.figure} format={percent} />}
                  meta={<FigureSample figure={entry.figure} />}
                />
              ))}
            </BigRow>
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
        <Note>
          The four lenses and the insight feed the prototype shows here are Phase 5. They are
          absent rather than stubbed: a hand-written narrative would read as generated
          analysis, and nothing on this screen should be something nobody computed.{' '}
          <Link to="/risk">Account risk</Link> and <Link to="/hierarchy">the hierarchy</Link>{' '}
          carry the rest of what is built.
        </Note>
      </div>
    </div>
  )
}
