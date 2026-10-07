/**
 * The rail, as `Prototype/v2/nv2.js` defines it.
 *
 * Pages are named as **questions** with a one-line plain-English subtext —
 * one of the deliberate changes in the v2 prototype, which wins on
 * presentation (plan §3.0). The labels are its own wording, not a paraphrase.
 *
 * Routes come from `Documents/notes/plan.md` §8, which is the authority on paths; the
 * prototype's filenames are not URLs.
 */

export interface NavItem {
  /** Route path. `Documents/notes/plan.md` §8. */
  to: string
  /** The question this page answers. `nv2.js` PAGES, verbatim. */
  label: string
  /** The one-line subtext under it. */
  hint: string
}

export const NAV_ITEMS: readonly NavItem[] = [
  { to: '/exec', label: 'Executive overview', hint: 'The period at a glance' },
  { to: '/risk', label: 'What are the risks?', hint: 'Accounts, drivers, signals' },
  {
    to: '/accounts',
    label: 'Insights & patterns around employers',
    hint: 'One account at a time',
  },
  { to: '/actions', label: 'What should we do next?', hint: 'Steps, owners, progress' },
  { to: '/hierarchy', label: 'Isolated or systemic?', hint: 'Region, broker, account' },
  { to: '/agents', label: 'How are agents handling calls?', hint: 'Conduct events' },
  { to: '/calls', label: 'All calls', hint: 'Browse, filter, export' },
]

/**
 * Screens that have a route but deliberately no rail entry.
 *
 * `/rules` is conflict **C5**, closed by Minnie on 2026-09-25 (**D14**):
 * it ships, reachable from `/agents` rather than from the main rail. The
 * rail is the seven questions the v2 prototype asks, and this is a page
 * you arrive at from a finding rather than one you start a session on.
 *
 * Kept as data so the rail test can assert it stays off, which is the
 * half of the decision that is easy to lose: "not in the nav" and
 * "nobody has decided" look identical in a nav file that lists neither.
 */
export const OFF_RAIL_SCREENS: readonly NavItem[] = [
  { to: '/rules', label: 'Rules we fail to explain', hint: 'Reached from the agents screen' },
]

/**
 * Screens the plan requires that the v2 prototype has no page for, and
 * that nobody has yet agreed to show.
 *
 * Kept as data rather than dropped, because "the prototype removed it" and
 * "nobody has decided" are different states and only the second is still
 * open. `/demand` is conflict **C6** in the revised plan; its endpoint is
 * built and it serves insights that render nowhere else. It is deliberately
 * absent from the rail, and unrouted, until that closes.
 */
export const UNPLACED_SCREENS: readonly NavItem[] = [
  { to: '/demand', label: 'Where calls come from', hint: 'Pending C6' },
]
