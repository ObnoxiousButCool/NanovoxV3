"""`worst_category`, tested for the same failure `trends.movement` guards.

A "worst" category with nothing wrong in it is a manufactured finding, and a
tie-break that ignores whether escalations were handled would let a clean
category crowd out one where a caller who asked for a supervisor did not get
one.
"""

from __future__ import annotations

from datetime import date

from domain.aggregation.call_tags import CallContext, CallTags
from domain.aggregation.concern import worst_category
from domain.value_objects.category import Category
from domain.value_objects.escalation import Escalation
from domain.value_objects.outcome import Outcome


def call(
    reference: str,
    category: Category,
    *,
    outcome: Outcome = Outcome.RESOLVED,
    escalation: Escalation | None = None,
) -> CallContext:
    return CallContext(
        tags=CallTags(
            reference=reference,
            outcome=outcome,
            category=category,
            escalation=escalation,
        ),
        occurred_on=date(2026, 9, 1),
        employer_ref="EMP-01",
        broker_of_record_ref="BRK-01",
        agent_ref="AG-01",
    )


def test_no_unresolved_call_anywhere_names_no_concern() -> None:
    """A clean book has no area of concern to invent."""
    calls = [call("C-1", Category.CLAIMS_AND_EOB, outcome=Outcome.RESOLVED)]

    assert worst_category(calls) is None


def test_the_category_with_the_most_unresolved_calls_wins() -> None:
    calls = [
        call("C-1", Category.CLAIMS_AND_EOB, outcome=Outcome.UNRESOLVED),
        call("C-2", Category.COVERAGE_AND_BENEFITS, outcome=Outcome.UNRESOLVED),
        call("C-3", Category.COVERAGE_AND_BENEFITS, outcome=Outcome.UNRESOLVED),
    ]

    result = worst_category(calls)

    assert result is not None
    assert result.category == "Coverage & Benefits"
    assert result.unresolved == 2
    assert result.calls == 2


def test_a_tied_unresolved_count_breaks_on_the_unhandled_escalation_gap() -> None:
    """The more serious fact — a supervisor asked for and not given — wins a tie."""
    clean = Escalation(triggered=True, handled=True)
    missed = Escalation(triggered=True, handled=False)
    calls = [
        call("C-1", Category.CLAIMS_AND_EOB, outcome=Outcome.UNRESOLVED, escalation=clean),
        call("C-2", Category.COVERAGE_AND_BENEFITS, outcome=Outcome.UNRESOLVED, escalation=missed),
    ]

    result = worst_category(calls)

    assert result is not None
    assert result.category == "Coverage & Benefits"
    assert result.escalations_triggered == 1
    assert result.escalations_handled == 0


def test_a_call_with_no_category_is_left_out_rather_than_bucketed_under_none() -> None:
    calls = [
        call("C-1", Category.CLAIMS_AND_EOB, outcome=Outcome.UNRESOLVED),
        CallContext(
            tags=CallTags(reference="C-2", outcome=Outcome.UNRESOLVED, category=None),
            occurred_on=date(2026, 9, 1),
            employer_ref="EMP-01",
            broker_of_record_ref="BRK-01",
            agent_ref="AG-01",
        ),
    ]

    result = worst_category(calls)

    assert result is not None
    assert result.category == "Claims & EOB"
    assert result.unresolved == 1
