/**
 * What each epistemic class means, and how the API's three map onto the six.
 *
 * Separate from the component so `EpistemicChip.tsx` exports only a
 * component: React Fast Refresh works on a module whose exports are all
 * components, and a mixed module silently loses hot reloading.
 */

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

/**
 * The API's three values, mapped onto the six the screens use.
 *
 * `WITHHELD` has no chip of its own: a withheld figure is rendered by
 * `Withheld`, which states the reason. Chipping it "withheld" would put the
 * suppression in two places and the reason in neither.
 *
 * The API's set is narrower than the prototype's — conflict **C3**. When
 * that closes, this map is the only thing that changes.
 */
export function epistemicFromApi(code: string): EpistemicKind | null {
  if (code === 'MEASURED') return 'observed'
  if (code === 'DERIVED') return 'derived'
  return null
}
