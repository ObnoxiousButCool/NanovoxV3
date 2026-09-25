/**
 * The "what to do about this" cue, beside a figure that reports a problem.
 *
 * Separate module from `issueHref` so this one exports only components and
 * React Fast Refresh keeps working — the same split `EpistemicChip` and
 * `epistemic.ts` already use.
 */

import { Link } from 'react-router-dom'
import type { ReactNode } from 'react'

import { issueHref } from '@/shared/actions/issueHref'
import type { IssueKey, IssueScope } from '@/shared/actions/issueHref'
import '@/shared/actions/actions.css'

/**
 * Wraps a value so the number itself is the link.
 *
 * `tone` is the prototype's `hot` / `warm`. It carries no meaning a reader
 * needs beyond emphasis, so it is never the only signal: the link has
 * visible text and an accessible name either way, and a reader who cannot
 * tell the two colours apart loses nothing but the emphasis.
 */
export function IssueValue({
  issue,
  scope,
  tone = 'hot',
  children,
}: {
  issue: IssueKey
  scope?: IssueScope
  tone?: 'hot' | 'warm'
  children: ReactNode
}) {
  return (
    <Link className={`nv-act nv-act-${tone}`} to={issueHref(issue, scope)} title="What to do about this">
      {children}
    </Link>
  )
}

/** The standalone cue the prototype puts under a tile. */
export function IssueCue({
  issue,
  scope,
  children,
}: {
  issue: IssueKey
  scope?: IssueScope
  children?: ReactNode
}) {
  return (
    <Link className="nv-todo" to={issueHref(issue, scope)}>
      {children ?? 'What to do'} →
    </Link>
  )
}
