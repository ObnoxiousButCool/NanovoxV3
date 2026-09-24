/**
 * One figure, rendered honestly.
 *
 * Every published number on every screen goes through here, so that
 * "withheld is not zero" is structural rather than a rule each screen has
 * to remember. A caller cannot render the value without passing the whole
 * figure, and an unpublished figure cannot reach the formatter at all.
 *
 * `format` receives the value only when there is one. That is deliberate:
 * a formatter typed to take `number | null` would sooner or later render
 * null as `0%`, which is the exact failure this exists to prevent.
 */

import { Withheld } from '@/shared/design/primitives/Withheld'
import type { Figure } from '@/shared/design/primitives/types'

export function FigureValue({
  figure,
  format = (value) => String(value),
}: {
  figure: Figure
  format?: (value: number) => string
}) {
  if (!figure.published || figure.value === null || figure.value === undefined) {
    return <Withheld reason={figure.withheldReason} caveats={figure.caveats} />
  }
  return <span className="nv-figure">{format(figure.value)}</span>
}

/** `n` beside a figure, so a reader can judge how much it rests on. */
export function FigureBasis({ figure }: { figure: Figure }) {
  return <span className="nv-basis">{figure.n === 1 ? '1 call' : `${String(figure.n)} calls`}</span>
}
