"""Metric 4's linkage, at the boundaries that decide it.

Consolidated from the two implementations the parallel streams each built —
Stream A's `domain/derivations/repeat_contact.py` and Stream B's
`domain/aggregation/repeat_contact.py`. They agreed on every rule and
differed only in types, so one survives and both sets of cases are kept
here. The boundary and direction cases came from Stream A's suite and are
the ones a second implementation would most likely get differently.
"""

from __future__ import annotations

from collections.abc import Sequence

from domain.aggregation.call_tags import CallContext
from domain.aggregation.repeat_contact import (
    EXPOSURE_DAYS,
    exposed_unresolved,
    failure_driven_repeats,
    repeats,
)
from domain.value_objects.category import Category
from domain.value_objects.outcome import Outcome
from tests.fixtures.tagged_calls import WINDOW, call, day


def _refs(calls: Sequence[CallContext]) -> set[str]:
    return {call.reference for call in calls}


def test_an_unresolved_call_followed_within_fourteen_days_is_a_repeat() -> None:
    traffic = (
        call("C-0001", caller_ref="CB-1", outcome=Outcome.UNRESOLVED, on=day(0)),
        call("C-0002", caller_ref="CB-1", on=day(3)),
    )

    assert _refs(failure_driven_repeats(traffic)) == {"C-0001"}


def test_a_contact_exactly_on_the_fourteenth_day_still_counts() -> None:
    """The boundary is inclusive. Two implementations of a 14-day window
    disagree here first, and neither would look wrong.
    """
    traffic = (
        call("C-0001", caller_ref="CB-1", outcome=Outcome.UNRESOLVED, on=day(0)),
        call("C-0002", caller_ref="CB-1", on=day(EXPOSURE_DAYS)),
    )

    assert _refs(failure_driven_repeats(traffic)) == {"C-0001"}


def test_a_contact_one_day_past_the_window_does_not_count() -> None:
    traffic = (
        call("C-0001", caller_ref="CB-1", outcome=Outcome.UNRESOLVED, on=day(0)),
        call("C-0002", caller_ref="CB-1", on=day(EXPOSURE_DAYS + 1)),
    )

    assert failure_driven_repeats(traffic) == ()


def test_a_resolved_call_is_never_failure_driven_however_often_they_call_back() -> None:
    traffic = (
        call("C-0001", caller_ref="CB-1", outcome=Outcome.RESOLVED, on=day(0)),
        call("C-0002", caller_ref="CB-1", on=day(2)),
    )

    assert failure_driven_repeats(traffic) == ()


def test_another_callers_later_contact_is_not_a_repeat() -> None:
    traffic = (
        call("C-0001", caller_ref="CB-1", outcome=Outcome.UNRESOLVED, on=day(0)),
        call("C-0002", caller_ref="CB-2", on=day(2)),
    )

    assert failure_driven_repeats(traffic) == ()


def test_an_earlier_contact_from_the_same_caller_is_not_a_repeat() -> None:
    """Direction matters. A call that *follows* is a repeat; one that
    preceded it is the thing being repeated.
    """
    traffic = (
        call("C-0001", caller_ref="CB-1", on=day(0)),
        call("C-0002", caller_ref="CB-1", outcome=Outcome.UNRESOLVED, on=day(5)),
    )

    assert failure_driven_repeats(traffic) == ()


def test_an_unresolved_call_nobody_followed_up_is_not_a_repeat() -> None:
    traffic = (call("C-0001", caller_ref="CB-1", outcome=Outcome.UNRESOLVED, on=day(0)),)

    assert failure_driven_repeats(traffic) == ()


def test_the_repeat_need_not_be_about_the_same_thing() -> None:
    """ "Same category" is not a workbook condition and was deliberately
    dropped. A member who calls about a denial and then an ID card called
    twice.
    """
    traffic = (
        call(
            "C-0001",
            caller_ref="CB-1",
            outcome=Outcome.UNRESOLVED,
            category=Category.CLAIMS_AND_EOB,
            on=day(0),
        ),
        call(
            "C-0002",
            caller_ref="CB-1",
            category=Category.ENROLLMENT_AND_ID_CARDS,
            on=day(3),
        ),
    )

    assert _refs(failure_driven_repeats(traffic)) == {"C-0001"}


def test_each_unresolved_call_from_one_caller_is_judged_on_its_own() -> None:
    traffic = (
        call("C-0001", caller_ref="CB-1", outcome=Outcome.UNRESOLVED, on=day(0)),
        call("C-0002", caller_ref="CB-1", outcome=Outcome.UNRESOLVED, on=day(3)),
        call("C-0003", caller_ref="CB-1", on=day(5)),
    )

    assert _refs(failure_driven_repeats(traffic)) == {"C-0001", "C-0002"}


def test_a_call_with_no_caller_reference_links_to_nothing() -> None:
    """An unresolved caller is a known gap the Phase 5 diagnostics count,
    not something to guess at here.
    """
    traffic = (
        call("C-0001", caller_ref=None, outcome=Outcome.UNRESOLVED, on=day(0)),
        call("C-0002", caller_ref=None, on=day(2)),
    )

    assert repeats(traffic) == ()


def test_the_last_fourteen_days_of_the_window_have_no_exposure() -> None:
    """A call from yesterday has not had its fourteen days, and counting it
    as a non-repeat asserts something nobody knows yet.
    """
    early = call("C-0001", outcome=Outcome.UNRESOLVED, on=day(0))
    late = call("C-0002", outcome=Outcome.UNRESOLVED, on=WINDOW.end)

    assert _refs(exposed_unresolved((early, late), WINDOW)) == {"C-0001"}
