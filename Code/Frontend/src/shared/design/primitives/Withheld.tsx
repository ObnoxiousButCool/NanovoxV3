/**
 * A figure that was suppressed, and why.
 *
 * The single most important primitive in the set. **Withheld is not zero**:
 * zero reads as good news where the truth is absence of evidence, and the
 * whole application is built to keep those apart. A withheld figure renders
 * as a dash with its reason attached, never as `0`, never as an empty cell.
 *
 * The reason is the API's own `withheldReason` label, not wording invented
 * here — "Too few calls to publish" and "Not a field in the v9 schema" mean
 * different things to a reader, and only the first is fixed by more calls.
 */

import type { CodedValue } from '@/shared/design/primitives/types'

export function Withheld({
  reason,
  caveats,
}: {
  reason?: CodedValue | null | undefined
  caveats?: string[] | undefined
}) {
  const notes = caveats ?? []
  return (
    <span className="nv-withheld">
      <span className="nv-withheld-mark" aria-hidden="true">
        –
      </span>
      <span className="nv-withheld-why">
        {reason?.label ?? 'Withheld'}
        {notes.length > 0 ? <small>{notes.join(' ')}</small> : null}
      </span>
    </span>
  )
}
