/**
 * Two vocabularies, deliberately kept apart — decision **D13**.
 *
 * A **panel** wears one of six chips saying what kind of claim it makes. A
 * **figure** carries a `basis` saying where its number came from. They are
 * not the same vocabulary at different sizes; they are about different
 * objects. A panel tagged `inference` holds no figure at all — it holds a
 * sentence, and there is nothing for a figure-level value to label.
 *
 * So the six live here as panel copy, the API sends three, and
 * `basisFromApi` is the one seam between them.
 *
 * Separate from the component so `EpistemicChip.tsx` exports only a
 * component: React Fast Refresh works on a module whose exports are all
 * components, and a mixed module silently loses hot reloading.
 */

import type { components } from '@/shared/api/schema'

export type EpistemicKind =
  | 'observed'
  | 'reference'
  | 'derived'
  | 'pattern'
  | 'inference'
  | 'recommendation'

/** What each class means, shown on hover and to assistive technology. */
export const EPISTEMIC_MEANING: Record<EpistemicKind, string> = {
  observed: 'Counted directly from the calls.',
  reference: 'A fact about the account from the workbook, not from a call.',
  derived: 'Calculated by us from observed values.',
  pattern: 'A shape across several calls. No cause is claimed.',
  inference: 'A reading that goes beyond the data. Test it before acting on it.',
  recommendation: 'A suggested action, for the owning team to confirm.',
}

/** The three the API can send, straight from the generated client. */
type ApiFigure = components['schemas']['FigureResponse']
export type BasisCode = NonNullable<NonNullable<ApiFigure['basis']>['code']>

/**
 * A figure's `basis`, as a chip kind.
 *
 * Typed against the generated schema rather than `string`, so that if the
 * backend's vocabulary moves again this stops compiling instead of quietly
 * returning null and dropping every chip off the screen — which is how the
 * previous mapping would have failed.
 *
 * `null` means **say nothing**, and it has two causes that both want
 * silence rather than a guess:
 *
 * - a withheld figure whose question the v9 schema has no field for, so
 *   there is no origin to name;
 * - a code this build does not know, which is a deployment skew rather
 *   than a fact about the number.
 *
 * Suppression never arrives here. A withheld figure is rendered by
 * `Withheld`, which states the reason; chipping it "withheld" would put
 * the suppression in two places and the reason in neither.
 */
export function basisFromApi(code: string | null | undefined): EpistemicKind | null {
  if (code === 'OBSERVED') return 'observed'
  if (code === 'DERIVED') return 'derived'
  if (code === 'REFERENCE') return 'reference'
  return null
}
