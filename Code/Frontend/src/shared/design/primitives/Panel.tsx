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
  children,
}: {
  title: ReactNode
  sub?: ReactNode
  chip?: ReactNode
  actions?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="nv-panel">
      <header>
        <div>
          <h2>{title}</h2>
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
