/**
 * The action board: KPI tiles, the stage strip, and the board / table toggle.
 *
 * The seven lanes the prototype hardcodes as `LANES` are `board.lanes` here
 * — read from `GET /insights/actions/board`, which reads them from
 * `config/action_lifecycle.yaml`. Nothing in this file names a lane by code;
 * a lifecycle change on the server draws a different board on the next
 * fetch, not a frontend rebuild.
 */

import { Empty, KpiTile } from '@/shared/design/primitives'
import type { Action, ActionBoard, Lane } from '@/shared/api/actionBoard'
import { formatDue, initials, laneColors, priorityColor } from '@/app/screens/actions/format'
import { findLane } from '@/app/screens/actions/lifecycle'

export function ActionBoardView({
  board,
  view,
  onView,
  stage,
  onStage,
  onOpenCard,
  onNewCard,
}: {
  board: ActionBoard
  view: 'board' | 'table'
  onView: (view: 'board' | 'table') => void
  stage: string | null
  onStage: (code: string | null) => void
  onOpenCard: (id: number) => void
  onNewCard: () => void
}) {
  const colors = laneColors(board.lanes)
  const counts = new Map(
    board.lanes.map((lane) => [lane.code, board.actions.filter((a) => a.status === lane.code).length]),
  )
  const openActions = board.actions.filter((a) => findLane(board.lanes, a.status)?.open)
  const overdue = board.actions.filter((a) => a.pastDue)
  const highOpen = openActions.filter((a) => a.priority === 'high')
  const measured = board.actions.filter((a) => a.outcome !== null)
  const visible = stage === null ? board.actions : board.actions.filter((a) => a.status === stage)

  return (
    <>
      <div className="nv-bigrow">
        <KpiTile
          label="Open actions"
          value={String(openActions.length)}
          meta={
            <span className="nv-indcount">
              of {board.actions.length} raised
            </span>
          }
        />
        <KpiTile
          label="Past due"
          value={String(overdue.length)}
          meta={<span className="nv-indcount">past the due date</span>}
          tone={overdue.length > 0 ? 'hot' : 'plain'}
        />
        <KpiTile
          label="High priority open"
          value={String(highOpen.length)}
          meta={<span className="nv-indcount">of {openActions.length} open</span>}
        />
        <KpiTile
          label="Outcome measured"
          value={String(measured.length)}
          meta={<span className="nv-indcount">of {board.actions.length} actions</span>}
        />
      </div>

      <section className="nv-panel">
        <header>
          <div>
            <h2>Action board</h2>
          </div>
          <div className="nv-seg" role="group" aria-label="View">
            <button type="button" aria-pressed={view === 'board'} onClick={() => { onView('board') }}>
              Board
            </button>
            <button type="button" aria-pressed={view === 'table'} onClick={() => { onView('table') }}>
              Table
            </button>
          </div>
        </header>
        <p className="nv-sub">{board.trustNote}</p>

        <div className="nv-boardbar">
          <p className="nv-sub" style={{ margin: 0 }}>
            Select a stage to filter. Select a card to work on it.
          </p>
          <div className="nv-fbtns">
            {stage !== null ? (
              <button type="button" className="nv-btn" onClick={() => { onStage(null) }}>
                Show all {board.actions.length} actions
              </button>
            ) : null}
            <button type="button" className="nv-btn" onClick={onNewCard}>
              + New action
            </button>
          </div>
        </div>

        <div className="nv-stages">
          {board.lanes.map((lane) => {
            const n = counts.get(lane.code) ?? 0
            if (n === 0) return null
            return (
              <button
                key={lane.code}
                type="button"
                aria-pressed={stage === lane.code}
                style={{ flex: n, background: colors.get(lane.code) }}
                title={`${lane.label}: ${String(n)}`}
                onClick={() => { onStage(stage === lane.code ? null : lane.code) }}
              >
                {n}
              </button>
            )
          })}
        </div>

        <div className="nv-stagechips" role="group" aria-label="Filter by stage">
          <button type="button" aria-pressed={stage === null} onClick={() => { onStage(null) }}>
            All <b>{board.actions.length}</b>
          </button>
          {board.lanes.map((lane) => (
            <button
              key={lane.code}
              type="button"
              aria-pressed={stage === lane.code}
              onClick={() => { onStage(stage === lane.code ? null : lane.code) }}
            >
              <i style={{ background: colors.get(lane.code) }} />
              {lane.label} <b>{counts.get(lane.code) ?? 0}</b>
            </button>
          ))}
        </div>

        {view === 'board' ? (
          <BoardKanban lanes={board.lanes} actions={visible} colors={colors} onOpenCard={onOpenCard} />
        ) : (
          <WorkTable actions={visible} onOpenCard={onOpenCard} />
        )}
      </section>
    </>
  )
}

function BoardKanban({
  lanes,
  actions,
  colors,
  onOpenCard,
}: {
  lanes: Lane[]
  actions: Action[]
  colors: Map<string, string>
  onOpenCard: (id: number) => void
}) {
  return (
    <div className="nv-kanban">
      {lanes.map((lane) => {
        const items = actions.filter((a) => a.status === lane.code)
        return (
          <div className="nv-lane" key={lane.code}>
            <h3>
              <span>
                <i style={{ background: colors.get(lane.code) }} />
                {lane.label}
              </span>
              <b>{items.length}</b>
            </h3>
            <div className="nv-lane-body">
              {items.length === 0 ? (
                <p className="nv-lane-empty">Nothing here</p>
              ) : (
                items.map((action) => (
                  <BoardCard
                    key={action.id}
                    action={action}
                    lane={lane}
                    onOpen={() => { onOpenCard(action.id) }}
                  />
                ))
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

function BoardCard({
  action,
  lane,
  onOpen,
}: {
  action: Action
  lane: Lane
  onOpen: () => void
}) {
  const borderColor = action.pastDue ? 'var(--critical)' : lane.open ? undefined : 'var(--good)'
  return (
    <button
      type="button"
      className="nv-card"
      style={borderColor ? { borderLeftColor: borderColor } : undefined}
      onClick={onOpen}
    >
      <span className="nv-card-labels">
        <i style={{ background: priorityColor(action.priority) }} title={`${action.priority} priority`} />
      </span>
      <span className="nv-card-title">{action.title}</span>
      <span className="nv-card-foot">
        <span className="nv-card-badges">
          {action.due ? (
            <span className={`nv-due${action.pastDue ? ' nv-late' : ''}${!lane.open ? ' nv-done' : ''}`}>
              ◷ {formatDue(action.due)}
            </span>
          ) : null}
          {action.callIds.length > 0 ? (
            <span className="nv-cardcount" title="Calls behind it">
              ☏ {action.callIds.length}
            </span>
          ) : null}
          {action.outcome ? (
            <span className="nv-cardcount nv-ok" title="Outcome recorded">
              ✓
            </span>
          ) : null}
        </span>
        <span className="nv-avatar" title={action.owner ?? 'Unassigned'}>
          {initials(action.owner)}
        </span>
      </span>
      <span className="nv-card-team">{action.ownerTeam}</span>
    </button>
  )
}

/**
 * The board as a table. Deliberately not `DataTable`: that primitive's rows
 * navigate to a route by `href`, and a card has no route of its own — it
 * opens a modal. So this is a plain table with its own click and keyboard
 * handling, the same shape `DataTable` uses internally.
 */
function WorkTable({ actions, onOpenCard }: { actions: Action[]; onOpenCard: (id: number) => void }) {
  if (actions.length === 0) {
    return <Empty title="Nothing at this stage">Choose a different stage, or clear the filter.</Empty>
  }

  return (
    <div className="nv-tblwrap nv-worktable">
      <table className="nv-risktable">
        <caption className="nv-visually-hidden">The action board, as a table</caption>
        <thead>
          <tr>
            <th scope="col">Action</th>
            <th scope="col">Owner</th>
            <th scope="col">Due</th>
            <th scope="col">Status</th>
            <th scope="col">Outcome</th>
          </tr>
        </thead>
        <tbody>
          {actions.map((action) => (
            <tr
              key={action.id}
              className="nv-clickable"
              tabIndex={0}
              onClick={() => { onOpenCard(action.id) }}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  onOpenCard(action.id)
                }
              }}
            >
              <td>
                <span className="nv-nm">{action.title}</span>
                <br />
                <span className="nv-indcount">{action.evidence}</span>
              </td>
              <td>
                <span className="nv-avatar">{initials(action.owner)}</span> {action.ownerTeam}
                <br />
                <span className="nv-indcount">{action.owner ?? 'unassigned'}</span>
              </td>
              <td>
                {action.due ? (
                  <span className={`nv-due${action.pastDue ? ' nv-late' : ''}`}>
                    {formatDue(action.due)}
                  </span>
                ) : (
                  '–'
                )}
              </td>
              <td>{action.statusLabel}</td>
              <td>{action.outcome ?? 'Not yet measured'}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
