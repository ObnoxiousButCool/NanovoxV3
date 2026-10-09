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
import type { Action } from '@/shared/api/actionBoard'
import { useCalls } from '@/shared/api/insights'
import type { AccountProfile, CallRow } from '@/shared/api/insights'
import { useOpenCall } from '@/shared/calls/openCall'
import { IssueCue, IssueValue } from '@/shared/actions/IssueLink'
import { BarCell } from '@/shared/design/charts'
import { BigRow, DataTable, Empty, EpistemicChip, KpiTile, Named, Note, Panel, Withheld } from '@/shared/design/primitives'
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
  const openCall = useOpenCall()

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
          {/* The same scroller `DataTable` puts round its own table. The
              cells are nowrap, so without it the table sets the width of the
              page and a phone gets a horizontal scrollbar on the whole
              document rather than on the table. */}
          <div className="nv-tblwrap">
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
                      openCall(call.reference)
                    }}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Panel>
  )
}

function CallLine({ call, onOpen }: { call: CallRow; onOpen: () => void }) {
  return (
    <tr
      className="nv-clickable"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onOpen()
        }
      }}
    >
      <td>
        {call.reference}
        <small>{call.occurredOn}</small>
      </td>
      <td>
        {/* The reference where reference data names nobody: a gap in the
            Member and Contact sheets, not an anonymous caller, and the
            reference is still how the reader looks them up. */}
        <Named name={call.callerName} reference={call.callerRef} mask fallback="not recorded" />
        <small>{call.callerKind ?? 'unknown caller type'}</small>
      </td>
      <td>
        {call.category ?? 'no category'}
        <small>{call.touchpoint ?? 'no touchpoint'}</small>
      </td>
      <td>
        {/* The word carries the meaning, never the colour alone. */}
        {call.outcome ? call.outcome.label : 'not recorded'}
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

/**
 * One card's heading on an account page: `Revenue opportunity — 4 / 39 calls`.
 *
 * The card's stored title already reads "Revenue opportunity — 39 calls",
 * because a seeded action counts every call that raised its signal: one
 * card, one owner team, worked once. Under a heading reading "Actions for
 * this account" that number is read as the account's, and 179 on an account
 * with 18 calls is out by an order of magnitude.
 *
 * So the count becomes a ratio in the same place the title carried it,
 * rather than a second line repeating the denominator. The name comes from
 * the server as `label` — cutting "— 39 calls" back off the title here
 * would be string surgery on prose the server wrote, and it would mangle a
 * hand-raised action whose own title ended in the same shape.
 *
 * Falls back to the title whenever either piece is missing: an unscoped
 * board sends no share, and there is no ratio to state without one.
 */
function CardHeading({ action }: { action: Action }) {
  const share = action.callsOnAccount
  if (share === null || share === undefined || action.label === null || action.label === undefined) {
    return <>{action.title}</>
  }
  const cited = action.callIds.length
  return (
    <span title="Calls on this account, of the calls behind this action">
      {action.label} — {share} / {cited} {cited === 1 ? 'call' : 'calls'}
    </span>
  )
}

export function AccountActions({ employerRef }: { employerRef: string }) {
  // Scoped by the server. It was scoped here, against `risk.evidence` --
  // the calls behind metric 10's *fired conditions*, not the account's
  // calls -- so an account with nothing flagged matched nothing at all and
  // the panel below reported that none of its calls had needed an action.
  //
  // The board now takes the shared filter set rather than a bare employer
  // reference, and `employer` is one of those filters, so this account page
  // asks for its own account the same way the filter bar would.
  const { data, isPending, error } = useActionBoard(
    new URLSearchParams({ employer: employerRef }).toString(),
  )

  const rows: Row[] = (data?.actions ?? []).map((action) => ({
    key: String(action.id),
    cells: [
      <>
        <CardHeading action={action} />
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
export function AccountTiles({
  profile,
  employerRef,
}: {
  profile: AccountProfile
  employerRef: string
}) {
  return (
    <Panel
      title="This account's calls"
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
          employerRef={employerRef}
          tone="warm"
          value={profile.unresolved}
          issue="unresolved"
          meta={`of ${String(profile.calls)} calls`}
        />
        <Tile
          label="Repeat contacts"
          employerRef={employerRef}
          tone="warm"
          value={profile.repeatContacts}
          issue="repeat_contact"
          meta="unresolved, and they came back"
        />
        <Tile
          label="Escalations missed"
          employerRef={employerRef}
          tone="hot"
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
        />
      </BigRow>
    </Panel>
  )
}

/**
 * A count that links to its playbook only when there is something to do.
 *
 * `NV.tile` in the prototype does three things to a tile carrying an issue
 * and we were doing one. It links the value, **and** tints the tile with an
 * inset bar, **and** puts "What to do →" underneath. The tint is the part a
 * reader sees first — a page of flat tiles gives them nothing to look at
 * first, which is the whole job of a tile strip.
 *
 * Zero takes none of it. A tile at zero is a good outcome, not a muted
 * warning, and offering a playbook for a problem nobody has is noise.
 */
function Tile({
  label,
  value,
  issue,
  meta,
  employerRef,
  tone,
}: {
  label: string
  value: number
  issue: 'unresolved' | 'repeat_contact' | 'escalation_missed'
  meta: string
  employerRef: string
  /** `hot` for a missed escalation, `warm` for the rest — the prototype's
      own split, and the reason it is passed rather than derived. */
  tone: 'hot' | 'warm'
}) {
  const raised = value > 0
  return (
    <KpiTile
      label={label}
      tone={raised ? tone : 'plain'}
      value={
        raised ? (
          <IssueValue issue={issue} tone={tone} scope={{ employer: employerRef }}>
            {String(value)}
          </IssueValue>
        ) : (
          '0'
        )
      }
      meta={<span className="nv-indcount">{meta}</span>}
      todo={
        raised ? <IssueCue issue={issue} scope={{ employer: employerRef }} /> : undefined
      }
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
        </>
      )}
    </Panel>
  )
}
