"""Trends, tested for the ways a screen invents a finding.

Three of these matter more than the rest:

- a gap is not a zero,
- a rise that call volume explains is not a finding,
- two windows of different lengths are not comparable.

Each is a bug that produces a plausible number nobody can disprove by
looking at the screen.
"""

from __future__ import annotations

from datetime import date
from itertools import pairwise

import pytest

from domain.aggregation.call_tags import CallContext, CallTags, Window
from domain.aggregation.trends import (
    NOISE_THRESHOLD,
    as_of_window,
    emerging,
    movement,
    preceding,
    slice_window,
    weekly_series,
    weeks_in,
)
from domain.value_objects.category import Category
from domain.value_objects.outcome import Outcome


def call(reference: str, day: date, *, outcome: Outcome = Outcome.RESOLVED) -> CallContext:
    return CallContext(
        tags=CallTags(reference=reference, outcome=outcome, category=Category.CLAIMS_AND_EOB),
        occurred_on=day,
        employer_ref="EMP-01",
        broker_of_record_ref="BRK-01",
        agent_ref="AG-01",
    )


def unresolved(context: CallContext) -> bool:
    return context.tags.outcome is Outcome.UNRESOLVED


# --------------------------------------------------------------------------
# Gaps
# --------------------------------------------------------------------------


def test_a_week_with_no_calls_is_none_not_zero() -> None:
    """The distinction the charts depend on, and the easiest to lose.

    `len([]) == 0` is such a natural thing to write that the bug arrives by
    default. A week the corpus is silent about is not a week we measured
    nothing in.
    """
    window = Window(date(2026, 9, 1), date(2026, 9, 21))
    calls = [call("C-1", date(2026, 9, 2)), call("C-2", date(2026, 9, 16))]

    series = weekly_series(calls, window, lambda _: True)

    assert series == (1, None, 1)


def test_a_week_with_calls_but_no_hits_is_zero() -> None:
    """The other half. This one is a measurement and must render as one."""
    window = Window(date(2026, 9, 1), date(2026, 9, 14))
    calls = [
        call("C-1", date(2026, 9, 2), outcome=Outcome.UNRESOLVED),
        call("C-2", date(2026, 9, 9), outcome=Outcome.RESOLVED),
    ]

    assert weekly_series(calls, window, unresolved) == (1, 0)


def test_weeks_keep_a_partial_final_week() -> None:
    """A short bar a reader can see beats a week that silently vanished."""
    weeks = weeks_in(Window(date(2026, 9, 1), date(2026, 9, 10)))

    assert len(weeks) == 2
    assert weeks[-1] == Window(date(2026, 9, 8), date(2026, 9, 10))


# --------------------------------------------------------------------------
# Movement: the noise test
# --------------------------------------------------------------------------


def test_a_rise_that_volume_explains_is_not_a_finding() -> None:
    """Twice the calls carrying twice the failures is not a deterioration.

    Without normalising, every busy period reads as things getting worse and
    the reader learns to ignore the screen.
    """
    prior = [
        call(f"P-{i}", date(2026, 9, 1), outcome=Outcome.UNRESOLVED if i < 5 else Outcome.RESOLVED)
        for i in range(50)
    ]
    now = [
        call(
            f"N-{i}", date(2026, 9, 20), outcome=Outcome.UNRESOLVED if i < 10 else Outcome.RESOLVED
        )
        for i in range(100)
    ]

    result = movement("Unresolved", now=now, prior=prior, measure=unresolved)

    assert result.now == 10
    assert result.prior == 5
    assert result.expected == pytest.approx(10.0)
    assert not result.beyond_noise


def test_a_rise_beyond_what_volume_explains_is_reported() -> None:
    prior = [
        call(f"P-{i}", date(2026, 9, 1), outcome=Outcome.UNRESOLVED if i < 5 else Outcome.RESOLVED)
        for i in range(100)
    ]
    now = [
        call(
            f"N-{i}", date(2026, 9, 20), outcome=Outcome.UNRESOLVED if i < 25 else Outcome.RESOLVED
        )
        for i in range(100)
    ]

    result = movement("Unresolved", now=now, prior=prior, measure=unresolved)

    assert result.expected == pytest.approx(5.0)
    assert result.z >= NOISE_THRESHOLD
    assert result.beyond_noise


def test_a_tiny_expectation_does_not_make_everything_significant() -> None:
    """At batch-1 volume this is the common case, not an edge case.

    With a true Poisson denominator an expectation below one drives the
    standard deviation towards zero, and a single call becomes an
    overwhelming finding.
    """
    prior = [call("P-1", date(2026, 9, 1), outcome=Outcome.UNRESOLVED)]
    now = [
        call(f"N-{i}", date(2026, 9, 20), outcome=Outcome.UNRESOLVED if i < 2 else Outcome.RESOLVED)
        for i in range(3)
    ]

    result = movement("Unresolved", now=now, prior=prior, measure=unresolved)

    assert not result.beyond_noise


def _resolved(context: CallContext) -> bool:
    return context.tags.outcome is Outcome.RESOLVED


def test_direction_is_not_meaning() -> None:
    """Unresolved rising is bad; resolved rising is good."""
    prior = [call("P-1", date(2026, 9, 1), outcome=Outcome.RESOLVED)]
    now = [call(f"N-{i}", date(2026, 9, 20), outcome=Outcome.RESOLVED) for i in range(5)]

    bad_up = movement("Resolved", now=now, prior=prior, measure=_resolved, bad_when_up=True)
    good_up = movement("Resolved", now=now, prior=prior, measure=_resolved, bad_when_up=False)

    assert bad_up.worse
    assert not good_up.worse


def test_an_empty_prior_window_does_not_divide_by_zero() -> None:
    result = movement("Unresolved", now=[], prior=[], measure=unresolved)

    assert result.expected == 0.0
    assert not result.beyond_noise


# --------------------------------------------------------------------------
# Comparable windows
# --------------------------------------------------------------------------


def test_the_preceding_window_is_the_same_length() -> None:
    """Comparing four weeks against a quarter is the subtler way to
    manufacture a finding: both numbers are real."""
    window = Window(date(2026, 9, 1), date(2026, 9, 28))

    before = preceding(window)

    assert before.end == date(2026, 8, 31)
    assert (before.end - before.start) == (window.end - window.start)


def test_a_window_is_sliced_into_equal_parts() -> None:
    parts = slice_window(Window(date(2026, 7, 6), date(2026, 9, 25)), 3)

    assert len(parts) == 3
    assert parts[0].start == date(2026, 7, 6)
    assert parts[-1].end == date(2026, 9, 25)


def test_no_day_falls_outside_a_slice() -> None:
    """A remainder left unsliced would silently drop calls from the rollup."""
    window = Window(date(2026, 9, 1), date(2026, 9, 20))
    parts = slice_window(window, 3)

    assert parts[0].start == window.start
    assert parts[-1].end == window.end
    for earlier, later in pairwise(parts):
        assert (later.start - earlier.end).days == 1


def test_a_window_too_short_to_slice_returns_nothing() -> None:
    assert slice_window(Window(date(2026, 9, 1), date(2026, 9, 2)), 3) == ()


# --------------------------------------------------------------------------
# Emerging
# --------------------------------------------------------------------------


def test_emerging_counts_each_value_across_slices() -> None:
    window = Window(date(2026, 9, 1), date(2026, 9, 30))
    calls = [
        call("C-1", date(2026, 9, 2)),
        call("C-2", date(2026, 9, 25)),
        call("C-3", date(2026, 9, 26)),
    ]

    rows = emerging(
        calls,
        window,
        kind="category",
        key_of=lambda c: c.tags.category.value if c.tags.category else None,
    )

    assert len(rows) == 1
    assert rows[0].buckets[0].hits == 1
    assert rows[0].buckets[-1].hits == 2
    assert rows[0].delta == 1
    assert rows[0].rising


def test_a_call_the_attribute_does_not_apply_to_is_left_out() -> None:
    """Not bucketed under an empty key.

    "No touchpoint recorded" is a real finding on its own screen; smuggling
    it in here as a topic would put a phantom row at the top of a list of
    rising topics.
    """
    window = Window(date(2026, 9, 1), date(2026, 9, 30))
    calls = [call("C-1", date(2026, 9, 2)), call("C-2", date(2026, 9, 25))]

    rows = emerging(calls, window, kind="touchpoint", key_of=lambda c: c.tags.touchpoint)

    assert rows == ()


def test_emerging_is_ordered_largest_rise_first_and_stably() -> None:
    """Equal deltas must not reshuffle between requests."""
    window = Window(date(2026, 9, 1), date(2026, 9, 30))
    calls = [
        call("C-1", date(2026, 9, 2)),
        call("C-2", date(2026, 9, 26)),
    ]

    rows = emerging(calls, window, kind="broker", key_of=lambda c: c.broker_of_record_ref)
    again = emerging(calls, window, kind="broker", key_of=lambda c: c.broker_of_record_ref)

    assert [row.key for row in rows] == [row.key for row in again]


def test_as_of_window_ends_on_the_date_given() -> None:
    window = as_of_window(date(2026, 9, 28), weeks=4)

    assert window.end == date(2026, 9, 28)
    assert round(window.weeks) == 4
