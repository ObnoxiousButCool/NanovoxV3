/**
 * A ring chart with a hero number at its centre.
 *
 * Categorical identity (which driver, which category), never magnitude by
 * itself — the center number is the total the ring divides, not a measured
 * value of its own. Segments meet edge-to-edge; colour distinguishes each
 * driver without adding gaps to the ring.
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
// At the 160px viewBox scale this gives an outer radius of 72px and an
// inner radius of 54px, matching the reference ring's 75% hole ratio.
const RADIUS = 63
const STROKE = 18
const CIRCUMFERENCE = 2 * Math.PI * RADIUS
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
              const length = (slice.value / total) * CIRCUMFERENCE
              const dash = `${length} ${CIRCUMFERENCE - length}`
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
                  transform={`rotate(${rotation} ${String(CENTER)} ${String(CENTER)})`}
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
