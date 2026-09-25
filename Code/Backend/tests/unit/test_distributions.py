"""How calls ended, week by week — the v2 risk page's three charts.

The assertions here are about the two kinds of nothing. A week with no
calls and a week with four calls both produce a blank in the share line,
and they mean opposite things: one is a quiet week, the other is a week we
cannot describe. Collapsing them is the failure this module exists to
avoid.
"""

from __future__ import annotations

from datetime import date

from domain.aggregation.call_tags import CallContext, CallTags, Window
from domain.aggregation.distributions import (
    SHARE_MIN_CALLS,
    good_quality,
    outcome_counts,
    resolved,
    weekly_shares,
)
from domain.dashboard_config import QualityBands
from domain.value_objects.outcome import Outcome

WINDOW = Window(start=date(2026, 9, 1), end=date(2026, 9, 14))


def _call(day: int, *, outcome: Outcome | None = None, score: int | None = None) -> CallContext:
    return CallContext(
        tags=CallTags(reference=f"C-{day:04d}", outcome=outcome, quality_score=score),
        occurred_on=date(2026, 9, day),
    )


def test_every_outcome_is_reported_including_the_ones_at_zero() -> None:
    """An absent category is a finding, and a chart that drops it hides one.

    No escalations at all is worth seeing. Ordering by size instead of by
    the workbook would also make two weeks' charts incomparable.
    """
    counts = outcome_counts([_call(2, outcome=Outcome.RESOLVED)])

    assert len(counts) == len(Outcome)
    assert {entry.outcome for entry in counts} == set(Outcome)
    assert [entry.outcome for entry in counts] == list(Outcome)
    assert sum(entry.calls for entry in counts) == 1


def test_a_call_with_no_outcome_is_counted_in_no_outcome() -> None:
    """Unrecorded is not a fifth outcome, and it is not 'resolved'."""
    counts = outcome_counts([_call(2), _call(3, outcome=Outcome.RESOLVED)])

    assert sum(entry.calls for entry in counts) == 1


def test_a_silent_week_and_a_small_week_are_different_blanks() -> None:
    """The distinction the charts are drawn from.

    Week one has no calls: the line breaks. Week two has four, which is
    under the floor: the count is shown and the share is withheld. Both
    render as a gap in the share, and only one is an absence of calls.
    """
    calls = [_call(day, outcome=Outcome.RESOLVED) for day in (8, 9, 10, 11)]

    weeks = weekly_shares(calls, WINDOW, resolved)

    silent, small = weeks[0], weeks[1]
    assert silent.calls is None and silent.matched is None and silent.share is None
    assert small.calls == 4
    assert small.matched == 4
    assert small.share is None, "four calls is under the floor"


def test_a_week_at_the_floor_publishes_its_share() -> None:
    calls = [_call(day, outcome=Outcome.RESOLVED) for day in range(8, 8 + SHARE_MIN_CALLS)]

    weeks = weekly_shares(calls, WINDOW, resolved)

    assert weeks[1].calls == SHARE_MIN_CALLS
    assert weeks[1].share == 1.0


def test_a_measured_zero_is_zero_and_not_a_gap() -> None:
    """Calls happened and none matched. That is a measurement."""
    calls = [_call(day, outcome=Outcome.UNRESOLVED) for day in range(8, 8 + SHARE_MIN_CALLS)]

    weeks = weekly_shares(calls, WINDOW, resolved)

    assert weeks[1].matched == 0
    assert weeks[1].share == 0.0


def test_an_unscored_call_is_not_good_quality_and_still_counts_below_the_line() -> None:
    """The share becomes a floor rather than an estimate.

    An ungraded call happened, so it belongs in the denominator. Nobody
    graded it, so it cannot be in the numerator. Dropping it from both
    would quietly raise the quality share of every week with a gap in it.
    """
    bands = QualityBands(good_min=86, average_min=60)
    calls = [_call(8, score=90), _call(9, score=None), *[_call(d, score=40) for d in (10, 11, 12)]]

    weeks = weekly_shares(calls, WINDOW, good_quality(bands))

    assert weeks[1].calls == 5
    assert weeks[1].matched == 1
    assert weeks[1].share == 0.2
