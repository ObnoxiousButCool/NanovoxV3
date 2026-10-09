/**
 * `/actions` — "What should we do next?" The action centre's write path
 * (Revised plan Phase 4, decision D6).
 *
 * ## Two different objects, both on this screen
 *
 * `GET /insights/actions` is a **finding**: what the calls say, with no
 * status. `GET /insights/actions/board` is the **persisted record** of what
 * somebody is doing about it. The backend keeps them apart on purpose —
 * merging them is how a finding acquires a fake status — so this screen
 * reads both and never lets one stand in for the other: the focused issue
 * and "issues to act on" come from the findings query, the board and its
 * cards come from the board query.
 *
 * ## The panels, and the ones that are not here
 *
 * Three, in `actions.html`'s order: the tiles, the issues list and the
 * board. Two that used to sit between them are gone — a "By team" routing
 * panel and an aggregated compliance-exceptions panel. The prototype has
 * neither, and neither loses anything: the owning team is on every issue
 * row and every card already, and metric 7 is reported per agent on
 * `/agents` and per call on `/calls`, where it is attached to something a
 * reader can open.
 *
 * ## "Did it work?" is not drawn
 *
 * Insight 22's withheld panel used to close the screen. It is the one
 * withheld panel that is not a schema gap: `withheld.py` says the others
 * need a field that does not exist and "no amount of corpus growth changes
 * any of them", while 22 only wants a second batch — a window after a
 * logged remediation. A panel saying "ask again when more data arrives" is
 * a different thing from one saying "this cannot be answered", and only the
 * second earns permanent space on the screen.
 *
 * The server still sends `findings.didItWork` and the other two panels still
 * render. Nothing about the withheld mechanism changed; this screen stopped
 * drawing one of its three.
 *
 * ## Every row leads to steps
 *
 * `findings.issues` is keyed by playbook, so a row's `key` is exactly what
 * `?focus=` takes. That is a reversal of conflict **C9** for this screen,
 * the same one `/accounts` needed: shaped by the page it mirrors rather
 * than by whichever endpoint happened to be built first.
 *
 * ## The lifecycle is configuration, not a constant here
 *
 * The prototype hardcodes seven lanes as a JS array. This reads
 * `board.lanes`, sent by the server from `config/action_lifecycle.yaml`, so
 * a lifecycle change lands on the next fetch rather than a rebuild. See
 * `@/app/screens/actions/lifecycle` for the rest of that rule: nothing here
 * asks "is this lane called `completed`" — only whether it is still open,
 * and what it requires.
 *
 * ## Nothing here writes to `localStorage`
 *
 * Every mutation — create, tick, move, assign, log, record — is a real
 * `POST`/`PATCH` through `@/shared/api/actionBoard`, and the board is
 * refetched afterward. There is no local copy of an action for the same
 * reason the prototype needed one: it had no server. This does.
 */

import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import type { Action, ActionBoard } from '@/shared/api/actionBoard'
import { useAction, useActionBoard } from '@/shared/api/actionBoard'
import { useActionsFindings, useFilterOptions } from '@/shared/api/insights'
import type { ActionsFindings } from '@/shared/api/insights'
import { usePlaybook } from '@/shared/api/playbooks'
import type { IssueKey } from '@/shared/actions/issueHref'
import { ISSUE_KEYS, issueHref } from '@/shared/actions/issueHref'
import { IssueCue } from '@/shared/actions/IssueLink'
import { useOpenCall } from '@/shared/calls/openCall'
import { DataTable, Empty, EpistemicChip, KpiTile, Note, Panel } from '@/shared/design/primitives'
import { useFilters } from '@/shared/filters/useFilters'
import { Screen } from '@/shared/screens/Screen'
import { ActionBoardView } from '@/app/screens/actions/ActionBoardView'
import { ActionCardModal } from '@/app/screens/actions/ActionCardModal'
import { ActionComposer } from '@/app/screens/actions/ActionComposer'
import { ActionDialog } from '@/app/screens/actions/ActionDialog'
import { formatDue, severityColor } from '@/app/screens/actions/format'
import { findLane } from '@/app/screens/actions/lifecycle'
import '@/app/screens/actions/actionsBoard.css'

type ModalState =
  | { kind: 'card'; actionId: number }
  | { kind: 'composer'; issueKey: string | null; employerRef: string | null }
  | null

type Issue = ActionsFindings['issues'][number]

//: The prototype's own cut of the "where it shows up" table.
const SHOWN_ACCOUNTS = 8

export function ActionsScreen() {
  const filters = useFilters()
  const [params, setParams] = useSearchParams()
  const focus = params.get('focus')
  const employerRef = params.get('employer')
  const stage = params.get('stage')

  const findings = useActionsFindings(filters.apiSearch)
  // The same query string the findings panel is given, so the board and
  // the issues beside it cannot be answering different questions.
  const board = useActionBoard(filters.apiSearch)
  const options = useFilterOptions(filters.apiSearch)
  const employerNames = new Map(
    (options.data?.employers ?? []).map((employer) => [employer.ref, employer.name]),
  )

  const [view, setView] = useState<'board' | 'table'>('board')
  const [modal, setModal] = useState<ModalState>(null)

  const isPending = findings.isPending || board.isPending
  const error = findings.error ?? board.error

  const setStage = (code: string | null) => {
    setParams(
      (previous) => {
        const next = new URLSearchParams(previous)
        if (code === null) next.delete('stage')
        else next.set('stage', code)
        return next
      },
      { replace: false },
    )
  }

  return (
    <Screen
      title="What should we do next?"
      scope={findings.data?.scope}
      isPending={isPending}
      error={error}
    >
      {findings.data === undefined || board.data === undefined ? null : (
        <ActionsBody
          findings={findings.data}
          board={board.data}
          employerNames={employerNames}
          focus={focus}
          employerRef={employerRef}
          stage={stage}
          onStage={setStage}
          view={view}
          onView={setView}
          modal={modal}
          onOpenCard={(actionId) => { setModal({ kind: 'card', actionId }) }}
          onOpenComposer={(issueKey, employer) => {
            setModal({ kind: 'composer', issueKey, employerRef: employer })
          }}
          onCloseModal={() => { setModal(null) }}
        />
      )}
    </Screen>
  )
}

function ActionsBody({
  findings,
  board,
  employerNames,
  focus,
  employerRef,
  stage,
  onStage,
  view,
  onView,
  modal,
  onOpenCard,
  onOpenComposer,
  onCloseModal,
}: {
  findings: ActionsFindings
  board: ActionBoard
  employerNames: Map<string, string>
  focus: string | null
  employerRef: string | null
  stage: string | null
  onStage: (code: string | null) => void
  view: 'board' | 'table'
  onView: (view: 'board' | 'table') => void
  modal: ModalState
  onOpenCard: (actionId: number) => void
  onOpenComposer: (issueKey: string | null, employerRef: string | null) => void
  onCloseModal: () => void
}) {
  const employerName = employerRef ? (employerNames.get(employerRef) ?? employerRef) : null

  const modalActionId = modal?.kind === 'card' ? modal.actionId : null
  const boardAction = board.actions.find((a) => a.id === modalActionId)
  // The board is invalidated after every write and after a create, so it is
  // the usual source. Right after a create the invalidated board may not
  // have refetched yet, so this fills the one gap that leaves.
  const fallback = useAction(boardAction === undefined ? modalActionId : null)
  const modalAction = boardAction ?? fallback.data

  const ownerTeams = [...new Set(board.actions.map((a) => a.ownerTeam).filter(Boolean))].sort()
  const owners = [
    ...new Set(board.actions.map((a) => a.owner).filter((v): v is string => v !== null)),
  ].sort()

  return (
    <div className="nv-grid">
      {focus !== null ? (
        <FocusPanel
          issueKey={focus}
          employerRef={employerRef}
          employerName={employerName}
          findings={findings}
          boardActions={board.actions}
          onOpenComposer={onOpenComposer}
        />
      ) : null}

      <div className="nv-c12">
        <ActionTiles board={board} />
      </div>

      <div className="nv-c12">
        <IssuesToActOn findings={findings} exclude={focus} employerRef={employerRef} />
      </div>

      <div className="nv-c12">
        <ActionBoardView
          board={board}
          view={view}
          onView={onView}
          stage={stage}
          onStage={onStage}
          onOpenCard={onOpenCard}
          onNewCard={() => { onOpenComposer(null, employerRef) }}
        />
      </div>

      <ActionDialog open={modal !== null} onClose={onCloseModal}>
        {modal?.kind === 'card' && modalAction ? (
          <ActionCardModal
            key={modalAction.id}
            action={modalAction}
            lanes={board.lanes}
            employerName={
              modalAction.employerRef ? (employerNames.get(modalAction.employerRef) ?? null) : null
            }
            onClose={onCloseModal}
          />
        ) : null}
        {modal?.kind === 'composer' ? (
          <ActionComposer
            lanes={board.lanes}
            issueKey={modal.issueKey}
            employerRef={modal.employerRef}
            employerName={
              modal.employerRef ? (employerNames.get(modal.employerRef) ?? modal.employerRef) : null
            }
            candidateCallIds={(() => {
              const issue = findings.issues.find((row) => row.key === modal.issueKey)
              return issue?.unit === 'calls' ? issue.references : []
            })()}
            ownerTeams={ownerTeams}
            owners={owners}
            onClose={onCloseModal}
            onCreated={(created: Action) => { onOpenCard(created.id) }}
          />
        ) : null}
      </ActionDialog>
    </div>
  )
}

/** An issue key the action view has a playbook for. */
function isIssueKey(code: string): code is IssueKey {
  return (ISSUE_KEYS as readonly string[]).includes(code)
}

function FocusPanel({
  issueKey,
  employerRef,
  employerName,
  findings,
  boardActions,
  onOpenComposer,
}: {
  issueKey: string
  employerRef: string | null
  employerName: string | null
  findings: ActionsFindings
  boardActions: Action[]
  onOpenComposer: (issueKey: string | null, employerRef: string | null) => void
}) {
  const playbook = usePlaybook(issueKey)

  if (playbook.isPending) {
    return (
      <div className="nv-c12">
        <Note>Loading the playbook for {issueKey}…</Note>
      </div>
    )
  }

  if (playbook.isError) {
    return (
      <div className="nv-c12">
        <Empty title="No playbook for this issue">
          {issueKey} does not resolve to a known or currently offered issue. It may have been
          held back, or the link is out of date.
        </Empty>
      </div>
    )
  }

  const pb = playbook.data
  const issue = findings.issues.find((candidate) => candidate.key === issueKey)
  const related = boardActions
    .filter(
      (action) =>
        action.issueKey === issueKey || (employerRef !== null && action.employerRef === employerRef),
    )
    .slice(0, 6)

  return (
    <div className="nv-c12">
      <section className={`nv-focus nv-lvl-${pb.severity}`}>
        <div className="nv-focus-head">
          <div>
            <span className="nv-eyebrow">
              What to do next{employerName ? ` · ${employerName}` : ''}
            </span>
            <h2>
              <span className="nv-n" style={{ color: pb.severity === 'high' ? 'var(--critical)' : 'var(--serious)' }}>
                {issue?.count ?? 0}
              </span>
              {pb.label}
            </h2>
            <p>
              <b>{pb.meaning}</b> {pb.why}
            </p>
          </div>
          <div className="nv-fbtns">
            <button
              type="button"
              className="nv-btn"
              onClick={() => { onOpenComposer(issueKey, employerRef) }}
            >
              Raise an action
            </button>
            <Link className="nv-btn" to="/actions">
              All issues
            </Link>
          </div>
        </div>
        <div className="nv-focus-body">
          <div>
            <h3>Recommended steps</h3>
            <ol className="nv-steps">
              {pb.steps.map((step) => (
                <li key={step}>
                  <span>{step}</span>
                </li>
              ))}
            </ol>
            <p className="nv-ownerline">
              Suggested owner: <b>{pb.ownerTeam}</b>
            </p>

            {related.length > 0 ? (
              <>
                <h3 style={{ marginTop: 20 }}>Already in progress</h3>
                <ul className="nv-indlist">
                  {related.map((action) => (
                    <li key={action.id}>
                      <span className="nv-t">
                        {action.title}
                        <small>
                          {action.ownerTeam}
                          {action.due ? ` · due ${formatDue(action.due)}` : ''}
                        </small>
                      </span>
                      <span>{action.statusLabel}</span>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <Note>No action has been raised for this yet.</Note>
            )}
          </div>
          <div>
            <WhereItShowsUp issue={issue} label={pb.label} />
          </div>
        </div>
      </section>
    </div>
  )
}

/**
 * "Where it shows up" — the accounts an issue landed on.
 *
 * `actions.html`'s right-hand column, and the reason the focused view is
 * worth arriving at: a count tells the reader there is a problem, and this
 * tells them whose desk it is on. Ranked the prototype's way, most calls
 * first and then soonest renewal, because two accounts with the same
 * problem are not equally urgent when one of them renews next month.
 *
 * The prototype's Risk column is gone. **D12** removed the four-level band
 * it showed, and there is no replacement for it here — the flag is a
 * yes/no that this screen already lists as its own issue.
 */
function WhereItShowsUp({ issue, label }: { issue: Issue | undefined; label: string }) {
  const openCall = useOpenCall()

  if (issue === undefined || issue.accounts.length === 0) {
    return (
      <>
        <h3>Where it shows up</h3>
        <Empty title="Nothing to show for this issue">
          {issue?.computable === false
            ? issue.unavailableBecause
            : 'Nothing fired in the current filters.'}
        </Empty>
      </>
    )
  }

  const accounts = issue.accounts
  const shown = accounts.slice(0, SHOWN_ACCOUNTS)
  const isCalls = issue.unit === 'calls'
  const counted = issue.count ?? 0

  return (
    <>
      <h3>Where it shows up</h3>
      <p className="nv-lede">
        {isCalls
          ? `${String(counted)} ${counted === 1 ? 'call' : 'calls'} across ${String(accounts.length)} ${accounts.length === 1 ? 'account' : 'accounts'}.`
          : `${String(counted)} ${counted === 1 ? 'account' : 'accounts'}.`}{' '}
        Select an account for its full picture{isCalls ? ', or a call for the transcript' : ''}.
      </p>
      <DataTable
        caption={`The accounts behind ${label}`}
        columns={[
          { key: 'account', header: 'Account' },
          { key: 'calls', header: 'Calls', numeric: true },
          { key: 'renews', header: 'Renews' },
        ]}
        rows={shown.map((account) => ({
          key: account.employerRef,
          href: `/accounts/${account.employerRef}`,
          cells: [
            <>
              <span className="nv-nm">{account.name}</span>
              <small>
                {account.brokerRef} · {account.region}
              </small>
            </>,
            account.calls,
            <>
              {account.renewalMonth || '–'}
              <RenewalCountdown months={account.renewalInMonths} />
            </>,
          ],
        }))}
      />
      {accounts.length > shown.length ? (
        <p className="nv-lede">and {accounts.length - shown.length} more.</p>
      ) : null}
      {isCalls && issue.references.length > 0 ? (
        <div className="nv-callchips">
          {issue.references.map((reference) => (
            <button
              key={reference}
              type="button"
              className="nv-callchip"
              onClick={() => {
                // Straight to the call. Wrapping a single reference in a
                // one-item evidence list was a drawer frame that existed
                // only to be clicked through.
                openCall(reference)
              }}
            >
              {reference}
            </button>
          ))}
        </div>
      ) : null}
    </>
  )
}

/**
 * How many months to the renewal, under the month itself.
 *
 * `null` renders nothing rather than a dash: the month above is still
 * true, and a dash here would suggest the renewal itself was unknown.
 */
function RenewalCountdown({ months }: { months: number | null }) {
  if (months === null) return null
  return (
    <small className="nv-figsub">
      {months === 0 ? 'this month' : `in ${String(months)} month${months === 1 ? '' : 's'}`}
    </small>
  )
}

/**
 * The four tiles the prototype puts at the top of the page.
 *
 * They read the board rather than the findings, because all four are
 * questions about the work — how much is open, how much is late — and none
 * of them is a question about the calls. Only the overdue tile offers a
 * route onward, and only when there is something at the other end of it.
 */
function ActionTiles({ board }: { board: ActionBoard }) {
  const open = board.actions.filter((a) => findLane(board.lanes, a.status)?.open)
  const overdue = board.actions.filter((a) => a.pastDue)
  const highOpen = open.filter((a) => a.priority === 'high')
  const measured = board.actions.filter((a) => a.outcome !== null)
  const raised = board.actions.length

  return (
    <div className="nv-bigrow">
      <KpiTile
        label="Open actions"
        value={String(open.length)}
        meta={
          <span className="nv-indcount">
            {raised > 0 ? `${String(Math.round((open.length / raised) * 100))}% of ` : 'of '}
            {raised} raised
          </span>
        }
        tone={open.length > 0 ? 'warm' : 'plain'}
      />
      <KpiTile
        label="Overdue"
        value={String(overdue.length)}
        meta={<span className="nv-indcount">past the due date</span>}
        tone={overdue.length > 0 ? 'hot' : 'plain'}
        todo={overdue.length > 0 ? <IssueCue issue="overdue" /> : undefined}
      />
      <KpiTile
        label="High priority open"
        value={String(highOpen.length)}
        meta={<span className="nv-indcount">of {open.length} open</span>}
        tone={highOpen.length > 0 ? 'hot' : 'plain'}
      />
      <KpiTile
        label="Outcome measured"
        value={String(measured.length)}
        meta={<span className="nv-indcount">of {raised} actions</span>}
        // The gap worth flagging is zero coverage, not partial coverage: a
        // team that has measured even one outcome is doing the thing this
        // tile checks for, so only "raised actions and nobody has recorded
        // whether any of them worked" gets the accent.
        tone={raised > 0 && measured.length === 0 ? 'warm' : 'plain'}
      />
    </div>
  )
}

/**
 * "Issues to act on" — the screen's front door.
 *
 * Every row is a playbook key, which is what makes every row a link. The
 * list used to be built from the `items` array, which is keyed by
 * `SignalType`: eleven of its twelve rows resolved to no playbook and so
 * rendered as a number with nothing behind it, on a screen whose whole
 * claim is that a number comes with the steps to fix it.
 */
function IssuesToActOn({
  findings,
  exclude,
  employerRef,
}: {
  findings: ActionsFindings
  exclude: string | null
  employerRef: string | null
}) {
  const issues = findings.issues.filter((issue) => issue.key !== exclude)
  // The prototype's own cut: eight rows, then a disclosure. Long enough to
  // be the day's work, short enough that the board below it is still on
  // the screen.
  const shown = issues.slice(0, 8)
  const rest = issues.slice(8)

  return (
    <Panel
      title={exclude !== null ? 'Other issues to act on' : 'Issues to act on'}
      chip={<EpistemicChip kind="recommendation" />}
    >
      {issues.length === 0 ? (
        <Empty title="Nothing to act on">Nothing fired in the current filters.</Empty>
      ) : (
        <>
          <ul className="nv-attn">
            {shown.map((issue) => (
              <AttnRow key={issue.key} issue={issue} employerRef={employerRef} />
            ))}
          </ul>
          {rest.length > 0 ? (
            <details className="nv-more">
              <summary>{rest.length} more issues</summary>
              <ul className="nv-attn">
                {rest.map((issue) => (
                  <AttnRow key={issue.key} issue={issue} employerRef={employerRef} />
                ))}
              </ul>
            </details>
          ) : null}
        </>
      )}
    </Panel>
  )
}

function AttnRow({ issue, employerRef }: { issue: Issue; employerRef: string | null }) {
  const inner = (
    <>
      <span className="nv-dot" style={{ background: severityColor(issue.severity) }} />
      <span>
        <b>{issue.label}</b>
        <small>{issue.computable ? issue.meaning : issue.unavailableBecause}</small>
      </span>
      {/* A key with no count shows no number. An em dash is not a zero and
          does not read as one, which "0" here would. */}
      <span className="nv-n">{issue.count === null ? '—' : issue.count}</span>
      <span className="nv-own">{issue.ownerTeam}</span>
      <span className="nv-go" aria-hidden="true">
        →
      </span>
    </>
  )
  if (!isIssueKey(issue.key)) {
    return (
      <li>
        <span className="nv-attn-static">{inner}</span>
      </li>
    )
  }
  return (
    <li>
      <Link to={issueHref(issue.key, { employer: employerRef ?? undefined })}>{inner}</Link>
    </li>
  )
}

