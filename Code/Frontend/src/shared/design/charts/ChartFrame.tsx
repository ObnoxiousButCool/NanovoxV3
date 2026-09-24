/**
 * The axes, gridlines and legend that `VBars` and `VLine` share.
 *
 * ## `null` is a gap, not a zero
 *
 * The contract every chart here honours. A week with no calls is not a week
 * with zero of something — it is a week we know nothing about, and drawing
 * it at the baseline claims a measurement that was never taken. Series carry
 * `(number | null)[]`, and `null` leaves a hole: the line breaks, the bar is
 * absent, and the band can say "none" underneath.
 *
 * This is the same principle as a withheld figure never rendering as zero,
 * applied to a shape instead of a number.
 */

import type { ReactNode } from 'react'

import { niceMax } from '@/shared/design/charts/useElementWidth'

export interface Series {
  name: string
  /** `null` is a gap. Never substitute zero. */
  values: (number | null)[]
  /** A CSS token reference, e.g. `var(--seq-2)`. */
  color: string
}

export interface ChartGeometry {
  width: number
  height: number
  padding: { top: number; right: number; bottom: number; left: number }
  /** Maps a value to a y coordinate. */
  y: (value: number) => number
  /** Width of one x band. */
  band: number
  low: number
}

export interface ChartFrameProps {
  labels: string[]
  series: Series[]
  width: number
  height?: number
  suffix?: string
  yMax?: number
  ticks?: number
  ariaLabel: string
  /** Draws the data. Called with resolved geometry. */
  children: (geometry: ChartGeometry) => ReactNode
}

export function ChartFrame({
  labels,
  series,
  width,
  height = 240,
  suffix = '',
  yMax,
  ticks = 4,
  ariaLabel,
  children,
}: ChartFrameProps) {
  const padding = { top: 12, right: 12, bottom: 30, left: 38 }
  const low = 0
  const observed = series.flatMap((s) => s.values.filter((v): v is number => v !== null))
  const high = yMax ?? niceMax(Math.max(...observed, 1))

  const y = (value: number): number =>
    padding.top + (1 - (value - low) / (high - low)) * (height - padding.top - padding.bottom)

  const inner = width - padding.left - padding.right
  const band = inner / Math.max(labels.length, 1)

  // On a narrow chart, label every other band rather than overlapping them.
  const every = labels.length > 8 && width < 520 ? 2 : 1

  return (
    <div className="nv-chart">
      <div className="nv-legend">
        {series.map((s) => (
          <span key={s.name}>
            <i style={{ background: s.color }} />
            {s.name}
          </span>
        ))}
      </div>
      <svg width={width} height={height} role="img" aria-label={ariaLabel}>
        {Array.from({ length: ticks + 1 }, (_, i) => {
          const value = low + ((high - low) * i) / ticks
          return (
            <g key={i}>
              <line
                x1={padding.left}
                x2={width - padding.right}
                y1={y(value)}
                y2={y(value)}
                stroke="var(--rule)"
                strokeWidth={1}
              />
              <text
                x={padding.left - 8}
                y={y(value) + 4}
                textAnchor="end"
                fontSize={12}
                fill="var(--ink-3)"
              >
                {Math.round(value * 10) / 10}
                {suffix}
              </text>
            </g>
          )
        })}

        {labels.map((label, i) =>
          i % every === 0 ? (
            <text
              key={label + String(i)}
              x={padding.left + band * i + band / 2}
              y={height - padding.bottom + 18}
              textAnchor="middle"
              fontSize={12}
              fill="var(--ink-2)"
            >
              {label}
            </text>
          ) : null,
        )}

        {children({ width, height, padding, y, band, low })}
      </svg>
    </div>
  )
}
