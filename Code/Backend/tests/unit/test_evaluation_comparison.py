"""The four comparison kinds, and the three verdicts.

The tests worth reading are the ones about *not comparable*. Folding that
verdict into either of the others produces a confident, wrong number — and
one of the two directions makes a pipeline that produced nothing look
perfect.
"""

from __future__ import annotations

import pytest

from domain.evaluation.comparison import (
    Comparison,
    MissingSide,
    Verdict,
    compare_exact,
    compare_presence_and_detail,
    compare_set,
)
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.outcome import Outcome

# --- Exact match -----------------------------------------------------------


def test_two_matching_values_agree() -> None:
    result = compare_exact("outcome", Outcome.RESOLVED, Outcome.RESOLVED)

    assert result.verdict is Verdict.AGREED
    assert result.comparable is True


def test_two_different_values_disagree_and_both_are_reported() -> None:
    """A disagreement a reader cannot see both sides of is not actionable."""
    result = compare_exact("outcome", Outcome.RESOLVED, Outcome.UNRESOLVED)

    assert result.verdict is Verdict.DISAGREED
    assert (result.expected, result.actual) == ("RESOLVED", "UNRESOLVED")


def test_an_enum_and_its_own_string_value_agree() -> None:
    """The answer key parses some fields into enums and keeps others as the
    workbook's strings. A comparison that failed on representation would
    report a disagreement about nothing.
    """
    assert compare_exact("outcome", Outcome.RESOLVED, "RESOLVED").verdict is Verdict.AGREED


def test_a_field_the_tracker_never_recorded_is_not_comparable() -> None:
    """Not a failure of the pipeline. The tracker records what happened
    rather than filling in every column, so this is most fields on most
    calls, and counting them as disagreements understates the pipeline.
    """
    result = compare_exact("touchpoint", None, "welcome_pack")

    assert result.verdict is Verdict.NOT_COMPARABLE
    assert result.missing is MissingSide.ANSWER_KEY


def test_a_field_the_pipeline_did_not_answer_is_not_comparable_but_is_named() -> None:
    """The one that matters most. Counting this as agreement would let a
    pipeline that produced nothing at all score 100%, so it is tracked
    separately and surfaces in the roll-up.
    """
    result = compare_exact("touchpoint", "welcome_pack", None)

    assert result.verdict is Verdict.NOT_COMPARABLE
    assert result.missing is MissingSide.PIPELINE


def test_neither_side_having_a_value_is_recorded_as_such() -> None:
    result = compare_exact("touchpoint", None, None)

    assert result.missing is MissingSide.BOTH


def test_an_incomparable_result_must_say_which_side_was_missing() -> None:
    """ "The tracker never said" and "the pipeline did not answer" are
    different findings with different owners, and a verdict that does not
    distinguish them is not usable.
    """
    with pytest.raises(ValueError, match="which side was missing"):
        Comparison(field="outcome", verdict=Verdict.NOT_COMPARABLE)


def test_a_comparable_result_cannot_claim_a_missing_side() -> None:
    with pytest.raises(ValueError, match="cannot also record a missing side"):
        Comparison(field="outcome", verdict=Verdict.AGREED, missing=MissingSide.PIPELINE)


# --- Set overlap -----------------------------------------------------------


def test_precision_and_recall_are_reported_apart_never_blended() -> None:
    """A pipeline that finds half the signals and invents none is a
    different problem from one that finds them all and invents four. One
    score hides which, and they are fixed differently.
    """
    result = compare_set(
        "signals",
        expected={"billing_defect", "process_breakdown", "knowledge_error"},
        actual={"billing_defect", "retention_risk"},
    )

    assert result.matched == frozenset({"billing_defect"})
    assert result.missed == frozenset({"process_breakdown", "knowledge_error"})
    assert result.spurious == frozenset({"retention_risk"})
    assert result.precision == pytest.approx(0.5)
    assert result.recall == pytest.approx(1 / 3)


def test_two_identical_sets_agree() -> None:
    result = compare_set("signals", expected={"billing_defect"}, actual={"billing_defect"})

    assert result.verdict is Verdict.AGREED
    assert result.precision == pytest.approx(1.0)


def test_both_sides_finding_nothing_is_agreement_not_absence() -> None:
    """ "This call raised no signals" is a real answer both sides can get
    right, and most calls are this case.
    """
    result = compare_set("signals", expected=set(), actual=set())

    assert result.verdict is Verdict.AGREED


def test_precision_is_undefined_rather_than_zero_when_nothing_was_claimed() -> None:
    """Scoring an empty extraction 0% precision punishes the pipeline for a
    call that genuinely had no signals.
    """
    result = compare_set("signals", expected=set(), actual=set())

    assert result.precision is None
    assert result.recall is None


def test_a_side_with_nothing_to_say_is_not_the_same_as_an_empty_set() -> None:
    """`None` means the layer did not run; an empty set means it ran and
    found nothing. Treating the first as the second credits a failed layer
    with a correct answer on every call that had no signals.
    """
    result = compare_set("signals", expected={"billing_defect"}, actual=None)

    assert result.verdict is Verdict.NOT_COMPARABLE
    assert result.missing is MissingSide.PIPELINE


# --- Presence and detail ---------------------------------------------------


def test_a_knowledge_failure_on_the_wrong_rule_fails_only_the_detail() -> None:
    """Metric 8's output is a ranked list of articles to rewrite. Getting
    the presence right and the rule wrong is a real failure with a real
    consequence, and it has to be visible apart from getting the presence
    wrong.
    """
    presence, detail = compare_presence_and_detail(
        "knowledge_failure",
        expected_present=True,
        actual_present=True,
        expected_detail="C-12",
        actual_detail="P-14",
    )

    assert presence.verdict is Verdict.AGREED
    assert detail.verdict is Verdict.DISAGREED
    assert (detail.expected, detail.actual) == ("C-12", "P-14")


def test_the_detail_is_not_compared_where_the_sides_disagree_that_it_happened() -> None:
    """Asking which rule was wrong on a call the pipeline found no knowledge
    failure on is asking about a value that should not exist.
    """
    presence, detail = compare_presence_and_detail(
        "knowledge_failure",
        expected_present=True,
        actual_present=False,
        expected_detail="C-12",
        actual_detail=None,
    )

    assert presence.verdict is Verdict.DISAGREED
    assert detail.verdict is Verdict.NOT_COMPARABLE


def test_both_sides_agreeing_nothing_happened_is_agreement() -> None:
    presence, detail = compare_presence_and_detail(
        "complaint",
        expected_present=False,
        actual_present=False,
        expected_detail=None,
        actual_detail=None,
    )

    assert presence.verdict is Verdict.AGREED
    assert detail.verdict is Verdict.NOT_COMPARABLE


def test_complaint_attribution_compares_the_target() -> None:
    """The Metrics sheet's own word for this dimension is "attribution
    target", not "party" — "party" is §7A's v10 fault-record vocabulary and
    does not exist in v9.
    """
    presence, detail = compare_presence_and_detail(
        "complaint",
        expected_present=True,
        actual_present=True,
        expected_detail=ComplaintAttribution.CHOICE,
        actual_detail=ComplaintAttribution.BROKER,
    )

    assert presence.verdict is Verdict.AGREED
    assert (detail.expected, detail.actual) == ("CHOICE", "BROKER")


def test_presence_and_detail_are_two_comparisons_never_one() -> None:
    """Collapsing them loses which half failed, and the two have different
    causes: presence is a classification problem, the detail is a citation
    or lookup problem.
    """
    results = compare_presence_and_detail(
        "knowledge_failure",
        expected_present=True,
        actual_present=True,
        expected_detail="C-12",
        actual_detail="C-12",
    )

    assert len(results) == 2
    assert [r.field for r in results] == ["knowledge_failure.present", "knowledge_failure.detail"]
