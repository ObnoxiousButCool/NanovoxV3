/**
 * A status, distinguished by **shape as well as colour**.
 *
 * The shape is not decoration. These pages are printed, often in greyscale,
 * and about one man in twelve cannot separate the red from the amber. A pill
 * that carries its meaning only in its colour is unreadable to both, so each
 * status has its own mark: a triangle, a disc, a rotated square, a ring.
 *
 * ## Why this is not a four-level band
 *
 * The prototype renders High / Elevated / Watch / None. `dashboard.yaml`
 * (decision D2) says metric 10 is a **yes/no flag**, and the ten indicator
 * families are informational and never set it. Which of those the word
 * "flagged" names is conflict **C1**, still open.
 *
 * So this renders the three states the API actually returns today, and the
 * shape vocabulary is kept general. If C1 settles on the band, the extra
 * statuses are two more entries here rather than a rewrite.
 */

export type StatusTone = 'flagged' | 'notFlagged' | 'ineligible'

const LABELS: Record<StatusTone, string> = {
  flagged: 'Flagged',
  notFlagged: 'Not flagged',
  // Never "no risk". Too few calls to assess is not a clean bill of health,
  // and the risk screen exists partly to stop that being implied.
  ineligible: 'Not enough calls to assess',
}

export function StatusPill({ tone, children }: { tone: StatusTone; children?: React.ReactNode }) {
  return (
    <span className={`nv-pill nv-pill-${tone}`}>{children ?? LABELS[tone]}</span>
  )
}

/** The pill for one account's standing, straight from the risk response. */
export function RiskPill({ eligible, flagged }: { eligible: boolean; flagged: boolean }) {
  if (!eligible) return <StatusPill tone="ineligible" />
  return <StatusPill tone={flagged ? 'flagged' : 'notFlagged'} />
}
