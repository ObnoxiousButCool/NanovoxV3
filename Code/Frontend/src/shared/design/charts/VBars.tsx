/**
 * Grouped vertical bars.
 *
 * A `null` draws nothing and the band is labelled "none" beneath, so a week
 * with no calls is visibly absent rather than sitting at zero. A `0` is a
 * real measurement and does draw — as a two-pixel stub, so "we measured
 * nothing" and "we measured zero" are distinguishable at a glance.
 */

import { ChartFrame } from '@/shared/design/charts/ChartFrame'
import type { Series } from '@/shared/design/charts/ChartFrame'
import { useElementWidth } from '@/shared/design/charts/useElementWidth'

export function VBars({
  labels,
  series,
  height = 240,
  suffix,
  ariaLabel,
}: {
  labels: string[]
  series: Series[]
  height?: number
  suffix?: string
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
        ariaLabel={ariaLabel}
      >
        {({ padding, y, band, low }) => {
          const count = series.length
          const gap = Math.min(band * 0.28, 26)
          const barWidth = Math.max(Math.min((band - gap) / count, 18), 3)

          return (
            <>
              {labels.map((label, i) => {
                const missing = series.every((s) => s.values[i] === null)
                return (
                  <g key={label + String(i)}>
                    {series.map((s, si) => {
                      const value = s.values[i]
                      if (value === null || value === undefined) return null
                      const top = y(value)
                      const bottom = y(low)
                      const barHeight = Math.max(bottom - top, 2)
                      const x =
                        padding.left +
                        band * i +
                        (band - barWidth * count - (count - 1) * 2) / 2 +
                        si * (barWidth + 2)
                      const radius = Math.min(3, barWidth / 2)
                      return (
                        <path
                          key={s.name}
                          d={`M${String(x)},${String(bottom)}V${String(bottom - barHeight + radius)}Q${String(x)},${String(bottom - barHeight)} ${String(x + radius)},${String(bottom - barHeight)}H${String(x + barWidth - radius)}Q${String(x + barWidth)},${String(bottom - barHeight)} ${String(x + barWidth)},${String(bottom - barHeight + radius)}V${String(bottom)}Z`}
                          fill={s.color}
                        />
                      )
                    })}
                    {missing ? (
                      <text
                        x={padding.left + band * i + band / 2}
                        y={y(low) - 8}
                        textAnchor="middle"
                        fontSize={11}
                        fill="var(--ink-3)"
                      >
                        none
                      </text>
                    ) : null}
                  </g>
                )
              })}
            </>
          )
        }}
      </ChartFrame>
    </div>
  )
}
