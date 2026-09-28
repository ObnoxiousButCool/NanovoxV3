/**
 * Reading an action against the lifecycle, without assuming a lane's code.
 *
 * The lifecycle is configuration (`config/action_lifecycle.yaml`), so this
 * screen never asks "is this the `completed` lane" — a config change would
 * make that question wrong silently. It asks the two things the server
 * actually publishes about a lane: whether it is still open, and what an
 * action must carry to sit there (`requires`). Everything here — the
 * "next move" banner, which Move-to buttons are enabled — is computed from
 * those two facts and the action's own fields.
 */

import type { Action, Lane } from '@/shared/api/actionBoard'

export function findLane(lanes: Lane[], code: string): Lane | undefined {
  return lanes.find((lane) => lane.code === code)
}

/** Whether `action` already carries what `requirement` names. An unknown
 * requirement string is treated as met — the server enforces the real
 * rule; this only avoids blocking a button on a requirement it cannot
 * read. */
function satisfies(requirement: string, action: Action): boolean {
  if (requirement === 'action_taken') return action.actionTaken !== null
  if (requirement === 'outcome') return action.outcome !== null
  if (requirement === 'measurement_window') return action.measurementWindow !== null
  return true
}

/** What `lane` still needs before `action` may move there. Empty means the
 * move is expected to succeed. */
export function missingRequirements(lane: Lane, action: Action): string[] {
  return lane.requires.filter((requirement) => !satisfies(requirement, action))
}

/** The index of the first unticked step, or -1 when every step is done (or
 * there are none). */
export function nextStepIndex(action: Action): number {
  return action.steps.findIndex((step) => !step.done)
}
