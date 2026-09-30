/**
 * A titled section. Everything on a screen sits in one.
 *
 * `chip` is the epistemic class for the panel as a whole — the plan requires
 * one on every panel, so it is a named slot rather than something a caller
 * remembers to add.
 */

import type { ReactNode } from 'react'

export function Panel({
  title,
  sub,
  chip,
  actions,
  info,
  meta,
  footer,
  className,
  children,
}: {
  title: ReactNode
  sub?: ReactNode
  chip?: ReactNode
  actions?: ReactNode
  /**
   * The (i) tooltip, rendered inside the heading as `v2` has it. One of
   * v2's stated changes is that explanations move out of the page body, so
   * a panel with more to say than its subtitle carries puts it here rather
   * than in a paragraph nobody reads.
   */
  info?: ReactNode
  /**
   * A line between the subtitle and the contents, laid out as two ends —
   * `.ai-meta` in `v2.css`, where the left names what the card is about and
   * the right counts what is behind it.
   */
  meta?: ReactNode
  /**
   * Below the contents. `v2.css` puts a card's actions at its foot
   * (`.ai-act`) rather than beside its title, which is where `actions`
   * puts them; a caller uses one or the other, not both.
   */
  footer?: ReactNode
  /** An extra class on the section, for a panel with its own card shape. */
  className?: string
  children: ReactNode
}) {
  return (
    <section className={className === undefined ? 'nv-panel' : `nv-panel ${className}`}>
      <header>
        <div>
          <h2>
            {title}
            {info}
          </h2>
        </div>
        {chip ?? actions ? (
          <div className="nv-panel-aside">
            {chip}
            {actions}
          </div>
        ) : null}
      </header>
      {sub ? <p className="nv-sub">{sub}</p> : null}
      {meta ? <p className="nv-panel-meta">{meta}</p> : null}
      {children}
      {footer}
    </section>
  )
}
