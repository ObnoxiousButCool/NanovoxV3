"""Rolling comparisons up, and the number that stops the roll-up lying.

Every test here is about the relationship between agreement and coverage.
An agreement rate on its own is the most quotable number this phase
produces and the easiest to mislead with, so the module refuses to render
one without its denominator.
"""

from __future__ import annotations

import pytest

from domain.evaluation.agreement import Agreement, LayerAgreement, agreement_for
from domain.evaluation.comparison import Comparison, compare_exact, compare_set
from domain.value_objects.outcome import Outcome


def _agreed(n: int) -> list[Comparison]:
    return [compare_exact("outcome", Outcome.RESOLVED, Outcome.RESOLVED) for _ in range(n)]


def _disagreed(n: int) -> list[Comparison]:
    return [compare_exact("outcome", Outcome.RESOLVED, Outcome.UNRESOLVED) for _ in range(n)]


def _silent(n: int) -> list[Comparison]:
    """Calls where the pipeline produced no value at all."""
    return [compare_exact("outcome", Outcome.RESOLVED, None) for _ in range(n)]


def _unrecorded(n: int) -> list[Comparison]:
    """Calls the tracker does not record this field for."""
    return [compare_exact("outcome", None, Outcome.RESOLVED) for _ in range(n)]


def test_agreement_is_agreed_over_comparable() -> None:
    result = agreement_for("outcome", [*_agreed(8), *_disagreed(2)])

    assert result.rate == pytest.approx(0.8)
    assert result.comparable == 10
    assert result.coverage == pytest.approx(1.0)


def test_a_silent_pipeline_does_not_score_a_hundred_percent() -> None:
    """The failure this whole module is shaped around. Ninety-eight calls
    the pipeline never answered and two it got right is not a 100% field.
    """
    result = agreement_for("outcome", [*_agreed(2), *_silent(98)])

    assert result.rate == pytest.approx(1.0), "the two it answered, it got right"
    assert result.coverage == pytest.approx(0.02), "on two calls out of a hundred"
    assert result.no_pipeline_value == 98
    assert "2 of 100" in result.summary
    assert "98 with no pipeline value" in result.summary


def test_a_pipeline_that_answered_nothing_has_no_rate_at_all() -> None:
    """`None`, not 0.0 — for the same reason a withheld figure is not zero.
    No comparison having been possible is not every comparison having failed.
    """
    result = agreement_for("outcome", _silent(100))

    assert result.rate is None
    assert result.coverage == pytest.approx(0.0)
    assert "no comparison possible" in result.summary


def test_calls_the_tracker_never_recorded_do_not_count_against_the_pipeline() -> None:
    """A limit of the answer key. Counting these as disagreements would
    understate the pipeline on most fields, since the tracker records what
    happened rather than filling in every column.
    """
    result = agreement_for("touchpoint", [*_agreed(10), *_unrecorded(90)])

    assert result.rate == pytest.approx(1.0)
    assert result.no_answer_key == 90
    assert result.disagreed == 0


def test_the_summary_always_carries_both_numbers() -> None:
    """100% on four calls and 100% on ninety-eight are the same number and
    different findings. Whichever a reader assumes is the one that misleads.
    """
    thin = agreement_for("outcome", [*_agreed(4), *_silent(96)])
    solid = agreement_for("outcome", _agreed(98))

    assert "100%" in thin.summary and "4 of 100" in thin.summary
    assert "100%" in solid.summary and "98 of 98" in solid.summary


def test_every_call_lands_in_exactly_one_bucket() -> None:
    result = agreement_for("outcome", [*_agreed(3), *_disagreed(2), *_silent(4), *_unrecorded(1)])

    assert result.calls == 10
    assert (result.agreed, result.disagreed) == (3, 2)
    assert (result.no_pipeline_value, result.no_answer_key) == (4, 1)


def test_a_set_field_rolls_up_on_exact_equality() -> None:
    """Strict on purpose: "the pipeline got this call's signals exactly
    right" is the claim a screen ends up making.
    """
    comparisons = [
        compare_set("signals", expected={"billing_defect"}, actual={"billing_defect"}),
        compare_set("signals", expected={"billing_defect"}, actual={"billing_defect", "extra"}),
    ]

    result = agreement_for("signals", comparisons)

    assert (result.agreed, result.disagreed) == (1, 1)


# --- Per layer -------------------------------------------------------------


def _field(name: str, agreed: int, disagreed: int) -> Agreement:
    return Agreement(
        field=name,
        agreed=agreed,
        disagreed=disagreed,
        no_answer_key=0,
        no_pipeline_value=0,
        neither=0,
    )


def test_a_layer_rolls_its_fields_up() -> None:
    """The layer is what a reader acts on: "L2 is weak" is a prompt to
    rewrite, where "touchpoint is weak" is only a column to distrust.
    """
    layer = LayerAgreement(
        layer="L2", fields=(_field("outcome", 90, 10), _field("category", 70, 30))
    )

    assert layer.rate == pytest.approx(0.8)
    assert layer.comparable == 200


def test_the_weakest_field_is_the_one_to_fix() -> None:
    layer = LayerAgreement(
        layer="L2", fields=(_field("outcome", 90, 10), _field("category", 70, 30))
    )

    weakest = layer.weakest

    assert weakest is not None
    assert weakest.field == "category"


def test_a_field_with_nothing_comparable_is_not_the_weakest() -> None:
    """It is an unanswered question, not a poor performer, and naming it as
    the thing to fix sends someone to the wrong place.
    """
    unanswered = Agreement(
        field="process_gap",
        agreed=0,
        disagreed=0,
        no_answer_key=0,
        no_pipeline_value=100,
        neither=0,
    )
    layer = LayerAgreement(layer="L4", fields=(_field("signals", 60, 40), unanswered))

    weakest = layer.weakest

    assert weakest is not None
    assert weakest.field == "signals"


def test_a_layer_with_nothing_comparable_names_no_weakest_field() -> None:
    silent = Agreement(
        field="signals", agreed=0, disagreed=0, no_answer_key=0, no_pipeline_value=5, neither=0
    )
    layer = LayerAgreement(layer="L4", fields=(silent,))

    assert layer.rate is None
    assert layer.weakest is None
