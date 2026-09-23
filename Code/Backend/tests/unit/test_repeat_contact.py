"""Failure-driven repeat contact, exactly as metric 4 defines it — not as
the Transcript Tracker's own "Repeat of" column happens to read.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from domain.derivations.repeat_contact import (
    CallForRepeatContact,
    failure_driven_repeats,
    has_full_exposure_window,
)

_DAY_ZERO = datetime(2026, 7, 6, 9, 0, tzinfo=timezone.utc)


def _call(
    reference: str, caller_ref: str, *, days_after_zero: float, unresolved: bool
) -> CallForRepeatContact:
    return CallForRepeatContact(
        reference=reference,
        caller_ref=caller_ref,
        occurred_at=_DAY_ZERO + timedelta(days=days_after_zero),
        is_unresolved=unresolved,
    )


def test_an_unresolved_call_followed_by_a_same_caller_contact_within_14_days_is_flagged() -> None:
    first = _call("C-0001", "CB-1", days_after_zero=0, unresolved=True)
    second = _call("C-0002", "CB-1", days_after_zero=10, unresolved=False)

    assert failure_driven_repeats([first, second]) == frozenset({"C-0001"})


def test_a_contact_exactly_at_the_14_day_boundary_still_counts() -> None:
    first = _call("C-0001", "CB-1", days_after_zero=0, unresolved=True)
    second = _call("C-0002", "CB-1", days_after_zero=14, unresolved=False)

    assert "C-0001" in failure_driven_repeats([first, second])


def test_a_contact_just_past_14_days_does_not_count() -> None:
    first = _call("C-0001", "CB-1", days_after_zero=0, unresolved=True)
    second = _call("C-0002", "CB-1", days_after_zero=14.01, unresolved=False)

    assert failure_driven_repeats([first, second]) == frozenset()


def test_a_resolved_call_is_never_flagged_even_with_a_later_contact() -> None:
    first = _call("C-0001", "CB-1", days_after_zero=0, unresolved=False)
    second = _call("C-0002", "CB-1", days_after_zero=5, unresolved=False)

    assert failure_driven_repeats([first, second]) == frozenset()


def test_a_different_callers_later_contact_does_not_count() -> None:
    first = _call("C-0001", "CB-1", days_after_zero=0, unresolved=True)
    second = _call("C-0002", "CB-2", days_after_zero=5, unresolved=False)

    assert failure_driven_repeats([first, second]) == frozenset()


def test_an_earlier_contact_from_the_same_caller_does_not_count() -> None:
    # The window looks forward only — a call before the UNRESOLVED one is
    # not a repeat of it.
    earlier = _call("C-0001", "CB-1", days_after_zero=0, unresolved=False)
    unresolved = _call("C-0002", "CB-1", days_after_zero=5, unresolved=True)

    assert failure_driven_repeats([earlier, unresolved]) == frozenset()


def test_an_unresolved_call_with_no_follow_up_is_not_flagged() -> None:
    lone = _call("C-0001", "CB-1", days_after_zero=0, unresolved=True)

    assert failure_driven_repeats([lone]) == frozenset()


def test_same_category_is_not_required() -> None:
    # This project's own earlier addition, deliberately dropped — the
    # function takes no category argument at all, so there is nothing to
    # assert beyond "a plain caller-and-window match is sufficient",
    # already covered above.
    first = _call("C-0001", "CB-1", days_after_zero=0, unresolved=True)
    second = _call("C-0002", "CB-1", days_after_zero=1, unresolved=False)

    assert failure_driven_repeats([first, second]) == frozenset({"C-0001"})


def test_multiple_unresolved_calls_from_one_caller_are_each_evaluated() -> None:
    first = _call("C-0001", "CB-1", days_after_zero=0, unresolved=True)
    second = _call("C-0002", "CB-1", days_after_zero=20, unresolved=True)
    third = _call("C-0003", "CB-1", days_after_zero=25, unresolved=False)

    # C-0001 has no contact within its own 14-day window (next contact is
    # 20 days out); C-0002 does (5 days later).
    assert failure_driven_repeats([first, second, third]) == frozenset({"C-0002"})


class TestExposureWindow:
    def test_a_call_with_a_full_14_days_before_window_end_has_exposure(self) -> None:
        window_end = _DAY_ZERO + timedelta(days=14)

        assert has_full_exposure_window(_DAY_ZERO, window_end)

    def test_a_call_inside_the_last_14_days_has_no_exposure_yet(self) -> None:
        window_end = _DAY_ZERO + timedelta(days=10)

        assert not has_full_exposure_window(_DAY_ZERO, window_end)
