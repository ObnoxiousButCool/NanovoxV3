/**
 * The small charts that sit inside text and table cells.
 *
 * All of them take the same `null`-is-a-gap contract as the full charts.
 * None of them has an axis, so none of them is readable on its own — each is
 * a shape beside a number that carries the actual value, never a replacement
 * for it.
 */

/**
 * A trend line small enough to sit in a table cell.
 *
 * Drawn at a fixed size because it has no axis to keep legible and no labels
 * to hold at 12px — the reason the full charts measure their container does
 * not apply here.
 */
export function Sparkline({
  values,
  width = 70,
  height = 20,
  color = 'var(--seq-2)',
  label,
}: {
  values: (number | null)[]
  width?: number
  height?: number
  color?: string
  label: string
}) {
  const measured = values.filter((v): v is number => v !== null)
  if (measured.length < 2) return null

  const max = Math.max(...measured, 1)
  const step = (width - 6) / Math.max(values.length - 1, 1)
  const points = values.map((value, i) =>
    value === null ? null : ([3 + i * step, height - 3 - (value / max) * (height - 7)] as const),
  )

  // Same rule as VLine: a gap breaks the path rather than interpolating.
  const segments: (readonly [number, number])[][] = []
  let current: (readonly [number, number])[] = []
  for (const point of points) {
    if (point === null) {
      if (current.length > 1) segments.push(current)
      current = []
      continue
    }
    current.push(point)
  }
  if (current.length > 1) segments.push(current)

  // A lone measured point cannot form a segment, but dropping it would make
  // a value surrounded by gaps disappear from the chart. Dot it instead.
  const isolated = points.filter(
    (point, i): point is readonly [number, number] =>
      point !== null && (points[i - 1] ?? null) === null && (points[i + 1] ?? null) === null,
  )
  const last = points.filter((p): p is readonly [number, number] => p !== null).at(-1)

  return (
    <svg
      viewBox={`0 0 ${String(width)} ${String(height)}`}
      width={width}
      height={height}
      role="img"
      aria-label={label}
      className="nv-spark"
    >
      {segments.map((segment, i) => (
        <path
          key={i}
          d={`M${segment.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join('L')}`}
          fill="none"
          stroke={color}
          strokeWidth={1.75}
          strokeLinejoin="round"
        />
      ))}
      {isolated.map(([x, y], i) => (
        <circle key={`iso-${String(i)}`} cx={x.toFixed(1)} cy={y.toFixed(1)} r={2.2} fill={color} />
      ))}
      {last ? <circle cx={last[0].toFixed(1)} cy={last[1].toFixed(1)} r={2.8} fill={color} /> : null}
    </svg>
  )
}

/**
 * Three or four buckets as tiny bars, for "is this rising?".
 *
 * The final bucket is coloured differently because it is the one being
 * claimed about; the earlier ones are context.
 */
export function MiniBars({
  values,
  color = 'var(--seq-3)',
  label,
}: {
  values: number[]
  color?: string
  label: string
}) {
  const max = Math.max(...values, 1)
  return (
    <span className="nv-minibars" role="img" aria-label={label}>
      {values.map((value, i) => (
        <i
          key={i}
          style={{
            height: `${String(Math.max(8, Math.round((value / max) * 100)))}%`,
            background: i === values.length - 1 ? color : 'var(--seq-1)',
          }}
        >
          <b>{value}</b>
        </i>
      ))}
    </span>
  )
}

/**
 * A bar inside a table cell, with the number beside it.
 *
 * The number is always present. The bar is for comparing rows at a glance;
 * it is not the value, and a reader should never have to estimate from it.
 */
export function BarCell({ value, max, bad = false }: { value: number; max: number; bad?: boolean }) {
  const percent = max > 0 ? Math.max(4, Math.round((value / max) * 100)) : 0
  return (
    <div className="nv-barcell">
      <div className="nv-track">
        <i className={bad ? 'nv-bad' : undefined} style={{ width: `${String(percent)}%` }} />
      </div>
      <span>{value}</span>
    </div>
  )
}
