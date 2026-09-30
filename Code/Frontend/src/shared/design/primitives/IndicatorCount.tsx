/**
 * How many of the ten indicator families fired — or that nobody looked.
 *
 * Two different noughts reach this component and they are opposite
 * statements:
 *
 * - **Assessed, none fired.** The families were tested against this account
 *   and cleared it. That is a finding.
 * - **Too few calls to assess.** `indicators.min_employer_calls` is 5 and
 *   metric 10's own floor is 3, so an account can be eligible for the flag
 *   and below the floor for the families. Nothing was tested. That is a gap.
 *
 * A bare `0` renders them identically, and beside the word "Flagged" it
 * reads as a flag with nothing behind it — which is exactly the reading
 * Ranjit challenged on 2026-09-30, twice: Junipero Restaurant Group and
 * Blue Mesa Advisors both showed "0 of 10" while carrying four families of
 * real hits apiece, unexamined because they have 3 and 4 calls.
 *
 * Shared rather than written per screen because the two screens that show
 * this number disagreed: the account picker had the dash and the risk table
 * still printed "0 of 10". One component, so a third screen cannot invent a
 * third answer.
 */

export function IndicatorCount({
  assessed,
  count,
  total,
  unassessed = '—',
}: {
  /** False when the account is below the families' own call floor. */
  assessed: boolean
  count: number
  /**
   * Renders as `count of total` when given, and as the bare count when not:
   * the risk table has room for "3 of 10" and the account picker does not.
   */
  total?: number
  /**
   * What "nobody looked" reads as. An em-dash in a table cell or beside a
   * flag, where there is no room to say it; words where there is, as in the
   * exec feed's "not assessed · Sep". Either way the dashed, dimmed styling
   * and the explanation on hover come from here, so a screen cannot show
   * this state without them.
   */
  unassessed?: string
}) {
  if (!assessed) {
    return (
      <i className="nv-unassessed" title="Too few calls to assess the indicator families">
        {unassessed}
      </i>
    )
  }
  return <>{total === undefined ? count : `${String(count)} of ${String(total)}`}</>
}
