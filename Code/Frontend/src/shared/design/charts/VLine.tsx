/**
 * Lines with a dot on every measured point.
 *
 * `null` **breaks the line**. This is the one that matters most: a line
 * drawn straight through a missing week interpolates a measurement nobody
 * took, and it is invisible — the chart looks complete and reads as
 * continuous evidence. Breaking the segment makes the hole visible, which is
 * the honest rendering of "we do not know".
 *
 * Segments are accumulated and flushed at each gap, so a series with holes
 * becomes several paths rather than one.
 */

import { ChartFrame } from '@/shared/design/charts/ChartFrame'
import type { Series } from '@/shared/design/charts/ChartFrame'
import { useElementWidth } from '@/shared/design/charts/useElementWidth'

export function VLine({
  labels,
  series,
  height = 240,
  suffix,
  yMax,
  ariaLabel,
}: {
  labels: string[]
  series: Series[]
  height?: number
  suffix?: string
  yMax?: number
  ariaLabel: string
}) {
  const [ref, width] = useElementWidth<HTMLDivElement>()

  return (
    <div ref={ref} className="nv-chart-host">
      <ChartFrame
        labels={labels}
        series={series}
        width={width}
        height={height}
        {...(suffix === undefined ? {} : { suffix })}
        {...(yMax === undefined ? {} : { yMax })}
        ariaLabel={ariaLabel}
      >
        {({ padding, y, band }) => (
          <>
            {series.map((s) => {
              const segments: [number, number][][] = []
              let current: [number, number][] = []

              s.values.forEach((value, i) => {
                if (value === null) {
                  if (current.length > 1) segments.push(current)
                  current = []
                  return
                }
                current.push([padding.left + band * i + band / 2, y(value)])
              })
              if (current.length > 1) segments.push(current)

              return (
                <g key={s.name}>
                  {segments.map((points, index) => (
                    <path
                      key={index}
                      d={`M${points.map(([x, py]) => `${String(x)},${String(py)}`).join('L')}`}
                      fill="none"
                      stroke={s.color}
                      strokeWidth={2}
                      strokeLinejoin="round"
                      strokeLinecap="round"
                    />
                  ))}
                  {s.values.map((value, i) =>
                    value === null ? null : (
                      <circle
                        key={i}
                        cx={padding.left + band * i + band / 2}
                        cy={y(value)}
                        r={3.5}
                        fill={s.color}
                        stroke="var(--surface)"
                        strokeWidth={1.5}
                      />
                    ),
                  )}
                </g>
              )
            })}
          </>
        )}
      </ChartFrame>
    </div>
  )
}
