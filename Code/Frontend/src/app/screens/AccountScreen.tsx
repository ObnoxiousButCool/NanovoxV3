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

import type { AccountDetail } from '@/shared/api/insights'
import { IssueCue } from '@/shared/actions/IssueLink'
import { isIssueKey } from '@/shared/actions/issueHref'
import { AccountTopics } from '@/app/screens/AccountPanels'
import { CallEvidence } from '@/shared/design/drawer/Evidence'
import { useDrawer } from '@/shared/design/drawer'
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
  Tooltip,
} from '@/shared/design/primitives'

const per1000 = (value: number) => value.toFixed(1)
const percent = (value: number) => `${String(Math.round(value * 100))}%`

function titleCase(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1).toLowerCase().replace(/_/g, ' ')
}

/**
 * How long until the renewal, beside the month it falls in.
 *
 * `null` where the workbook's month could not be parsed. Rendered as
 * nothing rather than as a dash: the month above is still true, and a dash
 * here would suggest the renewal itself was unknown.
 */
function RenewalCountdown({ months }: { months: number | null | undefined }) {
  if (months === null || months === undefined) return null
  return (
    <small className="nv-figsub">
      {months === 0 ? 'this month' : `in ${String(months)} month${months === 1 ? '' : 's'}`}
    </small>
  )
}

/**
 * "Account facts that raise the stakes" — `employer.html`'s structural notes.
 *
 * Reference, never observation: nothing here counts a call, and every note
 * is true whether or not anybody rang. That is why they sit beneath the
 * indicators rather than among them, and why the panel says so — a reader
 * who took "participation is below the threshold" for a recent event would
 * respond to it as if something had just happened.
 *
 * An empty list renders nothing at all. Unlike an indicator that did not
 * fire, a structural note that does not apply is not a finding: an account
 * whose participation meets rule P-18 has not told us anything by doing so.
 */
function AccountStakes({ stakes }: { stakes: AccountDetail['stakes'] }) {
  if (stakes.length === 0) return null

  return (
    <>
      <h3 className="nv-subhead">Account facts that raise the stakes</h3>
      <p className="nv-sub">
        From the workbook, not from these calls. True whether or not anyone rang.
      </p>
      <ul className="nv-stakes">
        {stakes.map((stake) => (
          <li key={stake.code}>
            <b>{stake.label}</b>
            <span>{stake.detail}</span>
          </li>
        ))}
      </ul>
    </>
  )
}


/**
 * The calls behind one indicator, and what to do about it.
 *
 * `employer.html` puts both on every indicator row, and they are the two
 * things that make the row usable: the chips are the evidence the figure
 * rests on, and the link is the only route from "this fired" to "here is
 * the step". Without them the panel states ten conditions and offers the
 * reader nothing to do with any of them.
 *
 * The playbook link is scoped to this employer, so the action view opens on
 * this account's instance of the issue rather than the whole book's.
 */
function IndicatorEvidence({
  code,
  callIds,
  employerRef,
}: {
  code: string
  callIds: readonly string[]
  employerRef: string
}) {
  const { open } = useDrawer()
  if (callIds.length === 0) return null

  return (
    <div className="nv-indevidence">
      <span className="nv-callchips">
        {callIds.map((reference) => (
          <button
            key={reference}
            type="button"
            className="nv-callchip"
            onClick={() => {
              open({
                title: `Call ${reference}`,
                chip: 'observed',
                body: <CallEvidence callId={reference} />,
              })
            }}
          >
            {reference}
          </button>
        ))}
      </span>
      {/* Dropped rather than guessed when this build ships no playbook for
          the family — a dead link is worse than none. */}
      {isIssueKey(code) ? <IssueCue issue={code} scope={{ employer: employerRef }} /> : null}
    </div>
  )
}

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
    <>
      <div className="nv-c6">
        <Panel
          title="The account"
          sub={`${facts.industry} · ${facts.region}`}
          chip={<EpistemicChip kind="reference" />}
          info={
            <Tooltip>
              <p>
                <b>More account facts</b>
              </p>
              <p>
                COBRA: {facts.cobraRegime === '' ? 'not recorded' : facts.cobraRegime}
                <br />
                Dental:{' '}
                {facts.dentalSponsorship === 'ER'
                  ? 'employer-sponsored'
                  : facts.dentalSponsorship === ''
                    ? 'not recorded'
                    : 'voluntary'}
                <br />
                Admin fee: ${facts.annualFee.toLocaleString()} a year
                <br />
                Planned calls at full corpus: {String(facts.plannedCalls)}
              </p>
              <p>
                Planned calls are the workbook&rsquo;s design for this account. The corpus
                is a sample of them, so the calls below will be fewer, and the two are
                never the same number.
              </p>
            </Tooltip>
          }
        >
          <div className="nv-figrow">
            <div>
              <span className="nv-figlabel">Enrolled lives</span>
              <b>
                {facts.enrolled.toLocaleString()}
                {facts.eligible > 0 ? ` of ${facts.eligible.toLocaleString()}` : ''}
              </b>
            </div>
            <div>
              <span className="nv-figlabel">Participation</span>
              {/* Null is a gap, not nought enrolled. */}
              <b>
                {facts.participation === null || facts.participation === undefined
                  ? 'Not recorded'
                  : percent(facts.participation)}
              </b>
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
              <span className="nv-figlabel">Admin fee</span>
              <b>${facts.annualFee.toLocaleString()} a year</b>
            </div>
            <div>
              <span className="nv-figlabel">Lines held</span>
              <b>{facts.linesHeld === '' ? 'Not recorded' : titleCase(facts.linesHeld)}</b>
            </div>
            <div>
              <span className="nv-figlabel">Renewal</span>
              {/* The countdown is what makes this actionable; the month
                  alone leaves the reader to work it out. Null where the
                  workbook's month could not be parsed — never a guess. */}
              <b>{facts.renewalMonth}</b>
              <RenewalCountdown months={facts.renewalInMonths} />
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
          {/* Filters slice, never hide. The tiles count the risk window and
              the calls panel lists the selected period; where those differ
              the page says so rather than appearing to contradict itself. */}
          {data.callsInPeriod > data.profile.calls ? (
            <Note>
              {String(data.callsInPeriod - data.profile.calls)} of this account&rsquo;s{' '}
              {String(data.callsInPeriod)} calls in the selected period fall outside the{' '}
              {String(data.riskWindowWeeks)}-week window the counts above use. They are in
              the calls panel below.
            </Note>
          ) : null}
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

      <div className="nv-c7">
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
                <IndicatorEvidence
                  code={condition.code}
                  callIds={condition.callIds ?? []}
                  employerRef={facts.employerRef}
                />
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
                  {/* Unavailable is never zero. A family whose field v9
                      does not carry would read as "no high-effort calls
                      here", which is a false statement about the account.

                      The reason is a sentence, not a count, so it does not
                      go in `nv-indcount` — that is nowrap, which is right
                      for "4 of 18 calls" and made this one sentence 1,458px
                      wide and put a horizontal scrollbar on the page. */}
                  {!observation.available ? (
                    <span className="nv-indreason">{observation.unavailableBecause}</span>
                  ) : (
                    <span className="nv-indcount">
                      {observation.observed
                        ? `${String(observation.hits)} of ${String(observation.employerCalls)} calls`
                        : 'not observed'}
                    </span>
                  )}
                  <IndicatorEvidence
                    code={observation.code}
                    callIds={observation.callIds ?? []}
                    employerRef={facts.employerRef}
                  />
                </li>
              ))}
            </ul>
          )}
          <AccountStakes stakes={data.stakes} />
        </Panel>
      </div>

      <div className="nv-c5">
        <AccountTopics profile={data.profile} />
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

    </>
  )
}
