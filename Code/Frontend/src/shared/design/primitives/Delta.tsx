/**
 * A change between two periods.
 *
 * `badWhenUp` exists because direction is not meaning: unresolved calls
 * rising is bad, resolved calls rising is good, and a component that
 * coloured every increase red would be wrong half the time.
 *
 * Renders nothing rather than "0%" when the prior period is zero. A
 * percentage change from nothing is not a large increase, it is undefined,
 * and printing one invents a number.
 */

export function Delta({
  now,
  prior,
  badWhenUp = true,
}: {
  now: number
  prior: number
  badWhenUp?: boolean
}) {
  if (prior === 0) {
    return (
      <span className="nv-delta nv-flat" title="No prior period to compare against.">
        new
      </span>
    )
  }
  const change = Math.round(((now - prior) / prior) * 100)
  if (change === 0) return <span className="nv-delta nv-flat">no change</span>

  const worse = change > 0 ? badWhenUp : !badWhenUp
  return (
    <span className={`nv-delta ${worse ? 'nv-up' : 'nv-down'}`}>
      {change > 0 ? '+' : ''}
      {change}%
    </span>
  )
}
