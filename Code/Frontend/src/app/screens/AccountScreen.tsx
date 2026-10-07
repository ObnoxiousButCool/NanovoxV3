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
  Empty,
  EpistemicChip,
  Note,
  Panel,
  RiskPill,
} from '@/shared/design/primitives'

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

/**
 * The account, named. `employer.html` opens with this and everything else
 * follows it — a reader who has just picked one of ninety-five accounts
 * needs to see which one they landed on before any figure about it.
 */
export function AccountHeader({ data }: { data: AccountDetail }) {
  const { facts, risk } = data
  return (
    <>
      {/* `employer.html` leads with the account, not with a panel called
          "The account": the name is the heading and the five workbook facts
          sit under it. A reader who has clicked an account out of ninety-five needs
          to see which one they landed on before anything else. */}
      <div className="nv-c12">
        <Panel
          title={facts.name}
          chip={<EpistemicChip kind="reference" />}
          actions={<RiskPill eligible={risk.eligible} flagged={risk.flagged} />}
        >
          {/* The prototype's five, in its order. */}
          <div className="nv-figrow">
            <div>
              <span className="nv-figlabel">Lives enrolled</span>
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
              <span className="nv-figlabel">Lines held</span>
              <b>{facts.linesHeld === '' ? 'Not recorded' : titleCase(facts.linesHeld)}</b>
            </div>
            <div>
              <span className="nv-figlabel">Admin fee</span>
              <b>${facts.annualFee.toLocaleString()} a year</b>
            </div>
            <div>
              <span className="nv-figlabel">Renews</span>
              <b>{facts.renewalMonth}</b>
              <RenewalCountdown months={facts.renewalInMonths} />
            </div>
          </div>
        </Panel>
      </div>
    </>
  )
}

export function AccountBody({ data }: { data: AccountDetail }) {
  const { facts, risk } = data
  const fired = risk.observations.filter((observation) => observation.observed)
  // One unassessable family means all ten are: the floor is on the employer,
  // not on the family. Read off the first rather than assumed, so a server
  // that ever disagreed would show through instead of being papered over.
  const unassessed = risk.observations.find((observation) => !observation.assessable)

  // The denominator is the families that could be looked at, not all ten.
  //
  // `available` is false where no v9 field backs the family at all — today
  // that is high member effort, a composite Stream A's derivations would own
  // and nobody built. Counting it in the denominator says ten were checked
  // when nine were, which is the same false statement the row below avoids by
  // drawing an em dash instead of a nought. Saying it in the heading and
  // denying it in the row would be an odd way to be careful.
  const checkable = risk.observations.filter((observation) => observation.available)
  const notComputable = risk.observations.length - checkable.length

  return (
    <>
      <div className="nv-c7">
        <Panel
          title="What went wrong on this account"
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
            Other conditions observed —{' '}
            {unassessed === undefined
              ? `${String(fired.length)} of ${String(checkable.length)}`
              : 'not assessed'}
            {unassessed === undefined && notComputable > 0 ? (
              <span className="nv-subhead-aside">
                {' '}
                ({String(notComputable)} not computable)
              </span>
            ) : null}
          </h3>
          {/* Said once at the top rather than repeated on all ten rows. A
              count of nought here would read as a clean account, when what
              happened is that nobody could look. */}
          {unassessed === undefined ? null : <Note>{unassessed.unassessableBecause}</Note>}
          {risk.observations.length === 0 ? (
            <Empty>No indicator families were evaluated for this account.</Empty>
          ) : (
            <ul className="nv-conditions">
              {risk.observations.map((observation) => (
                <li
                  key={observation.code}
                  className={
                    !observation.available || !observation.assessable
                      ? 'nv-unavailable'
                      : observation.observed
                        ? 'nv-met'
                        : 'nv-unmet'
                  }
                >
                  <span aria-hidden="true">
                    {!observation.available || !observation.assessable
                      ? '—'
                      : observation.observed
                        ? '●'
                        : '○'}
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
                      {/* Three readings, not two. A family with hits on an
                          account nobody could assess is neither observed nor
                          absent, and "not observed" is false about it — two
                          of Junipero's three calls carry a complaint. */}
                      {/* And a fourth: assessed, with hits, under the rate
                          gate. "Not observed" beside four listed calls — and
                          a tile reading "Escalations missed 4" — is false;
                          what is true is that they did not clear the bar. */}
                      {observation.observed
                        ? `${String(observation.hits)} of ${String(observation.employerCalls)} calls`
                        : observation.assessable
                          ? observation.hits > 0
                            ? `${String(observation.hits)} of ${String(observation.employerCalls)} calls, under the threshold`
                            : 'not observed'
                          : observation.hits > 0
                            ? `${String(observation.hits)} of ${String(observation.employerCalls)} calls, not assessed`
                            : 'not assessed'}
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

    </>
  )
}
