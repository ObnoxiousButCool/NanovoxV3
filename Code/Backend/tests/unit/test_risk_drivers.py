"""Which indicators drive the risk, across the book.

The assertions that matter are the three kinds of "no number": a family v9
cannot compute, a family nobody raised, and a window too short to say
whether anything moved. Collapsing any two of those is the failure.
"""

from __future__ import annotations

from datetime import date

from domain.aggregation.call_tags import CallContext, CallTags, Window
from domain.aggregation.risk_drivers import Driver, risk_drivers
from domain.value_objects.category import Category
from domain.value_objects.escalation import Escalation
from domain.value_objects.outcome import Outcome

#: Twelve weeks, so the first and last thirds are four weeks each.
QUARTER = Window(date(2026, 7, 1), date(2026, 9, 23))
#: Three weeks: a count is fair, a comparison is not.
SHORT = Window(date(2026, 9, 1), date(2026, 9, 21))


def _call(
    reference: str,
    *,
    on: date,
    outcome: Outcome | None = Outcome.RESOLVED,
    category: Category | None = Category.CLAIMS_AND_EOB,
    touchpoint: str | None = None,
    escalation: Escalation | None = None,
    employer: str = "EMP-1001",
) -> CallContext:
    return CallContext(
        tags=CallTags(
            reference=reference,
            outcome=outcome,
            category=category,
            touchpoint=touchpoint,
            escalation=escalation,
        ),
        occurred_on=on,
        employer_ref=employer,
    )


def _driver(calls: list[CallContext], code: str, window: Window = QUARTER) -> Driver:
    return next(d for d in risk_drivers(calls, window) if d.family.code == code)


class TestCounting:
    def test_a_family_counts_the_calls_that_raised_it(self) -> None:
        calls = [
            _call("C-1", on=date(2026, 8, 1), outcome=Outcome.UNRESOLVED),
            _call("C-2", on=date(2026, 8, 2), outcome=Outcome.UNRESOLVED),
            _call("C-3", on=date(2026, 8, 3), outcome=Outcome.RESOLVED),
        ]

        assert _driver(calls, "unresolved").calls == 2

    def test_calls_outside_the_window_do_not_count(self) -> None:
        calls = [
            _call("C-1", on=date(2026, 8, 1), outcome=Outcome.UNRESOLVED),
            _call("C-2", on=date(2026, 5, 1), outcome=Outcome.UNRESOLVED),
        ]

        assert _driver(calls, "unresolved").calls == 1

    def test_the_ranking_puts_the_biggest_driver_first(self) -> None:
        calls = [
            _call("C-1", on=date(2026, 8, 1), outcome=Outcome.UNRESOLVED),
            _call("C-2", on=date(2026, 8, 2), outcome=Outcome.UNRESOLVED),
            _call(
                "C-3",
                on=date(2026, 8, 3),
                escalation=Escalation(triggered=True, handled=False),
            ),
        ]

        drivers = risk_drivers(calls, QUARTER)

        assert drivers[0].family.code == "unresolved"

    def test_a_family_nobody_raised_is_kept_at_zero(self) -> None:
        """These ten are the flag's own inputs, so "nobody raised this" is a
        finding about the book rather than a long tail to trim."""
        calls = [_call("C-1", on=date(2026, 8, 1))]

        assert _driver(calls, "exit_language").calls == 0


class TestTheThreeKindsOfNothing:
    def test_an_uncomputable_family_is_reported_with_its_reason(self) -> None:
        driver = _driver([_call("C-1", on=date(2026, 8, 1))], "high_effort")

        assert driver.calls == 0
        assert driver.family.computable is False
        assert driver.family.unavailable_because
        assert driver.change is None

    def test_an_uncomputable_family_sorts_after_the_zeros(self) -> None:
        """It is a different statement from "nobody raised it", so it does
        not sit among the families that were looked for and not found."""
        drivers = risk_drivers([_call("C-1", on=date(2026, 8, 1))], QUARTER)

        assert drivers[-1].family.code == "high_effort"

    def test_a_short_window_counts_but_does_not_compare(self) -> None:
        calls = [_call("C-1", on=date(2026, 9, 10), outcome=Outcome.UNRESOLVED)]

        driver = _driver(calls, "unresolved", window=SHORT)

        assert driver.calls == 1
        assert driver.change is None


class TestTheChange:
    def test_a_move_carries_the_noise_test_rather_than_a_percentage(self) -> None:
        """Two calls becoming four is +100% and also a coin flip, so the
        screen is given `beyond_noise` to decide with."""
        calls = [
            _call("C-1", on=date(2026, 7, 3), outcome=Outcome.UNRESOLVED),
            _call("C-2", on=date(2026, 9, 18), outcome=Outcome.UNRESOLVED),
            _call("C-3", on=date(2026, 9, 19), outcome=Outcome.UNRESOLVED),
        ]

        change = _driver(calls, "unresolved").change

        assert change is not None
        assert change.prior == 1
        assert change.now == 2
        assert change.beyond_noise is False

    def test_repeat_contact_is_compared_like_every_other_family(self) -> None:
        """It has no per-call predicate, so it would otherwise be the one
        family with a count and no change."""
        calls = [_call("C-1", on=date(2026, 8, 1))]

        assert _driver(calls, "repeat_contact").change is not None


class TestContext:
    def test_a_driver_names_what_its_calls_were_about(self) -> None:
        calls = [
            _call(
                "C-1",
                on=date(2026, 8, 1),
                outcome=Outcome.UNRESOLVED,
                category=Category.BILLING_AND_PREMIUM,
                touchpoint="invoice_statement",
            ),
            _call(
                "C-2",
                on=date(2026, 8, 2),
                outcome=Outcome.UNRESOLVED,
                category=Category.BILLING_AND_PREMIUM,
                touchpoint="invoice_statement",
            ),
            _call(
                "C-3",
                on=date(2026, 8, 3),
                outcome=Outcome.UNRESOLVED,
                category=Category.CLAIMS_AND_EOB,
            ),
        ]

        driver = _driver(calls, "unresolved")

        assert driver.top_category is Category.BILLING_AND_PREMIUM
        assert driver.top_touchpoint == "invoice_statement"

    def test_context_is_absent_rather_than_guessed(self) -> None:
        calls = [_call("C-1", on=date(2026, 8, 1), outcome=Outcome.UNRESOLVED, category=None)]

        driver = _driver(calls, "unresolved")

        assert driver.top_category is None
        assert driver.top_touchpoint is None
