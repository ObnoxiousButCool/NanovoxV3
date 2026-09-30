/**
 * How an outcome's code is drawn — shared by every screen that shows one,
 * so `/risk`'s stacked bar and `/calls`' table row can never disagree about
 * what "escalated" looks like.
 *
 * Colours are the prototype's own outcome set (`--s3`/`--s4`/`--seq-2`/
 * `--critical`), not the general good/warning ramp: `--good` and `--warning`
 * already mean something else elsewhere (tile tone), and reusing them here
 * would make an outcome look like a status readout rather than one of four
 * equally-real endings a call has.
 */
export const OUTCOME_COLOR: Record<string, string> = {
  RESOLVED: 'var(--s3)',
  PARTIALLY_RESOLVED: 'var(--s4)',
  ESCALATED: 'var(--seq-2)',
  UNRESOLVED: 'var(--critical)',
}
