/**
 * How well sourced a **rule** is — the Rules sheets' own grade, not ours.
 *
 * ## It is not an epistemic class, and the shape says so
 *
 * `EpistemicChip` answers "where did this figure come from" (D13:
 * OBSERVED / REFERENCE / DERIVED). This answers something narrower and
 * unrelated: how the workbook came to believe one published rule. Every
 * grade here sits inside REFERENCE, so putting the two in the same visual
 * vocabulary would read as a fourth basis.
 *
 * It borrows `nv-pill`'s shape-plus-colour mechanism instead, for the
 * reason that primitive gives: these pages get printed in greyscale, and
 * roughly one man in twelve cannot separate the amber from the red. A
 * filled square is verified, a ring is verified at one remove, and a
 * triangle is unverified — legible with no colour at all.
 *
 * ## The prototype had the logic and no styling
 *
 * `rules.html` already carries three-way chip logic (`is-secondary`,
 * `is-unverified`) and `app.css` has no rule for `.conf` at all, which
 * `Documents/notes/plan.md` recorded rather than papering over. This is that gap closed in
 * the shared vocabulary, not a new one invented for one screen.
 */

import type { CodedValue } from '@/shared/design/primitives/types'

/** The grades the Rules sheets publish. Anything else keeps the plain mark. */
const TONES: Record<string, string> = {
  VERIFIED: 'verified',
  'VERIFIED (SECONDARY)': 'secondary',
  UNVERIFIED: 'unverified',
}

export function Provenance({ grade }: { grade: CodedValue }) {
  const tone = TONES[grade.code] ?? 'verified'
  return (
    <span className={`nv-pill nv-prov-${tone}`} title={grade.code}>
      {grade.label}
    </span>
  )
}
