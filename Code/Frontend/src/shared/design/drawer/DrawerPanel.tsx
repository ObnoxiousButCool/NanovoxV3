/**
 * One collapsible panel in a call's drawer.
 *
 * Shared by the five analysis panels and by the conversation, because they
 * are the same kind of object to a reader: a named part of what we hold
 * about this call, which they open when they want it and leave shut when
 * they do not. Two implementations would drift in the way that matters most
 * here — one of them would eventually stop saying whether its contents are
 * there, which is the distinction these panels exist to carry.
 *
 * ## Colour is never the only signal
 *
 * The accent down the left edge repeats what the title, the subtitle and
 * the "Not run" pill already say. `StatusPill` makes the same argument in
 * the design system — shape, not only colour — and a panel that encoded
 * "this layer never ran" as a hue alone would say nothing to a reader who
 * cannot separate these greys.
 *
 * Each panel used to wear a "Code" / "Model" / "Source" badge naming what
 * produced it. It was removed on request; the subtitles say the same thing
 * in longer words, which is why it could go.
 */

import type { ReactNode } from 'react'

import { Note } from '@/shared/design/primitives'

/** Which accent a panel wears. One per panel, so no two are confusable. */
export type PanelAccent = 'l1' | 'l2' | 'l3' | 'l4' | 'derived' | 'conversation'

export function DrawerPanel({
  accent,
  title,
  subtitle,
  present,
  absentBecause,
  absentLabel = 'Not run',
  footer,
  openByDefault = false,
  children,
}: {
  accent: PanelAccent
  title: string
  subtitle: string
  /** Whether there is anything behind this panel at all. */
  present: boolean
  /** Said in place of the contents. Never left to an empty panel to imply. */
  absentBecause?: string | null | undefined
  /** What the header pill reads when `present` is false. */
  absentLabel?: string
  /** Rendered under the contents — provenance, where a layer has it. */
  footer?: ReactNode
  openByDefault?: boolean
  children: ReactNode
}) {
  return (
    <details className={`nv-layer nv-layer-${accent}`} open={present && openByDefault}>
      <summary>
        <span className="nv-layer-title">{title}</span>
        {present ? null : <span className="nv-layer-off">{absentLabel}</span>}
      </summary>
      <div className="nv-layer-body">
        <p className="nv-layer-sub">{subtitle}</p>
        {present ? (
          <>
            {children}
            {footer}
          </>
        ) : (
          <Note>{absentBecause ?? 'There is nothing behind this panel.'}</Note>
        )}
      </div>
    </details>
  )
}
