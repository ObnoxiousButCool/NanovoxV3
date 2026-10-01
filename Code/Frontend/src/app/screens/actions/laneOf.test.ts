/**
 * Which lane a late action is drawn in.
 *
 * The board printed "Overdue 0" beside a tile counting two genuinely late
 * actions, because the lane matched `status === 'overdue'` and nothing sets
 * that status — the server computes `pastDue` from the due date and leaves
 * the action in the stage it is really in.
 */

import { describe, expect, it } from 'vitest'

import { laneOf } from '@/app/screens/actions/laneOf'
import type { Action, Lane } from '@/shared/api/actionBoard'

const LANES: Lane[] = [
  { code: 'assigned', label: 'Assigned', open: true, requires: [] },
  { code: 'overdue', label: 'Overdue', open: true, requires: [] },
  { code: 'completed', label: 'Completed', open: false, requires: [] },
]

function action(overrides: Partial<Action>): Action {
  return { status: 'assigned', pastDue: false, ...overrides } as Action
}

describe('laneOf', () => {
  it('draws a late open action in the overdue lane, not in its own stage', () => {
    expect(laneOf(action({ status: 'assigned', pastDue: true }), LANES)).toBe('overdue')
  })

  it('leaves an action that is not late where it is', () => {
    expect(laneOf(action({ status: 'assigned', pastDue: false }), LANES)).toBe('assigned')
  })

  it('does not call finished work overdue', () => {
    // Closed after its due date is a fact about the past, which the card's
    // own date already carries. Moving it would reopen it on the board.
    expect(laneOf(action({ status: 'completed', pastDue: true }), LANES)).toBe('completed')
  })

  it('leaves the action in its stage when the lifecycle has no overdue lane', () => {
    const without = LANES.filter((lane) => lane.code !== 'overdue')
    expect(laneOf(action({ status: 'assigned', pastDue: true }), without)).toBe('assigned')
  })
})
