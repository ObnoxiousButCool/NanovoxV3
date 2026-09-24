/**
 * What kind of claim this is.
 *
 * Each chip is distinguished by border style as well as colour — dashed for
 * the two that go beyond the data — so it survives greyscale printing.
 */

import { EPISTEMIC_MEANING } from '@/shared/design/primitives/epistemic'
import type { EpistemicKind } from '@/shared/design/primitives/epistemic'

export function EpistemicChip({ kind }: { kind: EpistemicKind }) {
  return (
    <span className={`nv-cls nv-cls-${kind}`} title={EPISTEMIC_MEANING[kind]}>
      {kind}
    </span>
  )
}
