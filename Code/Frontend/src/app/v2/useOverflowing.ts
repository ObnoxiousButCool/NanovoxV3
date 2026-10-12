/**
 * Whether a container's text no longer fits it on one line.
 *
 * Mirrors `shared/design/charts/useElementWidth`'s shape and its fallback:
 * a one-time measurement where `ResizeObserver` does not exist (older
 * environments, jsdom), and a live one where it does — a legend column's
 * width changes with the panel, a filter row wrapping, or the rail
 * collapsing, none of which fire a window resize event.
 *
 * `scrollWidth > clientWidth` rather than counting words: a three-word
 * label can still wrap in a narrow column, and a longer one can still fit
 * in a wide one. Measuring the real layout is the only thing that answers
 * "does this fit" for every width, not just the common one.
 *
 * ## Why two elements, not one
 *
 * The first version measured `scrollWidth` on the same element whose CSS
 * toggles `white-space` on hover (`overview.css`'s `:has()` rule) — and
 * that element's own hover state fed back into the measurement that
 * decides it: wrapping the text on hover makes it stop overflowing
 * horizontally, `scrollWidth` collapses to match `clientWidth`, this hook
 * reports `false`, the caller un-renders the hover target, `:hover` ends
 * because the target is gone, the CSS reverts, the text re-overflows, this
 * hook reports `true` again, the target reappears under the pointer, and
 * the cycle repeats — a flicker loop, not a measurement.
 *
 * `measureRef` stays `white-space: nowrap` always, never touched by any
 * hover rule, so its `scrollWidth` is the text's one-line width regardless
 * of what the visible element is doing. `containerRef`'s `clientWidth` is
 * the available width, which a sibling's `white-space` does not change
 * either. Comparing the two keeps the question "does this fit" answered
 * from values neither hover state can move.
 */

import { useEffect, useRef, useState } from 'react'

export function useOverflowing<Container extends HTMLElement, Measure extends HTMLElement>(
  // Content the caller renders into the measured elements. Not read here —
  // only so the effect re-measures when it changes, the same nodes
  // otherwise persisting across a re-render with nothing to tell this hook
  // to look again.
  content: unknown,
): [React.RefObject<Container>, React.RefObject<Measure>, boolean] {
  const containerRef = useRef<Container>(null)
  const measureRef = useRef<Measure>(null)
  const [overflowing, setOverflowing] = useState(false)

  useEffect(() => {
    const container = containerRef.current
    const measure = measureRef.current
    if (!container || !measure) return

    const check = () => {
      setOverflowing(measure.scrollWidth > container.clientWidth)
    }
    check()

    if (typeof ResizeObserver === 'undefined') return

    // The container, not the measurer: the measurer's own size never
    // changes (always one line, same text), so nothing would ever fire.
    // The container resizes with the panel, which is the case this exists
    // for.
    const observer = new ResizeObserver(check)
    observer.observe(container)
    return () => {
      observer.disconnect()
    }
  }, [content])

  return [containerRef, measureRef, overflowing]
}
