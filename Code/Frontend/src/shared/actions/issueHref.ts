/**
 * Every red or orange number links to what to do about it.
 *
 * The prototype's `NV.actHref(key, extra)`, typed. A figure that says
 * something is wrong and offers no way to act on it is a screen that
 * reports problems at people; this is the seam that turns the four read
 * screens into a place work starts.
 *
 * ## Why the keys are a union rather than a string
 *
 * `/actions` will look each key up in a registry — checkpoint **I3**
 * validates that registry at startup in Phase 4. Until then a mistyped key
 * would route to a page that shrugs, and nothing would catch it. A union
 * makes a typo a build failure instead, which is the cheapest place to
 * find one.
 *
 * The seventeen keys are the prototype's own, read off `nv2.js` rather
 * than invented here. Three of them — `high`, `brush_off`, `circular` —
 * are **deliberately absent**: `high` is a risk band and **D12** removed
 * bands, and the other two key off `archetype`, which conflict **C8a**
 * leaves without a workbook source. Adding them would put a definition on
 * screen that nobody agreed.
 */

/** The issues a figure can hand to the action view. */
export const ISSUE_KEYS = [
  'flagged',
  'renew_soon',
  'unresolved',
  'escalation_missed',
  'complaint_choice',
  'repeat_contact',
  'exit_language',
  'critical_signal',
  'control_exception',
  'knowledge_failure',
  'high_effort',
  'broker_adverse',
  'overdue',
  'unowned',
] as const

export type IssueKey = (typeof ISSUE_KEYS)[number]

/** How near a renewal has to be to count as "soon" for `renew_soon` — the
 * prototype's own `NV.RENEW_SOON`. Named once here so the Exec and Risk
 * screens, which both flag against it, cannot drift apart on the number. */
export const RENEW_SOON_MONTHS = 4

/**
 * Whether a string names a playbook this build ships.
 *
 * Needed because a key can arrive from the API — a generated insight names
 * one — and three of the prototype's keys are deliberately absent (`high`,
 * `brush_off`, `circular`, held back by D12 and D14). Linking to one would
 * produce a focus the actions page cannot honour, so an unrecognised key
 * loses its link rather than making a dead one.
 */
export function isIssueKey(value: string): value is IssueKey {
  return (ISSUE_KEYS as readonly string[]).includes(value)
}

/**
 * Narrowing an issue to one account, broker or region.
 *
 * Each field is `string | undefined` rather than merely optional. Under
 * `exactOptionalPropertyTypes` those differ, and a caller that builds a
 * scope from data — `{ employer: row.employerRef }` where the ref may be
 * null — has an explicit `undefined` to pass. Refusing it would push every
 * call site into conditional spreads for no gain.
 */
export interface IssueScope {
  employer?: string | undefined
  broker?: string | undefined
  region?: string | undefined
  agent?: string | undefined
}

/**
 * The route to the focused action view for one issue.
 *
 * The current filters are **not** carried across. The action view asks a
 * different question — "what should be done about this" rather than "what
 * does this period show" — and inheriting a period would silently scope a
 * task list to a window the reader had set for a chart. What narrows it is
 * `scope`, passed explicitly.
 */
export function issueHref(key: IssueKey, scope: IssueScope = {}): string {
  const params = new URLSearchParams({ focus: key })
  // Entries rather than a hand-written list, so adding a field to
  // `IssueScope` cannot silently fail to reach the URL. Typed explicitly
  // because `Object.entries` widens the value to `any` on an interface
  // with optional members.
  const entries = Object.entries(scope) as [string, string | undefined][]
  for (const [name, value] of entries) {
    // An undefined field is absent, not empty: `?employer=` would read as
    // a filter matching nothing rather than as no filter at all.
    if (value !== undefined && value !== '') params.set(name, value)
  }
  return `/actions?${params.toString()}`
}
