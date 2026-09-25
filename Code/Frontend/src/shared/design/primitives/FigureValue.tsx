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
/**
 * How many calls stand behind a figure.
 *
 * Named `FigureBasis` until D13, which gave `basis` a precise and different
 * meaning on the wire — where a number came from, not how much of it there
 * is. A component rendering the sample size under that name would have read
 * as the origin chip to the next person looking for one.
 */
export function FigureSample({ figure }: { figure: Figure }) {
  return <span className="nv-basis">{figure.n === 1 ? '1 call' : `${String(figure.n)} calls`}</span>
}
