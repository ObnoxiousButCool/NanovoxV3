/**
 * A ring chart with a hero number at its centre.
 *
 * Categorical identity (which driver, which category), never magnitude by
 * itself — the center number is the total the ring divides, not a measured
 * value of its own. Segments carry a 2px gap at both ends (the house style
 * for adjacent/stacked fills, `nv-chart`'s own convention) rather than
 * touching, so a reader can tell where one driver ends and the next begins
 * without relying on the colour boundary alone.
 *
 * Direct labels live beside this component (its own legend), not inside
 * it: the ring is the same component whether five slices or two, and a
 * legend that counts and ranks them is specific to what is being compared.
 */

export interface DonutSlice {
  key: string
  value: number
  color: string
}

const SIZE = 160
const CENTER = SIZE / 2
const RADIUS = 60
const STROKE = 20
const CIRCUMFERENCE = 2 * Math.PI * RADIUS
const GAP = 2

export function Donut({
  slices,
  centerValue,
  centerLabel,
  ariaLabel,
  rounded = true,
}: {
  slices: readonly DonutSlice[]
  centerValue: string
  centerLabel: string
  ariaLabel: string
  /** Use flat segment ends when matching designs with a continuous ring. */
  rounded?: boolean
}) {
  const total = slices.reduce((sum, slice) => sum + slice.value, 0)
  let offset = 0

  return (
    <div className="nv-donut">
      <svg viewBox={`0 0 ${String(SIZE)} ${String(SIZE)}`} role="img" aria-label={ariaLabel}>
        <circle
          cx={CENTER}
          cy={CENTER}
          r={RADIUS}
          fill="none"
          stroke="var(--rule)"
          strokeWidth={STROKE}
        />
        {total > 0
          ? slices.map((slice) => {
              if (slice.value <= 0) return null
              const length = Math.max((slice.value / total) * CIRCUMFERENCE - GAP, 0)
              const dash = `${length.toFixed(1)} ${(CIRCUMFERENCE - length).toFixed(1)}`
              const rotation = (offset / CIRCUMFERENCE) * 360 - 90
              offset += (slice.value / total) * CIRCUMFERENCE
              return (
                <circle
                  key={slice.key}
                  cx={CENTER}
                  cy={CENTER}
                  r={RADIUS}
                  fill="none"
                  stroke={slice.color}
                  strokeWidth={STROKE}
                  strokeDasharray={dash}
                  strokeLinecap={rounded ? 'round' : 'butt'}
                  transform={`rotate(${rotation.toFixed(2)} ${String(CENTER)} ${String(CENTER)})`}
                />
              )
            })
          : null}
      </svg>
      <div className="nv-donut-center">
        <b>{centerValue}</b>
        <span>{centerLabel}</span>
      </div>
    </div>
  )
}
