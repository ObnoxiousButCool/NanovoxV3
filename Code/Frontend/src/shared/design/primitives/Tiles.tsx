/**
 * The headline tiles across the top of a screen.
 *
 * `tone` is an edge colour, never the only signal: the figure and its
 * subtext carry the meaning, and a tile read in greyscale still says what it
 * says. `withheld` is a tone of its own rather than an absence, so a
 * suppressed headline looks deliberate instead of broken.
 */

import type { ReactNode } from 'react'

export type TileTone = 'plain' | 'hot' | 'warm' | 'withheld'

export function BigRow({ children }: { children: ReactNode }) {
  return <div className="nv-bigrow">{children}</div>
}

export function KpiTile({
  label,
  value,
  meta,
  tone = 'plain',
  todo,
}: {
  label: ReactNode
  value: ReactNode
  meta?: ReactNode
  tone?: TileTone
  /**
   * The route from a number to the step that answers it — `.big .todo` in
   * `v2.css`, which the prototype puts on every tile carrying an issue.
   * It sits under the meta line rather than on the value, because the
   * value is a figure and this is a recommendation (C3a).
   */
  todo?: ReactNode
}) {
  return (
    <div className={`nv-big${tone === 'plain' ? '' : ` nv-${tone}`}`}>
      <span className="nv-k">{label}</span>
      <span className="nv-v">{value}</span>
      {meta ? <span className="nv-m">{meta}</span> : null}
      {todo}
    </div>
  )
}
