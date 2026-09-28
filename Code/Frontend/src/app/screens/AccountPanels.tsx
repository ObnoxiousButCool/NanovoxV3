/**
 * The two account panels the prototype's `employer.html` ends with: the
 * calls behind the account, and the actions raised from them.
 *
 * Both are servable from endpoints that already exist, which is why they
 * are here and the other three prototype panels are not — "What they call
 * about", the unresolved/missed/quality tiles and the structural notes have
 * no source, and inventing one is what §2A.4 forbids.
 *
 * ## The calls panel asks the server; the actions panel filters the board
 *
 * Calls come from `/insights/calls?employer=…`, because the corpus is large
 * and paging belongs on the server. Actions come from the whole board,
 * filtered here — the board is one page of work in progress, not a corpus,
 * and a per-account endpoint would be a second definition of a list a
 * reader could count.
 *
 * An action reaches this account two ways, both of which the prototype
 * uses: it names the employer, or it cites one of the account's calls. The
 * second matters, because an action raised from a signal carries the call
 * it was raised from and not the employer behind it.
 */

import { useMemo } from 'react'

import { useActionBoard } from '@/shared/api/actionBoard'
import { useCalls } from '@/shared/api/insights'
import type { AccountProfile, CallRow } from '@/shared/api/insights'
import { CallEvidence } from '@/shared/design/drawer/Evidence'
import { useDrawer } from '@/shared/design/drawer'
import { IssueValue } from '@/shared/actions/IssueLink'
import { BarCell } from '@/shared/design/charts'
import {
  BigRow,
  DataTable,
  Empty,
  EpistemicChip,
  KpiTile,
  Note,
  Panel,
  Tooltip,
  Withheld,
} from '@/shared/design/primitives'
import type { Column, Row } from '@/shared/design/primitives'

/** One page of calls, as the prototype shows. The workbench has the rest. */
const PER_PAGE = 25

function titleCase(value: string): string {
  return value.charAt(0) + value.slice(1).toLowerCase().replace(/_/g, ' ')
}

export function AccountCalls({
  employerRef,
  search,
}: {
  employerRef: string
  search: string
}) {
  const { open } = useDrawer()

  const query = useMemo(() => {
    const params = new URLSearchParams(search)
    // Deleted before it is set: the filter bar may already carry an
    // employer, and two would read as "either", putting another account's
    // calls under this account's name.
    params.delete('employer')
    params.set('employer', employerRef)
    params.set('perPage', String(PER_PAGE))
    return params.toString()
  }, [employerRef, search])

  const { data, isPending, error } = useCalls(query)

  return (
    <Panel
      title="Calls"
      sub="Select a call for the transcript, tags and quoted evidence."
      chip={<EpistemicChip kind="observed" />}
    >
      {error ? (
        <Note>{error.message}</Note>
      ) : isPending ? (
        <Note>Loading this account&rsquo;s calls…</Note>
      ) : data.rows.length === 0 ? (
        <Empty title="No calls in this period">
          Widen the period to see this account&rsquo;s calls.
        </Empty>
      ) : (
        <>
          <table className="nv-risktable nv-callstable">
            <thead>
              <tr>
                <th scope="col">Call</th>
                <th scope="col">Caller</th>
                <th scope="col">Topic</th>
                <th scope="col">Outcome</th>
                <th scope="col">Signals</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((call) => (
                <CallLine
                  key={call.reference}
                  call={call}
                  onOpen={() => {
                    open({
                      title: `Call ${call.reference}`,
                      chip: 'observed',
                      body: <CallEvidence callId={call.reference} />,
                    })
                  }}
                />
              ))}
            </tbody>
          </table>
          {data.total > data.rows.length ? (
            <Note>
              Showing {String(data.rows.length)} of {String(data.total)} calls for this
              account. The calls workbench carries the rest.
            </Note>
          ) : null}
        </>
      )}
    </Panel>
  )
}

function CallLine({ call, onOpen }: { call: CallRow; onOpen: () => void }) {
  return (
    <tr>
      <td>
        <button type="button" className="nv-linkbtn" onClick={onOpen}>
          {call.reference}
        </button>
        <small>{call.occurredOn}</small>
      </td>
      <td>
        {/* The reference where reference data names nobody: a gap in the
            Member and Contact sheets, not an anonymous caller, and the
            reference is still how the reader looks them up. */}
        {call.callerName ?? call.callerRef ?? 'not recorded'}
        <small>{call.callerKind ?? 'unknown caller type'}</small>
      </td>
      <td>
        {call.category ?? 'no category'}
        <small>{call.touchpoint ?? 'no touchpoint'}</small>
      </td>
      <td>
        {/* The word carries the meaning, never the colour alone. */}
        {call.outcome ? titleCase(call.outcome) : 'not recorded'}
        <small>
          {call.qualityScore === null || call.qualityScore === undefined
            ? 'unscored'
            : `quality ${String(call.qualityScore)}`}
        </small>
      </td>
      <td>
        {call.signals && call.signals.length > 0 ? (
          <span className="nv-acct-sigs">
            {call.signals.map((signal) => (
              <span key={signal}>{titleCase(signal)}</span>
            ))}
          </span>
        ) : (
          <span className="nv-acct-none">–</span>
        )}
      </td>
    </tr>
  )
}

const ACTION_COLUMNS: Column[] = [
  { key: 'action', header: 'Action' },
  { key: 'owner', header: 'Owner' },
  { key: 'status', header: 'Status' },
  { key: 'outcome', header: 'Outcome' },
]

export function AccountActions({
  employerRef,
  callRefs,
}: {
  employerRef: string
  /** This account's calls, so an action citing one is found too. */
  callRefs: readonly string[]
}) {
  const { data, isPending, error } = useActionBoard()

  const mine = useMemo(() => {
    const cited = new Set(callRefs)
    return (data?.actions ?? []).filter(
      (action) =>
        action.employerRef === employerRef ||
        action.callIds.some((reference) => cited.has(reference)),
    )
  }, [data, employerRef, callRefs])

  const rows: Row[] = mine.map((action) => ({
    key: String(action.id),
    cells: [
      <>
        {action.title}
        <small>{action.evidence}</small>
      </>,
      <>
        {action.ownerTeam}
        <small>{action.owner ?? 'unassigned'}</small>
      </>,
      <>
        {action.status}
        {action.due === null ? null : <small>due {action.due}</small>}
      </>,
      // Never a dash on its own: an action with no measured outcome yet is
      // a different thing from one that achieved nothing.
      action.outcome ?? <span className="nv-acct-none">not yet measured</span>,
    ],
  }))

  return (
    <Panel
      title="Actions for this account"
      // A recommendation, not an observation: C3a rules that a suggestion
      // must never be readable as something the corpus measured.
      chip={<EpistemicChip kind="recommendation" />}
    >
      {error ? (
        <Note>{error.message}</Note>
      ) : isPending ? (
        <Note>Loading actions…</Note>
      ) : rows.length === 0 ? (
        <Empty title="No action raised for this account yet">
          Nothing in its calls has needed one.
        </Empty>
      ) : (
        <DataTable columns={ACTION_COLUMNS} rows={rows} />
      )}
    </Panel>
  )
}

/**
 * The four tiles the prototype puts above the account detail.
 *
 * **Five tiles, and the fifth says why it has no number.** `employer.html`
 * ends with "Average call quality". Metric 12 is defined per agent and the
 * domain states that rolling it up to an employer is forbidden by the
 * Metrics sheet, so no average is served or computed. What this used to do
 * was leave the slot out entirely — and a silently missing tile is the one
 * thing the rest of this application never does. Withheld is not zero, and
 * it is not absence either: it is a figure we decline to publish, with the
 * reason attached, which is what `tone="withheld"` is for.
 *
 * The count beside it is **coverage, not quality**: how many of the
 * account's calls carry a score at all. Every one of those scores is
 * already printed against its own call in the panel below, because metric
 * 12 is admissible as a property of a call. It is the summary over an
 * employer that the sheet forbids, and none is made here.
 *
 * The other four tiles are **counts**, so none is suppressed: zero
 * unresolved calls out of four is a true and useful statement, where a zero
 * *rate* over four would not be.
 */
export function AccountTiles({ profile }: { profile: AccountProfile }) {
  return (
    <Panel
      title="This account's calls"
      sub={`Counted over the same window as the risk flag below.`}
      chip={<EpistemicChip kind="observed" />}
    >
      <BigRow>
        <KpiTile
          label="Calls in period"
          value={String(profile.calls)}
          meta={<span className="nv-indcount">in the risk window</span>}
        />
        <Tile
          label="Unresolved"
          value={profile.unresolved}
          issue="unresolved"
          meta={`of ${String(profile.calls)} calls`}
        />
        <Tile
          label="Repeat contacts"
          value={profile.repeatContacts}
          issue="repeat_contact"
          meta="unresolved, and they came back"
        />
        <Tile
          label="Escalations missed"
          value={profile.escalationsMissed}
          issue="escalation_missed"
          meta="warranted, not given"
        />
        <KpiTile
          tone="withheld"
          label="Average call quality"
          // Never a number here. The reason is the finding.
          value={<Withheld reason={{ code: 'per_agent_only', label: 'Not published' }} />}
          // Plain text, not `nv-indcount`: that class is nowrap, which is
          // right for a bare count and wrong for a sentence — it pushed the
          // tile past the edge of the page.
          meta={
            profile.scoredCalls === 0
              ? 'No call here carries a score'
              : `${String(profile.scoredCalls)} of ${String(profile.calls)} calls scored — each one below`
          }
          info={
            <Tooltip>
              <p>
                <b>Why there is no average call quality</b>
              </p>
              Metric 12 is a property of the call and the agent. The Metrics sheet says
              it is never averaged to an employer, product line or broker, so this
              account has no quality score of its own — the per-call scores in the calls
              panel are the figure, and they are not summed into one.
            </Tooltip>
          }
        />
      </BigRow>
    </Panel>
  )
}

/** A count that links to its playbook only when there is something to do. */
function Tile({
  label,
  value,
  issue,
  meta,
}: {
  label: string
  value: number
  issue: 'unresolved' | 'repeat_contact' | 'escalation_missed'
  meta: string
}) {
  return (
    <KpiTile
      label={label}
      value={value === 0 ? '0' : <IssueValue issue={issue}>{String(value)}</IssueValue>}
      meta={<span className="nv-indcount">{meta}</span>}
    />
  )
}

/**
 * "What they call about" — the account's categories, most first.
 *
 * Only the categories this account raised. Unlike the outcome chart, a
 * category nobody called about is not a finding here, and seven near-empty
 * bars would bury the two that matter.
 *
 * `uncategorised` is printed rather than folded away, so the bars can be
 * reconciled against the call count instead of quietly falling short of it.
 */
export function AccountTopics({ profile }: { profile: AccountProfile }) {
  const max = profile.topics[0]?.calls ?? 0

  return (
    <Panel title="What they call about" chip={<EpistemicChip kind="observed" />}>
      {profile.topics.length === 0 ? (
        <Empty title="No calls in this period">
          Widen the period to see what this account calls about.
        </Empty>
      ) : (
        <>
          <ul className="nv-topics">
            {profile.topics.map((topic) => (
              <li key={topic.category}>
                <span>{topic.category}</span>
                <BarCell value={topic.calls} max={max} />
              </li>
            ))}
          </ul>
          {profile.uncategorised > 0 ? (
            <Note>
              {String(profile.uncategorised)} call
              {profile.uncategorised === 1 ? '' : 's'} carried no category and{' '}
              {profile.uncategorised === 1 ? 'is' : 'are'} in none of the bars above.
            </Note>
          ) : null}
        </>
      )}
    </Panel>
  )
}
