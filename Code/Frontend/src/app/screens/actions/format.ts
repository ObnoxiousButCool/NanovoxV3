/**
 * Small formatting helpers shared by the board, the card and the composer.
 *
 * Kept out of the components so the lane-colour rule — the one place this
 * screen assigns meaning to a lane it did not define — sits in one spot with
 * its reasoning attached.
 */

import type { Lane } from '@/shared/api/actionBoard'

const MONTHS = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec',
]

/** `2026-10-05` -> `5 Oct`, parsed as a plain date so no timezone can shift
 * the day shown from the day stored. */
export function formatDue(due: string): string {
  const [, month, day] = due.split('-').map(Number)
  return `${String(day)} ${MONTHS[(month ?? 1) - 1] ?? ''}`
}

export function initials(name: string | null): string {
  if (!name) return '–'
  return name
    .split(' ')
    .map((part) => part[0])
    .join('')
    .slice(0, 2)
    .toUpperCase()
}

/** Working lanes cycle one palette, closed lanes another — a colour per
 * lane without this screen inventing meaning for a lane code it did not
 * define. Which lanes exist, and their order, come from the server alone;
 * this only decides how to tint them. */
const OPEN_PALETTE = ['var(--seq-1)', 'var(--seq-2)', 'var(--brand)', 'var(--s1)']
const CLOSED_PALETTE = ['var(--s4)', 'var(--s3)', 'var(--good)']

export function laneColor(lane: Lane, openIndex: number, closedIndex: number): string {
  return lane.open
    ? (OPEN_PALETTE[openIndex % OPEN_PALETTE.length] ?? 'var(--seq-1)')
    : (CLOSED_PALETTE[closedIndex % CLOSED_PALETTE.length] ?? 'var(--s4)')
}

/** Every lane, coloured once, by the order the server sent them in. */
export function laneColors(lanes: Lane[]): Map<string, string> {
  const colors = new Map<string, string>()
  let openIndex = 0
  let closedIndex = 0
  for (const lane of lanes) {
    colors.set(lane.code, laneColor(lane, openIndex, closedIndex))
    if (lane.open) openIndex += 1
    else closedIndex += 1
  }
  return colors
}

const PRIORITY_COLOR: Record<string, string> = {
  high: 'var(--critical)',
  medium: 'var(--warning)',
  low: 'var(--rule-strong)',
}

export function priorityColor(priority: string): string {
  return PRIORITY_COLOR[priority] ?? 'var(--rule-strong)'
}

/** What a lane still needs before an action may sit there, in words rather
 * than as the raw requirement codes the server sends. */
const REQUIREMENT_LABEL: Record<string, string> = {
  action_taken: 'what was done',
  measurement_window: 'a measurement window',
  outcome: 'an outcome',
}

export function requirementLabel(requirement: string): string {
  return REQUIREMENT_LABEL[requirement] ?? requirement.replace(/_/g, ' ')
}

/** What produced an action, labelled and coloured. `manual` and anything
 * this list does not yet name fall back to a plain label and a neutral
 * tone rather than guessing. */
const SOURCE_KIND_LABEL: Record<string, string> = {
  process_gap: 'Process gap',
  knowledge_failure: 'Knowledge failure',
  escalation_missed: 'Escalation missed',
  retention_risk: 'Retention risk',
  control_exception: 'Control exception',
  broker_pattern: 'Broker pattern',
  manual: 'Raised on the board',
}

const SOURCE_KIND_COLOR: Record<string, string> = {
  process_gap: 'var(--seq-2)',
  knowledge_failure: 'var(--s4)',
  escalation_missed: 'var(--critical)',
  retention_risk: 'var(--serious)',
  control_exception: 'var(--s1)',
  broker_pattern: 'var(--seq-3)',
  manual: 'var(--ink-3)',
}

export function sourceKindLabel(sourceKind: string): string {
  return SOURCE_KIND_LABEL[sourceKind] ?? sourceKind.replace(/_/g, ' ')
}

export function sourceKindColor(sourceKind: string): string {
  return SOURCE_KIND_COLOR[sourceKind] ?? 'var(--ink-3)'
}

/** The Signal Taxonomy's four severities (`SignalSeverity`), coloured. */
const SEVERITY_COLOR: Record<string, string> = {
  // The Signal Taxonomy's four, used by the board's cards.
  CRITICAL: 'var(--critical)',
  HIGH: 'var(--critical)',
  MEDIUM: 'var(--serious)',
  LOW: 'var(--warning)',
  // A playbook's two, used by the issues list. Deliberately the same two
  // colours as the taxonomy's top and middle rather than a third palette:
  // red is urgent and orange is important wherever the reader sees them.
  high: 'var(--critical)',
  medium: 'var(--serious)',
}

export function severityColor(code: string): string {
  return SEVERITY_COLOR[code] ?? 'var(--ink-3)'
}
