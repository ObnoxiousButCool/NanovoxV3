/**
 * Whether an element's own content no longer fits it on one line.
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
 */

import { useEffect, useRef, useState } from 'react'

export function useOverflowing<T extends HTMLElement>(
  // Content the caller renders into the measured element. Not read here —
  // only so the effect re-measures when it changes, the same text node
  // otherwise persisting across a re-render with nothing to tell this hook
  // to look again.
  content: unknown,
): [React.RefObject<T>, boolean] {
  const ref = useRef<T>(null)
  const [overflowing, setOverflowing] = useState(false)

  useEffect(() => {
    const element = ref.current
    if (!element) return

    const check = () => {
      setOverflowing(element.scrollWidth > element.clientWidth)
    }
    check()

    if (typeof ResizeObserver === 'undefined') return

    const observer = new ResizeObserver(check)
    observer.observe(element)
    return () => {
      observer.disconnect()
    }
  }, [content])

  return [ref, overflowing]
}
