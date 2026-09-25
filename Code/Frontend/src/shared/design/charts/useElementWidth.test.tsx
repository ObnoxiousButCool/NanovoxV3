/**
 * The measuring behind every chart.
 *
 * This is the one piece of the chart system no test reached: jsdom has no
 * `ResizeObserver`, so `useElementWidth` returned early and the whole
 * redraw-on-resize path — a named Phase 1 deliverable — ran only in a real
 * browser. It is installed here so the behaviour is pinned, because the
 * failure it prevents is silent: a chart that measures once keeps drawing
 * at its first width forever, and looks entirely correct until a panel
 * changes size.
 */

import { render, screen, act } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { MIN_CHART_WIDTH, useElementWidth } from '@/shared/design/charts/useElementWidth'

type Callback = (entries: { contentRect: { width: number } }[]) => void

/** The observers created during one test, so a test can drive them. */
const observers: { callback: Callback; disconnected: boolean }[] = []

class FakeResizeObserver {
  private readonly entry: { callback: Callback; disconnected: boolean }

  constructor(callback: Callback) {
    this.entry = { callback, disconnected: false }
    observers.push(this.entry)
  }

  observe(): void {
    // The real one fires on observe. This does not, so that a test can tell
    // the mount-time measurement apart from an observed change.
  }

  disconnect(): void {
    this.entry.disconnected = true
  }
}

function Probe() {
  const [ref, width] = useElementWidth<HTMLDivElement>()
  return (
    <div ref={ref} data-testid="host">
      <span data-testid="width">{width}</span>
    </div>
  )
}

/**
 * jsdom reports `clientWidth` 0 for everything, so layout is stubbed on the
 * prototype rather than on the node.
 *
 * On the node is what the first version did, through a callback ref — but
 * `RefObject.current` is read-only in the React types, so that version
 * passed vitest and failed `tsc`. Worth recording: the tests ran green
 * while the typecheck did not.
 */
function layoutWidth(width: number): void {
  vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(width)
}

function resizeTo(width: number): void {
  act(() => {
    for (const observer of observers) {
      if (!observer.disconnected) observer.callback([{ contentRect: { width } }])
    }
  })
}

afterEach(() => {
  observers.length = 0
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('useElementWidth', () => {
  it('measures its container on mount rather than painting at zero', () => {
    vi.stubGlobal('ResizeObserver', FakeResizeObserver)

    layoutWidth(640)
    render(<Probe />)

    expect(screen.getByTestId('width')).toHaveTextContent('640')
  })

  it('redraws when the container changes size', () => {
    // The deliverable: "measuring their container and redrawing on resize".
    // A chart that measures once looks correct until a panel opens, a filter
    // row wraps or the rail collapses — none of which resize the window,
    // which is why this is a ResizeObserver and not a resize listener.
    vi.stubGlobal('ResizeObserver', FakeResizeObserver)
    layoutWidth(640)
    render(<Probe />)

    resizeTo(1440)

    expect(screen.getByTestId('width')).toHaveTextContent('1440')
  })

  it('never reports less than the width a chart can be labelled at', () => {
    // Below this the axis has no room for its ticks. Callers thin their
    // labels against this number, so it must not drift with the container.
    vi.stubGlobal('ResizeObserver', FakeResizeObserver)
    layoutWidth(640)
    render(<Probe />)

    resizeTo(120)

    expect(screen.getByTestId('width')).toHaveTextContent(String(MIN_CHART_WIDTH))
  })

  it('stops observing when the chart goes away', () => {
    vi.stubGlobal('ResizeObserver', FakeResizeObserver)
    layoutWidth(640)
    const { unmount } = render(<Probe />)

    unmount()

    expect(observers.every((observer) => observer.disconnected)).toBe(true)
  })

  it('still measures once where ResizeObserver does not exist', () => {
    // Older environments and jsdom itself. The chart must render at a
    // sensible width rather than collapsing to nothing.
    vi.stubGlobal('ResizeObserver', undefined)

    layoutWidth(900)
    render(<Probe />)

    expect(screen.getByTestId('width')).toHaveTextContent('900')
  })
})
