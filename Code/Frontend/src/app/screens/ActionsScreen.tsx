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
import { CallList } from '@/shared/design/drawer/Evidence'
import { useDrawer } from '@/shared/design/drawer'
import { Empty, EpistemicChip, FigureValue, Note, Panel } from '@/shared/design/primitives'
import { useFilters } from '@/shared/filters/useFilters'
import { Screen } from '@/shared/screens/Screen'
import { ActionBoardView } from '@/app/screens/actions/ActionBoardView'
import { ActionCardModal } from '@/app/screens/actions/ActionCardModal'
import { ActionComposer } from '@/app/screens/actions/ActionComposer'
import { ActionDialog } from '@/app/screens/actions/ActionDialog'
import { formatDue, severityColor } from '@/app/screens/actions/format'
import '@/app/screens/actions/actionsBoard.css'

type ModalState =
  | { kind: 'card'; actionId: number }
  | { kind: 'composer'; issueKey: string | null; employerRef: string | null }
  | null

type ActionItem = ActionsFindings['items'][number]

export function ActionsScreen() {
  const filters = useFilters()
  const [params, setParams] = useSearchParams()
  const focus = params.get('focus')
  const employerRef = params.get('employer')
  const stage = params.get('stage')

  const findings = useActionsFindings(filters.apiSearch)
  const board = useActionBoard()
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
      lede="Every issue the platform has flagged, with the steps to fix it, who should own it, and how far the work has got."
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

  const measured = board.actions.filter((a) => a.outcome !== null)

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
        <IssuesToActOn findings={findings} exclude={focus} />
      </div>

      {findings.owners.length > 0 ? (
        <div className="nv-c6">
          <OwnerWorkloadPanel owners={findings.owners} />
        </div>
      ) : null}

      {findings.controlExceptions.length > 0 ? (
        <div className="nv-c6">
          <ControlExceptionsPanel
            exceptions={findings.controlExceptions}
            caveat={findings.controlDenominatorCaveat}
          />
        </div>
      ) : null}

      <div className="nv-c12">
        <DidItWorkPanel panel={findings.didItWork} />
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

      {measured.length > 0 ? (
        <div className="nv-c12">
          <Panel
            title="What was done, and what changed"
            sub="Outcomes recorded for actions that reached a closed lane."
            chip={<EpistemicChip kind="derived" />}
          >
            <ul className="nv-movements">
              {measured.map((action) => (
                <li key={action.id}>
                  <span className="nv-nm">{action.title}</span>
                  <span>{action.actionTaken ?? '–'}</span>
                  <span>{action.outcome}</span>
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      ) : null}

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
            candidateCallIds={
              findings.items.find((item) => item.signal.code === modal.issueKey)?.callIds ?? []
            }
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
  const { open: openDrawer } = useDrawer()

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
  const item = findings.items.find((candidate) => candidate.signal.code === issueKey)
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
                {item?.calls ?? 0}
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
            {!pb.reviewed ? (
              <Note>
                Recommendation, not policy: these steps have not been reviewed by the owning team.
              </Note>
            ) : null}

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
            <h3>Evidence</h3>
            {item && item.callIds.length > 0 ? (
              <>
                <p>
                  {item.calls} {item.calls === 1 ? 'call' : 'calls'} in this period.
                </p>
                <button
                  type="button"
                  className="nv-btn"
                  onClick={() => {
                    openDrawer({
                      title: pb.label,
                      chip: 'observed',
                      body: <CallList callIds={item.callIds} />,
                    })
                  }}
                >
                  See the calls behind it
                </button>
              </>
            ) : (
              <Empty title="No call evidence in this period">
                This issue is not signal-based, or nothing fired in the current filters.
              </Empty>
            )}
          </div>
        </div>
      </section>
    </div>
  )
}

function IssuesToActOn({ findings, exclude }: { findings: ActionsFindings; exclude: string | null }) {
  const items = findings.items.filter((item) => item.signal.code !== exclude)

  return (
    <Panel
      title={exclude !== null ? 'Other issues to act on' : 'Issues to act on'}
      sub="Most urgent first. Select an issue to see the steps and the evidence."
      chip={<EpistemicChip kind="recommendation" />}
    >
      {items.length === 0 ? (
        <Empty title="Nothing to act on">No signal was raised in this scope.</Empty>
      ) : (
        <ul className="nv-attn">
          {items.map((item) => (
            <AttnRow key={item.signal.code} item={item} />
          ))}
        </ul>
      )}
    </Panel>
  )
}

function AttnRow({ item }: { item: ActionItem }) {
  const inner = (
    <>
      <span className="nv-dot" style={{ background: severityColor(item.severity.code) }} />
      <span>
        <b>{item.signal.label}</b>
      </span>
      <span className="nv-n">{item.calls}</span>
      <span className="nv-own">{item.ownerTeam}</span>
      <span className="nv-go" aria-hidden="true">
        →
      </span>
    </>
  )
  if (isIssueKey(item.signal.code)) {
    return (
      <li>
        <Link to={issueHref(item.signal.code)}>{inner}</Link>
      </li>
    )
  }
  return (
    <li>
      <span className="nv-attn-static">{inner}</span>
    </li>
  )
}

function OwnerWorkloadPanel({ owners }: { owners: ActionsFindings['owners'] }) {
  return (
    <Panel
      title="By team"
      sub="The same items, routed. Teams with critical work first."
      chip={<EpistemicChip kind="observed" />}
    >
      <ul className="nv-movements">
        {owners.map((owner) => (
          <li key={owner.ownerTeam}>
            <span className="nv-nm">{owner.ownerTeam}</span>
            <span>{owner.calls} calls</span>
            {owner.critical > 0 ? <span className="nv-worse">{owner.critical} critical</span> : null}
          </li>
        ))}
      </ul>
    </Panel>
  )
}

function ControlExceptionsPanel({
  exceptions,
  caveat,
}: {
  exceptions: ActionsFindings['controlExceptions']
  caveat: string
}) {
  return (
    <Panel
      title="Compliance control exceptions"
      sub="Metric 7, by type. Never blended into one compliance rate."
      chip={<EpistemicChip kind="observed" />}
    >
      <ul className="nv-movements">
        {exceptions.map((exception) => (
          <li key={exception.exceptionType.code}>
            <span className="nv-nm">{exception.exceptionType.label}</span>
            <FigureValue figure={exception.figure} format={(v) => `${String(Math.round(v * 100))}%`} />
          </li>
        ))}
      </ul>
      <Note>{caveat}</Note>
    </Panel>
  )
}

function DidItWorkPanel({ panel }: { panel: ActionsFindings['didItWork'] }) {
  return (
    <Panel title={panel.question} chip={<EpistemicChip kind="inference" />}>
      <Note>{panel.why}</Note>
      <Note>{panel.unlockedBy}</Note>
    </Panel>
  )
}
