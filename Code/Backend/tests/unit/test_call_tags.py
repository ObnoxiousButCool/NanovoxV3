"""The schema value objects and the aggregation layer's input contract.

The invariants here are the schema sheet's own notes turned into code. Each
one is a rule the sheet states in prose and that nothing would otherwise
enforce — a knowledge failure with no rule id, an escalation that was
handled without ever triggering, a process gap with no lifecycle.
"""

from __future__ import annotations

from datetime import date

import pytest

from domain.aggregation.call_tags import (
    BrokerFacts,
    CallContext,
    CallTags,
    EmployerFacts,
    Window,
    book_lives_for,
)
from domain.value_objects.escalation import Escalation
from domain.value_objects.knowledge_failure import KnowledgeFailure
from domain.value_objects.process_gap import ProcessGap, ProcessGapStatus, RaisedBy
from domain.value_objects.product_line import ProductLine
from domain.value_objects.signal_code import (
    SEVERITY_ORDER,
    Severity,
    SignalCode,
    owner_team_of,
    severity_of,
)


def _employer(reference: str, *, enrolled: int, broker_ref: str = "BRK-01") -> EmployerFacts:
    return EmployerFacts(
        reference=reference,
        name=f"Employer {reference}",
        enrolled=enrolled,
        region="North",
        industry="Manufacturing",
        renewal_month="January",
        broker_ref=broker_ref,
    )


# --- Escalation (schema field 6) -------------------------------------------


def test_an_escalation_that_never_triggered_cannot_be_handled() -> None:
    """The denominator has to travel with the numerator, or somebody
    eventually divides by the wrong thing.
    """
    with pytest.raises(ValueError, match="cannot carry a trigger type or be handled"):
        Escalation(triggered=False, handled=True)


def test_a_triggered_and_unhandled_escalation_is_missed() -> None:
    """The refusal view is the inverse of integrity over the same
    denominator, not a separate measure — so it is derived, never tagged.
    """
    assert Escalation(triggered=True, handled=False).missed is True
    assert Escalation(triggered=True, handled=True).missed is False


def test_a_call_with_no_escalation_at_all_is_not_missed() -> None:
    assert Escalation(triggered=False).missed is False


# --- Knowledge failure (schema field 8) ------------------------------------


def test_a_knowledge_failure_must_cite_a_rule() -> None:
    """ "Naming the rule points at one article; naming the agent fixes
    nothing." Metric 8's output is a ranked list of articles to rewrite, and
    a failure with no rule id cannot appear on it.
    """
    with pytest.raises(ValueError, match="must cite a rule id"):
        KnowledgeFailure(present=True)


def test_an_absent_knowledge_failure_carries_nothing_else() -> None:
    with pytest.raises(ValueError, match="must not carry a rule id"):
        KnowledgeFailure(present=False, rule_id="C-12")


def test_a_present_knowledge_failure_holds_its_rule_and_correction() -> None:
    failure = KnowledgeFailure(
        present=True,
        rule_id="C-12",
        correct_statement="major-service waiting periods do not apply",
    )

    assert failure.rule_id == "C-12"


# --- Process gap (schema field 15) -----------------------------------------


def test_a_process_gap_must_carry_a_lifecycle() -> None:
    """ "A tag without a lifecycle is a note nobody reads." The status is the
    field that turns seven calls proposing the same change into a backlog
    item rather than seven notes.
    """
    with pytest.raises(ValueError, match="a tag without a lifecycle is a note"):
        ProcessGap(present=True, proposed_change="name the waiting period in the denial letter")


def test_an_absent_process_gap_carries_nothing_else() -> None:
    with pytest.raises(ValueError, match="must not carry any of its other fields"):
        ProcessGap(present=False, touchpoint="denial_letter_eob")


def test_a_present_process_gap_routes_by_touchpoint() -> None:
    gap = ProcessGap(
        present=True,
        gap_type="missing_detail",
        touchpoint="denial_letter_eob",
        proposed_change="name the waiting period and its end date",
        raised_by=RaisedBy.CALLER,
        status=ProcessGapStatus.UNVALIDATED,
    )

    assert gap.touchpoint == "denial_letter_eob"
    assert gap.status is ProcessGapStatus.UNVALIDATED


# --- Signal taxonomy (schema field 5) --------------------------------------


def test_every_signal_has_a_severity_and_an_owner() -> None:
    """Both are mandatory per the sheet: severity drives ranking, owner
    drives routing. A signal missing either is a signal that cannot be shown
    or cannot be sent to anyone.
    """
    for signal in SignalCode:
        assert severity_of(signal) in SEVERITY_ORDER
        assert owner_team_of(signal).strip()


def test_severity_order_runs_worst_first() -> None:
    assert SEVERITY_ORDER[0] is Severity.CRITICAL
    assert SEVERITY_ORDER[-1] is Severity.LOW


def test_knowledge_error_is_owned_by_knowledge_management_not_the_call_centre() -> None:
    """D7: this is the agent-conduct event, and it routes to the people who
    own the article — not to Operations, and not to the agent.
    """
    assert owner_team_of(SignalCode.KNOWLEDGE_ERROR) == "Knowledge Management"


# --- CallTags --------------------------------------------------------------


def test_a_multi_line_call_counts_under_one_primary_line() -> None:
    """Shares over `product_lines` exceed 100% by design. Counting a
    two-line call once per line inflates every per-line contact rate, so the
    choice of primary is made in one place.
    """
    tags = CallTags(reference="C-0001", product_lines=(ProductLine.DENTAL, ProductLine.VISION))

    assert tags.primary_product_line is ProductLine.DENTAL


def test_a_call_with_no_product_line_has_no_primary() -> None:
    assert CallTags(reference="C-0001").primary_product_line is None


def test_signals_are_distinct_types_not_occurrences() -> None:
    """ "Five instances of one problem is one problem, whereas three different
    problems on one call is an account coming apart." A frozenset is what
    makes the second impossible to miscount as the first.
    """
    tags = CallTags(
        reference="C-0001",
        signals=frozenset({SignalCode.BILLING_DEFECT, SignalCode.BILLING_DEFECT}),
    )

    assert len(tags.signals) == 1


def test_a_call_context_exposes_its_reference() -> None:
    call = CallContext(tags=CallTags(reference="C-0001"), occurred_on=date(2026, 7, 6))

    assert call.reference == "C-0001"


# --- Broker book size ------------------------------------------------------


def test_book_lives_sums_the_brokers_whole_book_not_the_callers() -> None:
    """The floor exists to stop a three-group agency being ranked on noise.
    Summing only employers that happened to call would make the denominator
    move with call volume, which defeats it entirely.
    """
    employers = (
        _employer("EMP-01", enrolled=100, broker_ref="BRK-01"),
        _employer("EMP-02", enrolled=60, broker_ref="BRK-01"),
        _employer("EMP-03", enrolled=500, broker_ref="BRK-02"),
    )

    assert book_lives_for("BRK-01", employers) == 160
    assert book_lives_for("BRK-99", employers) == 0


def test_groups_in_book_and_book_lives_are_different_denominators() -> None:
    """Metric 2's broker complaint rate divides by groups; insight 10's
    ranking floor is 150 lives. Carrying one and deriving the other from it
    would be inventing a group size nobody published.
    """
    broker = BrokerFacts(
        reference="BRK-01",
        name="A Broker",
        agency="An Agency",
        region="North",
        groups_in_book=3,
        book_lives=160,
    )

    assert (broker.groups_in_book, broker.book_lives) == (3, 160)


# --- Window ----------------------------------------------------------------


def test_a_window_cannot_end_before_it_starts() -> None:
    with pytest.raises(ValueError, match="cannot end before it starts"):
        Window(start=date(2026, 9, 25), end=date(2026, 7, 6))


def test_a_window_is_inclusive_at_both_ends() -> None:
    window = Window(start=date(2026, 7, 6), end=date(2026, 9, 25))

    assert window.contains(date(2026, 7, 6)) is True
    assert window.contains(date(2026, 9, 25)) is True
    assert window.contains(date(2026, 7, 5)) is False
    assert window.contains(date(2026, 9, 26)) is False


def test_window_length_in_weeks_is_what_annualises_a_rate() -> None:
    """Contact rate is calls x (52 / weeks). A window measured wrongly
    scales every annualised figure by the same wrong factor, which is
    invisible because the shape of the chart does not change.
    """
    window = Window(start=date(2026, 7, 6), end=date(2026, 9, 28))

    assert window.weeks == pytest.approx(12.0)


def test_a_same_day_window_is_one_day_not_zero() -> None:
    """Otherwise annualising divides by zero on the narrowest filter a user
    can pick.
    """
    day = date(2026, 7, 6)

    assert Window(start=day, end=day).weeks == pytest.approx(1 / 7)


def test_calls_outside_the_window_are_excluded() -> None:
    window = Window(start=date(2026, 7, 6), end=date(2026, 9, 25))
    calls = (
        CallContext(tags=CallTags(reference="C-0001"), occurred_on=date(2026, 7, 6)),
        CallContext(tags=CallTags(reference="C-0002"), occurred_on=date(2026, 6, 30)),
        CallContext(tags=CallTags(reference="C-0003"), occurred_on=date(2026, 9, 25)),
    )

    assert [call.reference for call in window.calls_in(calls)] == ["C-0001", "C-0003"]
