/**
 * The width a chart actually has, in real pixels.
 *
 * This is the whole reason the v2 charts exist. The shared charts in the
 * original prototype draw into a fixed `viewBox` and let the browser scale
 * them, so a 12px axis label becomes 18px on a wide panel and 8px in a
 * narrow one — the type and the stroke weights balloon or collapse with the
 * container. Measuring instead, and drawing at that size, keeps 12px at
 * 12px everywhere.
 *
 * `ResizeObserver` rather than a window resize listener: a chart's container
 * changes size when a panel opens, a filter row wraps or the rail collapses,
 * none of which resize the window.
 */

import { useEffect, useRef, useState } from 'react'

/** Below this a chart is too narrow to label; callers thin their ticks. */
export const MIN_CHART_WIDTH = 280

export function useElementWidth<T extends HTMLElement>(): [React.RefObject<T>, number] {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(0)

  useEffect(() => {
    const element = ref.current
    if (!element) return

    // Measure once up front: ResizeObserver fires on observe in every
    // browser that matters, but a first paint at zero width is a visible
    // flash and not worth relying on the spec for.
    setWidth(element.clientWidth)

    if (typeof ResizeObserver === 'undefined') return

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0]
      if (entry) setWidth(entry.contentRect.width)
    })
    observer.observe(element)
    return () => {
      observer.disconnect()
    }
  }, [])

  return [ref, Math.max(width, MIN_CHART_WIDTH)]
}

/**
 * A round number at or above `value`, for the top of an axis.
 *
 * Ported from the prototype's `niceMax`. An axis topped at the exact maximum
 * puts the tallest bar against the frame and gives gridlines at arbitrary
 * values; rounding up gives both room and readable ticks.
 */
export function niceMax(value: number): number {
  if (value <= 5) return 5
  const magnitude = Math.pow(10, Math.floor(Math.log10(value)))
  const normalised = value / magnitude
  const step = normalised <= 1 ? 1 : normalised <= 2 ? 2 : normalised <= 2.5 ? 2.5 : normalised <= 5 ? 5 : 10
  return step * magnitude
}
