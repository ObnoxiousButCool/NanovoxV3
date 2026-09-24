/**
 * The rail, as `Prototype/v2/nv2.js` defines it.
 *
 * Pages are named as **questions** with a one-line plain-English subtext —
 * one of the deliberate changes in the v2 prototype, which wins on
 * presentation (plan §3.0). The labels are its own wording, not a paraphrase.
 *
 * Routes come from `plan.md` §8, which is the authority on paths; the
 * prototype's filenames are not URLs.
 */

export interface NavItem {
  /** Route path. `plan.md` §8. */
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
 * Screens the plan requires that the v2 prototype has no page for.
 *
 * Kept as data rather than dropped, because "the prototype removed it" and
 * "nobody has decided" are different states and only the second is still
 * open. `/rules` is conflict **C5** and `/demand` is **C6** in the revised
 * plan; both endpoints are built and serve insights that render nowhere
 * else. They are deliberately absent from the rail until those close.
 */
export const UNPLACED_SCREENS: readonly NavItem[] = [
  { to: '/rules', label: 'Rules we fail to explain', hint: 'Pending C5' },
  { to: '/demand', label: 'Where calls come from', hint: 'Pending C6' },
]
