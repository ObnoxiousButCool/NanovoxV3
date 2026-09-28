/**
 * One account's detail, rendered inside `/accounts` beside the picker.
 *
 * The screen wrapper that used to live here is gone: `AccountsScreen` owns
 * both routes now, and two components fetching the same account to render
 * the same panels was one more than the page needs.
 *
 * ## Account facts are reference, and are labelled as such
 *
 * Enrolled lives, premium, renewal month and broker come from the workbook,
 * not from any call. They wear the **reference** chip, which is the first
 * place in this application that value is used for real — D13 defined it
 * with no producer in the backend, and this panel is the reader-facing half
 * of the same idea. A reader comparing "1,450 lives" against "12 calls"
 * needs to know one was counted and one was looked up.
 *
 * ## The peer comparison says who the peers are, or withholds
 *
 * A median over two employers is not a median anybody should act on. The
 * API sends `peers`, and a comparison is only shown with the count beside
 * it; where the band has no publishable peers it sends null and this says
 * so rather than rendering a dash that reads as zero difference.
 */

import { Link } from 'react-router-dom'

import type { AccountDetail } from '@/shared/api/insights'
import { IssueCue } from '@/shared/actions/IssueLink'
import {
  BigRow,
  Empty,
  EpistemicChip,
  FigureSample,
  FigureValue,
  KpiTile,
  Note,
  Panel,
  RiskPill,
} from '@/shared/design/primitives'

const per1000 = (value: number) => value.toFixed(1)
const percent = (value: number) => `${String(Math.round(value * 100))}%`

export function AccountBody({
  data,
  brokerName,
}: {
  data: AccountDetail
  /** Falls back to the reference while the options are still loading. */
  brokerName: (ref: string) => string
}) {
  const { facts, peers, risk } = data
  const fired = risk.observations.filter((observation) => observation.observed)

  return (
    <div className="nv-grid">
      <div className="nv-c6">
        <Panel
          title="The account"
          sub={`${facts.industry} · ${facts.region}`}
          chip={<EpistemicChip kind="reference" />}
        >
          <div className="nv-figrow">
            <div>
              <span className="nv-figlabel">Enrolled lives</span>
              <b>{facts.enrolled.toLocaleString()}</b>
            </div>
            <div>
              <span className="nv-figlabel">Annual premium</span>
              <b>
                {/* Null is not zero. An account with no premium recorded is
                    not an account worth nothing, and the exposure total on
                    /risk already says it is a floor for this reason. */}
                {facts.annualPremium === null || facts.annualPremium === undefined
                  ? 'Not recorded'
                  : `$${facts.annualPremium.toLocaleString()}`}
              </b>
            </div>
            <div>
              <span className="nv-figlabel">Renewal</span>
              <b>{facts.renewalMonth}</b>
            </div>
            <div>
              <span className="nv-figlabel">Broker of record</span>
              <b>{brokerName(facts.brokerRef)}</b>
            </div>
          </div>
          <Note>
            From the workbook, not from a call. These are what the account is, not what
            happened on it.
          </Note>
        </Panel>
      </div>

      <div className="nv-c6">
        <Panel
          title="Against its peers"
          sub={
            peers.band === null || peers.band === undefined
              ? 'This account fits no size band, so there is nobody to compare it with.'
              : `Size band ${peers.band}, ${String(peers.peers)} peers with a publishable rate.`
          }
          chip={<EpistemicChip kind="derived" />}
        >
          {peers.peerMedian === null || peers.peerMedian === undefined ? (
            <Empty>
              No peer in this band has a rate we can publish, so there is no median to
              compare against. That is a gap in the comparison, not a finding about this
              account.
            </Empty>
          ) : (
            <BigRow>
              <KpiTile
                label="Peer median contact rate"
                value={per1000(peers.peerMedian)}
                meta={<span className="nv-indcount">per 1,000 lives</span>}
              />
              <KpiTile
                label="Difference"
                value={
                  peers.difference === null || peers.difference === undefined
                    ? '–'
                    : `${peers.difference > 0 ? '+' : ''}${per1000(peers.difference)}`
                }
                meta={<span className="nv-indcount">against the median</span>}
              />
            </BigRow>
          )}
        </Panel>
      </div>

      <div className="nv-c6">
        <Panel title="Contact rate" chip={<EpistemicChip kind="observed" />}>
          <BigRow>
            <KpiTile
              label={`Per 1,000 lives · ${String(data.contactRate.windowWeeks)}wk`}
              value={<FigureValue figure={data.contactRate.figure} format={per1000} />}
              meta={<FigureSample figure={data.contactRate.figure} />}
            />
          </BigRow>
        </Panel>
      </div>

      <div className="nv-c6">
        <Panel title="Repeat contact" chip={<EpistemicChip kind="observed" />}>
          <BigRow>
            <KpiTile
              label={`Repeat rate · ${String(data.repeatRate.windowWeeks)}wk`}
              value={<FigureValue figure={data.repeatRate.figure} format={percent} />}
              meta={<FigureSample figure={data.repeatRate.figure} />}
            />
          </BigRow>
        </Panel>
      </div>

      <div className="nv-c12">
        <Panel
          title="The risk flag"
          sub={`Metric 10 over ${String(data.riskWindowWeeks)} weeks, as at ${data.asOf}.`}
          chip={<EpistemicChip kind="observed" />}
          actions={<RiskPill eligible={risk.eligible} flagged={risk.flagged} />}
        >
          {/* The server's own sentence, not one composed here. It already
              distinguishes ineligible from not-flagged and says the flag is
              not a prediction; rewriting it on the client is how those
              distinctions get lost. */}
          <Note>{risk.state}</Note>

          <h3 className="nv-subhead">The four conditions</h3>
          <ul className="nv-conditions">
            {/* Every condition, including the ones that did not fire. A list
                of only what fired cannot be told apart from a list nobody
                evaluated. */}
            {risk.conditions.map((condition) => (
              <li key={condition.code} className={condition.met ? 'nv-met' : 'nv-unmet'}>
                <span aria-hidden="true">{condition.met ? '●' : '○'}</span>
                <span>{condition.label}</span>
                <span className="nv-indcount">
                  {condition.met
                    ? `${String((condition.callIds ?? []).length)} call(s)`
                    : 'not met'}
                </span>
              </li>
            ))}
          </ul>

          <h3 className="nv-subhead">
            Other conditions observed — {fired.length} of {risk.observations.length}
          </h3>
          <p className="nv-sub">
            Informational. These do not set the flag (D2), and the count is a count rather
            than a level (D12).
          </p>
          {risk.observations.length === 0 ? (
            <Empty>No indicator families were evaluated for this account.</Empty>
          ) : (
            <ul className="nv-conditions">
              {risk.observations.map((observation) => (
                <li
                  key={observation.code}
                  className={
                    !observation.available
                      ? 'nv-unavailable'
                      : observation.observed
                        ? 'nv-met'
                        : 'nv-unmet'
                  }
                >
                  <span aria-hidden="true">
                    {!observation.available ? '—' : observation.observed ? '●' : '○'}
                  </span>
                  <span>{observation.label}</span>
                  <span className="nv-indcount">
                    {/* Unavailable is never zero. A family whose field v9
                        does not carry would read as "no high-effort calls
                        here", which is a false statement about the account. */}
                    {!observation.available
                      ? observation.unavailableBecause
                      : observation.observed
                        ? `${String(observation.hits)} of ${String(observation.employerCalls)} calls`
                        : 'not observed'}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <div className="nv-c12">
        <Panel
          title="Broker of record"
          sub="Insight 7: who the caller named, against who is on record."
          chip={<EpistemicChip kind="observed" />}
        >
          {/* The server's sentence, which distinguishes a clean book from
              an unexamined one. Zero mismatches is a finding, so this
              panel renders in every case rather than only on drift. */}
          <Note>{data.drift.finding}</Note>
          {data.drift.flagged ? (
            <IssueCue issue="broker_adverse" scope={{ employer: facts.employerRef }}>
              What to do about the drift
            </IssueCue>
          ) : null}
        </Panel>
      </div>

      <div className="nv-c12">
        <Note>
          The calls behind these figures open in Phase 3, when <Link to="/calls">/calls</Link>{' '}
          exists. Until then the evidence is the call references the API returns, not a
          screen.
        </Note>
      </div>
    </div>
  )
}
