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
  children: ReactNode
}) {
  return (
    <section className="nv-panel">
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
      {children}
    </section>
  )
}
