"""Member effort and complexity — composites, not v9 fields.

"Not corpus values... the UI labels them 'derived' wherever they appear"
(Prototype/tools/03_join_corpus.py). The workbook has no field for
either, and nothing here stands in for one — these exist only because the
prototype invented them, and are ported (not re-derived) from its own
formula so the two stay comparable.

Both formulas take a call's **percentile rank** against the rest of the
corpus for talk time and turn count, not raw values — a five-minute call
reads as long against a mostly two-minute corpus and short against a
mostly ten-minute one. `percentile_rank` computes that ranking; it is
deliberately not folded into the scoring functions below, because ranking
needs every other call's value and the two composite scores only need
this one call's already-ranked position — mixing the two would mean
recomputing the whole corpus's ranking to score one call.
"""

from __future__ import annotations

from collections.abc import Sequence

from domain.value_objects.outcome import Outcome

MAX_SCORE = 100


def percentile_rank(sorted_values: Sequence[float], value: float) -> float:
    """Where `value` sits against `sorted_values`, as a fraction in [0, 1].

    ``sorted_values`` must already be sorted ascending. Ties rank at the
    share of the corpus strictly below them, matching the prototype's own
    definition exactly.
    """
    lower_count = sum(1 for other in sorted_values if other < value)
    return min(lower_count / max(len(sorted_values) - 1, 1), 1.0)


def effort_score(
    *,
    aht_percentile: float,
    is_failure_driven_repeat: bool,
    escalation_requested_by_caller: bool,
    outcome: Outcome,
    escalation_triggered: bool,
    escalation_handled: bool,
) -> int:
    """How much the member had to work for this call to happen, 0-100."""
    score = 45 * aht_percentile
    if is_failure_driven_repeat:
        score += 20
    if escalation_requested_by_caller:
        score += 12
    if outcome is Outcome.UNRESOLVED:
        score += 18
    elif outcome is Outcome.PARTIALLY_RESOLVED:
        score += 8
    if escalation_triggered and not escalation_handled:
        score += 10
    return round(min(score, MAX_SCORE))


def complexity_score(
    *,
    aht_percentile: float,
    turn_count_percentile: float,
    rule_ref_count: int,
    signal_count: int,
) -> int:
    """How complicated the call itself was, 0-100."""
    score = 55 * aht_percentile + 45 * turn_count_percentile
    if rule_ref_count >= 2:
        score += 8
    if signal_count >= 2:
        score += 6
    return round(min(score, MAX_SCORE))
