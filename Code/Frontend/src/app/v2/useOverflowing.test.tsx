/**
 * The measurement behind the legend's dot bubble.
 *
 * Same gap `useElementWidth.test.tsx` closes for the charts: jsdom has no
 * `ResizeObserver`, so this is pinned here rather than left to run only in
 * a real browser.
 *
 * The case that matters most here is the one that is not a layout fact at
 * all: a consumer that measures `scrollWidth` on the same element whose CSS
 * reacts to its own hover state. See `useOverflowing.ts`'s own note on the
 * flicker loop that produced — this hook's two-ref shape exists to make
 * that measurement impossible to write by accident, not just to work today.
 */

import { render, screen, act } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useOverflowing } from '@/app/v2/useOverflowing'

type Callback = () => void

/** The observers created during one test, so a test can drive them. */
const observers: { callback: Callback; disconnected: boolean }[] = []

class FakeResizeObserver {
  private readonly entry: { callback: Callback; disconnected: boolean }

  constructor(callback: Callback) {
    this.entry = { callback, disconnected: false }
    observers.push(this.entry)
  }

  observe(): void {
    // The real one fires on observe. This does not, so a test can tell the
    // mount-time measurement apart from an observed change.
  }

  disconnect(): void {
    this.entry.disconnected = true
  }
}

/** jsdom reports 0 for both on every element, so each node's value is read
 * off a data attribute instead — see `useElementWidth.test.tsx`'s own note
 * on why a callback ref will not do this instead. Two separate elements,
 * not one: that separation is the whole point of this hook. */
function layout(): void {
  vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockImplementation(function (
    this: HTMLElement,
  ) {
    return Number(this.dataset.mockScrollWidth ?? 0)
  })
  vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockImplementation(function (
    this: HTMLElement,
  ) {
    return Number(this.dataset.mockClientWidth ?? 0)
  })
}

function resize(): void {
  act(() => {
    for (const observer of observers) {
      if (!observer.disconnected) observer.callback()
    }
  })
}

function Probe({
  text,
  scrollWidth,
  clientWidth,
}: {
  text: string
  scrollWidth: number
  clientWidth: number
}) {
  const [containerRef, measureRef, overflowing] = useOverflowing<HTMLSpanElement, HTMLSpanElement>(
    text,
  )
  return (
    <span ref={containerRef} data-mock-client-width={clientWidth} data-testid="container">
      <span data-testid="overflowing">{String(overflowing)}</span>
      <span ref={measureRef} data-mock-scroll-width={scrollWidth}>
        {text}
      </span>
    </span>
  )
}

afterEach(() => {
  observers.length = 0
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('useOverflowing', () => {
  it('is false when the content fits on one line', () => {
    vi.stubGlobal('ResizeObserver', FakeResizeObserver)
    layout()

    render(<Probe text="Repeat contact" scrollWidth={80} clientWidth={120} />)

    expect(screen.getByTestId('overflowing')).toHaveTextContent('false')
  })

  it('is true once the content is wider than the column it sits in', () => {
    vi.stubGlobal('ResizeObserver', FakeResizeObserver)
    layout()

    render(<Probe text="Compliance control exception" scrollWidth={220} clientWidth={120} />)

    expect(screen.getByTestId('overflowing')).toHaveTextContent('true')
  })

  it('re-measures when the column is resized, not just on mount', () => {
    // A legend column is as wide as its panel, and a panel resizes with the
    // window or a sibling opening — neither is a one-time fact.
    vi.stubGlobal('ResizeObserver', FakeResizeObserver)
    layout()

    const { rerender } = render(
      <Probe text="Compliance control exception" scrollWidth={220} clientWidth={120} />,
    )
    expect(screen.getByTestId('overflowing')).toHaveTextContent('true')

    rerender(<Probe text="Compliance control exception" scrollWidth={220} clientWidth={320} />)
    resize()

    expect(screen.getByTestId('overflowing')).toHaveTextContent('false')
  })

  it('still measures once where ResizeObserver does not exist', () => {
    vi.stubGlobal('ResizeObserver', undefined)
    layout()

    render(<Probe text="Compliance control exception" scrollWidth={220} clientWidth={120} />)

    expect(screen.getByTestId('overflowing')).toHaveTextContent('true')
  })

  it('stops observing when the element goes away', () => {
    vi.stubGlobal('ResizeObserver', FakeResizeObserver)
    layout()
    const { unmount } = render(<Probe text="Repeat contact" scrollWidth={80} clientWidth={120} />)

    unmount()

    expect(observers.every((observer) => observer.disconnected)).toBe(true)
  })

  it('does not flip back and forth when only the measured element\'s own height changes', () => {
    // The bug this hook exists to make unwritable: a consumer whose visible
    // element wraps (grows taller, not wider) in reaction to this hook's
    // own `overflowing` value must not see that height change read back as
    // "no longer overflowing". Simulated here as a resize callback that
    // fires with the width unchanged — the shape a height-only layout
    // change actually produces.
    vi.stubGlobal('ResizeObserver', FakeResizeObserver)
    layout()

    render(<Probe text="Compliance control exception" scrollWidth={220} clientWidth={120} />)
    expect(screen.getByTestId('overflowing')).toHaveTextContent('true')

    resize()
    resize()
    resize()

    expect(screen.getByTestId('overflowing')).toHaveTextContent('true')
  })
})
