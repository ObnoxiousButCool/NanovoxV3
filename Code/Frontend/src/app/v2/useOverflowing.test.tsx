/**
 * The measurement behind the legend's dot bubble.
 *
 * Same gap `useElementWidth.test.tsx` closes for the charts: jsdom has no
 * `ResizeObserver`, so this is pinned here rather than left to run only in
 * a real browser.
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

function Probe({ text }: { text: string }) {
  const [ref, overflowing] = useOverflowing<HTMLSpanElement>(text)
  return (
    <span ref={ref} data-testid="measured">
      {text}
      <span data-testid="overflowing">{String(overflowing)}</span>
    </span>
  )
}

/** jsdom reports both at 0 for everything, so the comparison is stubbed on
 * the prototype rather than on the node — see `useElementWidth.test.tsx`'s
 * own note on why a callback ref will not do this instead. */
function layout(scrollWidth: number, clientWidth: number): void {
  vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockReturnValue(scrollWidth)
  vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockReturnValue(clientWidth)
}

function resize(scrollWidth: number, clientWidth: number): void {
  layout(scrollWidth, clientWidth)
  act(() => {
    for (const observer of observers) {
      if (!observer.disconnected) observer.callback()
    }
  })
}

afterEach(() => {
  observers.length = 0
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('useOverflowing', () => {
  it('is false when the content fits on one line', () => {
    vi.stubGlobal('ResizeObserver', FakeResizeObserver)
    layout(80, 120)

    render(<Probe text="Repeat contact" />)

    expect(screen.getByTestId('overflowing')).toHaveTextContent('false')
  })

  it('is true once the content is wider than the column it sits in', () => {
    vi.stubGlobal('ResizeObserver', FakeResizeObserver)
    layout(220, 120)

    render(<Probe text="Compliance control exception" />)

    expect(screen.getByTestId('overflowing')).toHaveTextContent('true')
  })

  it('re-measures when the column is resized, not just on mount', () => {
    // A legend column is as wide as its panel, and a panel resizes with the
    // window or a sibling opening — neither is a one-time fact.
    vi.stubGlobal('ResizeObserver', FakeResizeObserver)
    layout(220, 120)

    render(<Probe text="Compliance control exception" />)
    expect(screen.getByTestId('overflowing')).toHaveTextContent('true')

    resize(220, 320)

    expect(screen.getByTestId('overflowing')).toHaveTextContent('false')
  })

  it('still measures once where ResizeObserver does not exist', () => {
    vi.stubGlobal('ResizeObserver', undefined)
    layout(220, 120)

    render(<Probe text="Compliance control exception" />)

    expect(screen.getByTestId('overflowing')).toHaveTextContent('true')
  })

  it('stops observing when the element goes away', () => {
    vi.stubGlobal('ResizeObserver', FakeResizeObserver)
    layout(80, 120)
    const { unmount } = render(<Probe text="Repeat contact" />)

    unmount()

    expect(observers.every((observer) => observer.disconnected)).toBe(true)
  })
})
