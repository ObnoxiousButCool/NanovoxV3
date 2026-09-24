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
  info,
}: {
  label: ReactNode
  value: ReactNode
  meta?: ReactNode
  tone?: TileTone
  info?: ReactNode
}) {
  return (
    <div className={`nv-big${tone === 'plain' ? '' : ` nv-${tone}`}`}>
      <span className="nv-k">
        {label}
        {info}
      </span>
      <span className="nv-v">{value}</span>
      {meta ? <span className="nv-m">{meta}</span> : null}
    </div>
  )
}
