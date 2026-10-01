/**
 * Which lane an action is drawn in.
 *
 * Being late is not a status anything sets: the server computes `pastDue`
 * from the due date and leaves the action in the stage it is actually in.
 * So the board's Overdue lane, which `config/action_lifecycle.yaml` does
 * define, matched nothing and printed "Overdue 0" beside a tile counting
 * two genuinely late actions. The prototype has no such split because
 * `overdue` is a real status in its fixture data.
 *
 * Its own module rather than a helper inside the board: three call sites
 * read it — the stage strip's counts, the strip's filter and the kanban's
 * card placement — and the bug was those three agreeing with each other
 * and not with the tile.
 */

import type { Action, Lane } from '@/shared/api/actionBoard'

/** The lifecycle's own code for the late lane. See the module docstring. */
const OVERDUE = 'overdue'

/**
 * Which lane an action is drawn in.
 *
 * A late action **moves** rather than appearing twice: the lane counts have
 * to add up to the board, and a card in two columns is a card two people
 * each think the other is working.
 */
export function laneOf(action: Action, lanes: Lane[]): string {
  if (!action.pastDue) return action.status
  // Only open work can be late. A closed action finished after its due date
  // was finished late, which is a fact about the past and not a column.
  const stage = lanes.find((lane) => lane.code === action.status)
  if (stage !== undefined && !stage.open) return action.status
  return lanes.some((lane) => lane.code === OVERDUE) ? OVERDUE : action.status
}
