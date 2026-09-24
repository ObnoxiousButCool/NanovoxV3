/**
 * A semicircle gauge, 0–100, with the band the value sits in.
 *
 * Used for escalation integrity on the executive screen, where the number is
 * a percentage of a *small* denominator — handled ÷ warranted, not ÷ all
 * calls. The gauge shows the bands so 64% reads as "in the red third"
 * rather than as a bare number a reader has to have a policy in mind to
 * interpret.
 *
 * A `null` value draws **no needle at all** and labels itself. A gauge with
 * its needle parked at zero is the most misleading rendering available here:
 * it looks like a measured catastrophe rather than an absent measurement.
 */

const RADIUS = 60
const CX = 75
const CY = 72

/** Where a percentage sits on the arc. */
function point(percent: number): [number, number] {
  const angle = Math.PI * (1 - percent / 100)
  return [CX + RADIUS * Math.cos(angle), CY - RADIUS * Math.sin(angle)]
}

function arc(from: number, to: number, color: string, key: string) {
  const [sx, sy] = point(from)
  const [ex, ey] = point(to)
  return (
    <path
      key={key}
      d={`M${sx.toFixed(1)},${sy.toFixed(1)} A${String(RADIUS)},${String(RADIUS)} 0 0 1 ${ex.toFixed(1)},${ey.toFixed(1)}`}
      stroke={color}
      strokeWidth={12}
      fill="none"
    />
  )
}

export function Gauge({
  value,
  label,
  ariaLabel,
}: {
  /** 0–100, or `null` when the figure is withheld. */
  value: number | null
  label: string
  ariaLabel: string
}) {
  const tone =
    value === null
      ? 'var(--ink-3)'
      : value >= 90
        ? 'var(--good)'
        : value >= 75
          ? 'var(--warning)'
          : 'var(--critical)'

  const needle = value === null ? null : point(value)

  return (
    <div className="nv-gauge">
      <svg viewBox="0 0 150 84" role="img" aria-label={ariaLabel}>
        {arc(0, 74.5, 'color-mix(in srgb, var(--critical) 75%, transparent)', 'low')}
        {arc(75.5, 89.5, 'color-mix(in srgb, var(--warning) 80%, transparent)', 'mid')}
        {arc(90.5, 100, 'color-mix(in srgb, var(--good) 75%, transparent)', 'high')}
        {needle ? (
          <>
            <line
              x1={CX}
              y1={CY}
              x2={((CX + needle[0]) / 2 + (needle[0] - CX) * 0.25).toFixed(1)}
              y2={((CY + needle[1]) / 2 + (needle[1] - CY) * 0.25).toFixed(1)}
              stroke="var(--ink-2)"
              strokeWidth={4}
              strokeLinecap="round"
            />
            <circle cx={CX} cy={CY} r={5} fill="var(--ink-2)" />
          </>
        ) : null}
      </svg>
      <span className="nv-gv" style={{ color: tone }}>
        {label}
      </span>
    </div>
  )
}
