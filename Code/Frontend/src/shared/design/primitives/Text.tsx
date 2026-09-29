/**
 * The small text primitives: empty states, notes, quotes and claims.
 *
 * `Empty` says what to do about it. "No data" is a dead end; "widen the
 * period or clear a filter" is the next step, and at batch-1 volume an empty
 * panel is usually a filter that is too narrow rather than a real absence.
 */

import type { ReactNode } from 'react'

export function Empty({
  title = 'Nothing in scope',
  children = 'Widen the period or clear a filter.',
}: {
  title?: ReactNode
  children?: ReactNode
}) {
  return (
    <div className="nv-empty">
      <b>{title}</b>
      {children}
    </div>
  )
}

export function Note({ suppressed = false, children }: { suppressed?: boolean; children: ReactNode }) {
  return <p className={`nv-note${suppressed ? ' nv-suppressed' : ''}`}>{children}</p>
}

/** A verbatim line from a call. Attribution is required, not optional. */
export function Quote({ children, source }: { children: ReactNode; source: string }) {
  return (
    <blockquote className="nv-quote">
      {children}
      <cite>{source}</cite>
    </blockquote>
  )
}

export function Claim({ children }: { children: ReactNode }) {
  return (
    <div className="nv-claim">
      <span className="nv-t">{children}</span>
    </div>
  )
}

export function SeverityLabel({ severity }: { severity: string }) {
  return <span className={`nv-sev nv-sev-${severity}`}>{severity.toLowerCase()}</span>
}

/**
 * A visual stand-in for a panel with nothing in it yet — used only when the
 * underlying corpus is genuinely empty (an action board nobody has written
 * to, say), never to paper over a withheld figure or a movement inside
 * noise, which already have their own honest renderings (`Withheld`, the
 * noise tag on `nv-movements`). The badge names it every time it appears,
 * so a reader never mistakes the shape for a claim about the account.
 */
export function SampleFallback({ children }: { children: ReactNode }) {
  return (
    <div className="nv-sample">
      <span className="nv-samplebadge">Sample data — illustrative, not from the corpus</span>
      <div className="nv-samplebody">{children}</div>
    </div>
  )
}
