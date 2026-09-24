/**
 * The charts, tested for the one failure they all share.
 *
 * A chart that renders a missing week at the baseline looks complete and is
 * a lie: it claims a measurement nobody took. Every assertion here is some
 * version of "the gap survived".
 */

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { BarCell, Gauge, Heatmap, MiniBars, Sparkline, VBars, VLine } from '@/shared/design/charts'
import { niceMax } from '@/shared/design/charts/useElementWidth'

const WEEKS = ['1', '2', '3', '4']

describe('VLine', () => {
  it('breaks the line at a gap rather than interpolating across it', () => {
    // One path either side of the hole, never one path through it.
    const { container } = render(
      <VLine
        labels={['1', '2', '3', '4', '5']}
        series={[{ name: 'Calls', values: [4, 5, null, 6, 7], color: 'var(--seq-2)' }]}
        ariaLabel="Calls each week"
      />,
    )

    expect(container.querySelectorAll('path')).toHaveLength(2)
  })

  it('still shows a measured value that has gaps on both sides', () => {
    // It cannot be a line segment, so it survives as a dot or not at all.
    const { container } = render(
      <VLine
        labels={WEEKS}
        series={[{ name: 'Calls', values: [null, 6, null, null], color: 'var(--seq-2)' }]}
        ariaLabel="Calls each week"
      />,
    )

    expect(container.querySelectorAll('path')).toHaveLength(0)
    expect(container.querySelectorAll('circle')).toHaveLength(1)
  })

  it('draws a dot only where something was measured', () => {
    const { container } = render(
      <VLine
        labels={WEEKS}
        series={[{ name: 'Calls', values: [4, null, 6, 7], color: 'var(--seq-2)' }]}
        ariaLabel="Calls each week"
      />,
    )

    expect(container.querySelectorAll('circle')).toHaveLength(3)
  })

  it('keeps a measured zero, which is not a gap', () => {
    // "We measured zero" and "we measured nothing" must stay distinct.
    const { container } = render(
      <VLine
        labels={WEEKS}
        series={[{ name: 'Calls', values: [4, 0, 6, 7], color: 'var(--seq-2)' }]}
        ariaLabel="Calls each week"
      />,
    )

    expect(container.querySelectorAll('path')).toHaveLength(1)
    expect(container.querySelectorAll('circle')).toHaveLength(4)
  })
})

describe('VBars', () => {
  it('labels an empty band "none" instead of drawing a zero bar', () => {
    render(
      <VBars
        labels={WEEKS}
        series={[{ name: 'Calls', values: [4, null, 6, 7], color: 'var(--seq-2)' }]}
        ariaLabel="Calls each week"
      />,
    )

    expect(screen.getByText('none')).toBeInTheDocument()
  })

  it('draws a bar for a measured zero', () => {
    const { container } = render(
      <VBars
        labels={WEEKS}
        series={[{ name: 'Calls', values: [4, 0, 6, 7], color: 'var(--seq-2)' }]}
        ariaLabel="Calls each week"
      />,
    )

    expect(screen.queryByText('none')).not.toBeInTheDocument()
    expect(container.querySelectorAll('path')).toHaveLength(4)
  })

  it('carries an accessible name', () => {
    render(
      <VBars
        labels={WEEKS}
        series={[{ name: 'Calls', values: [1, 2, 3, 4], color: 'var(--seq-2)' }]}
        ariaLabel="Calls each week"
      />,
    )

    expect(screen.getByRole('img', { name: 'Calls each week' })).toBeInTheDocument()
  })
})

describe('Sparkline', () => {
  it('breaks at a gap, like the full line chart', () => {
    const { container } = render(<Sparkline values={[1, 2, null, 3, 4]} label="Trend" />)

    expect(container.querySelectorAll('path')).toHaveLength(2)
  })

  it('keeps a measured value that has gaps on both sides', () => {
    // Without this an isolated point is silently dropped from the chart.
    const { container } = render(<Sparkline values={[1, null, 5, null, 2, 3]} label="Trend" />)

    const dots = container.querySelectorAll('circle')
    expect(dots.length).toBeGreaterThanOrEqual(2)
  })

  it('renders nothing rather than a single meaningless point', () => {
    const { container } = render(<Sparkline values={[5, null, null, null]} label="Trend" />)

    expect(container).toBeEmptyDOMElement()
  })
})

describe('Gauge', () => {
  it('draws no needle for a withheld figure', () => {
    // A needle parked at zero reads as a measured catastrophe.
    const { container } = render(<Gauge value={null} label="–" ariaLabel="Escalation integrity" />)

    expect(container.querySelector('line')).toBeNull()
  })

  it('draws a needle for a real figure', () => {
    const { container } = render(<Gauge value={64} label="64%" ariaLabel="Escalation integrity" />)

    expect(container.querySelector('line')).not.toBeNull()
  })
})

describe('Heatmap', () => {
  it('marks an empty cell with a dot, not the palest step', () => {
    // On a sequential scale the lightest step and "nothing here" look the
    // same, and the difference is the whole question the chart asks.
    const { container } = render(
      <Heatmap
        rows={['West']}
        columns={['Claims']}
        cells={[{ row: 'West', column: 'Claims', value: 0 }]}
        ariaLabel="Calls by region and topic"
      />,
    )

    expect(screen.getByText('·')).toBeInTheDocument()
    expect(container.querySelector('.nv-heat-none')).toBeInTheDocument()
  })

  it('steps the scale by share of the maximum', () => {
    const { container } = render(
      <Heatmap
        rows={['West', 'East']}
        columns={['Claims']}
        cells={[
          { row: 'West', column: 'Claims', value: 10 },
          { row: 'East', column: 'Claims', value: 1 },
        ]}
        ariaLabel="Calls by region and topic"
      />,
    )

    expect(container.querySelector('.nv-heat-3')).toBeInTheDocument()
    expect(container.querySelector('.nv-heat-1')).toBeInTheDocument()
  })
})

describe('MiniBars and BarCell', () => {
  it('always shows the number beside the bar', () => {
    // The bar is for comparing rows; nobody should estimate from it.
    render(<BarCell value={7} max={10} />)

    expect(screen.getByText('7')).toBeInTheDocument()
  })

  it('survives a zero maximum without dividing by it', () => {
    render(<BarCell value={0} max={0} />)

    expect(screen.getByText('0')).toBeInTheDocument()
  })

  it('labels the mini bars for assistive technology', () => {
    render(<MiniBars values={[1, 2, 5]} label="Rising across the quarter" />)

    expect(screen.getByRole('img', { name: 'Rising across the quarter' })).toBeInTheDocument()
  })
})

describe('niceMax', () => {
  it('rounds an axis top up to something readable', () => {
    expect(niceMax(3)).toBe(5)
    expect(niceMax(7)).toBe(10)
    expect(niceMax(42)).toBe(50)
  })

  it('never returns zero, which would collapse the axis', () => {
    expect(niceMax(0)).toBeGreaterThan(0)
  })
})
