"""The Phase 5 harness: what it reports, and what it refuses to decide.

Two things are being protected here. The first is that a pipeline which has
not run must not read as one that agrees — coverage carries that. The second
is that the harness has no opinion about whether a number is good, because
plan §8 gives that decision to Minnie with the numbers in hand.
"""

from __future__ import annotations

import pytest

from application.ports.call_extraction_repository import (
    CallExtractionRepository,
    L2Save,
    L3Save,
    L4Save,
)
from application.ports.ground_truth_repository import GroundTruthCounts, GroundTruthRepository
from application.use_cases.evaluate_extraction import EvaluateExtraction
from domain.entities.call_extraction import CallExtraction
from domain.entities.ground_truth import GroundTruth
from domain.value_objects.category import Category
from domain.value_objects.outcome import Outcome


class _Answers(GroundTruthRepository):
    def __init__(self, rows: tuple[GroundTruth, ...]) -> None:
        self._rows = rows

    async def upsert(self, rows: tuple[GroundTruth, ...]) -> GroundTruthCounts:
        raise NotImplementedError

    async def all(self) -> tuple[GroundTruth, ...]:
        return self._rows


class _Extractions(CallExtractionRepository):
    def __init__(self, rows: dict[str, CallExtraction]) -> None:
        self._rows = rows

    async def get(self, call_reference: str) -> CallExtraction | None:
        return self._rows.get(call_reference)

    async def save_l2(self, call_reference: str, result: L2Save) -> None:
        raise NotImplementedError

    async def save_l3(self, call_reference: str, result: L3Save) -> None:
        raise NotImplementedError

    async def save_l4(self, call_reference: str, result: L4Save) -> None:
        raise NotImplementedError

    async def mark_l3_provisional(self, call_reference: str) -> None:
        raise NotImplementedError


def _answer(reference: str, *, outcome: Outcome = Outcome.RESOLVED) -> GroundTruth:
    return GroundTruth(reference=reference, outcome=outcome, category=Category.CLAIMS_AND_EOB)


def _extraction(reference: str, *, outcome: Outcome = Outcome.RESOLVED) -> CallExtraction:
    return CallExtraction(
        call_reference=reference, outcome=outcome, category=Category.CLAIMS_AND_EOB
    )


def _harness(
    answers: tuple[GroundTruth, ...], extractions: dict[str, CallExtraction]
) -> EvaluateExtraction:
    return EvaluateExtraction(_Answers(answers), _Extractions(extractions))


async def test_a_pipeline_that_agrees_scores_fully() -> None:
    answers = tuple(_answer(f"C-{i:04d}") for i in range(1, 11))
    extractions = {a.reference: _extraction(a.reference) for a in answers}

    report = await _harness(answers, extractions).execute()

    outcome = next(f for f in report.fields if f.field == "outcome")
    assert outcome.rate == pytest.approx(1.0)
    assert report.coverage == pytest.approx(1.0)
    assert report.comparable is True


async def test_a_disagreement_is_reported_and_not_resolved() -> None:
    """Same discipline as ImportAnswerKey: the harness says the two differ
    and stops. It does not prefer one, and it does not adjust either.
    """
    answers = (_answer("C-0001", outcome=Outcome.RESOLVED),)
    extractions = {"C-0001": _extraction("C-0001", outcome=Outcome.UNRESOLVED)}

    report = await _harness(answers, extractions).execute()

    outcome = next(f for f in report.fields if f.field == "outcome")
    assert (outcome.agreed, outcome.disagreed) == (0, 1)
    assert outcome.rate == pytest.approx(0.0)


async def test_a_pipeline_that_ran_on_four_calls_does_not_read_as_agreeing_on_everything() -> None:
    """The failure the whole report is shaped around. Four calls right out
    of a hundred is a 100% agreement rate at 4% coverage, and the second
    number is the one that matters.
    """
    answers = tuple(_answer(f"C-{i:04d}") for i in range(1, 101))
    extractions = {a.reference: _extraction(a.reference) for a in answers[:4]}

    report = await _harness(answers, extractions).execute()

    outcome = next(f for f in report.fields if f.field == "outcome")
    assert outcome.rate == pytest.approx(1.0)
    assert report.coverage == pytest.approx(0.04)
    assert len(report.unscored_calls) == 96


async def test_unscored_calls_are_named_not_merely_counted() -> None:
    """The first question anyone asks is which ones."""
    answers = (_answer("C-0001"), _answer("C-0002"))
    extractions = {"C-0001": _extraction("C-0001")}

    report = await _harness(answers, extractions).execute()

    assert report.unscored_calls == ("C-0002",)


async def test_a_pipeline_that_never_ran_is_incomparable_rather_than_wrong() -> None:
    """A distinct outcome, not a bad score. No amount of reading the
    agreement numbers would tell anyone the pipeline had not run.
    """
    answers = tuple(_answer(f"C-{i:04d}") for i in range(1, 11))

    report = await _harness(answers, {}).execute()

    assert report.comparable is False
    assert report.scored == 0
    assert all(field.rate is None for field in report.fields)


async def test_agreement_is_grouped_by_layer_in_the_order_the_layers_run() -> None:
    """A reader tracing a weak L4 wants to see whether L2 was sound first."""
    answers = (_answer("C-0001"),)
    extractions = {"C-0001": _extraction("C-0001")}

    report = await _harness(answers, extractions).execute()

    assert [layer.layer for layer in report.layers] == ["L1", "L2", "L3", "L4"]


async def test_the_weakest_layer_is_the_one_to_look_at_first() -> None:
    answers = (_answer("C-0001", outcome=Outcome.RESOLVED),)
    extractions = {"C-0001": _extraction("C-0001", outcome=Outcome.UNRESOLVED)}

    report = await _harness(answers, extractions).execute()

    weakest = report.weakest_layer
    assert weakest is not None
    assert weakest.layer == "L2", "outcome is L2's, and it is the only disagreement"


async def test_a_layer_with_nothing_comparable_is_not_named_weakest() -> None:
    """An unanswered layer is not a badly performing one, and naming it
    sends someone to the wrong prompt.
    """
    report = await _harness((_answer("C-0001"),), {}).execute()

    assert report.weakest_layer is None


async def test_the_report_carries_the_columns_that_cannot_be_scored() -> None:
    """E2's finding travels with every report, so "we did not score this"
    is never mistaken for "this scored badly".
    """
    report = await _harness((_answer("C-0001"),), {}).execute()

    assert {entry.field for entry in report.unscored_fields} == {
        "rule_refs",
        "archetype",
        "aht_seconds",
    }


async def test_an_empty_answer_key_reports_nothing_rather_than_dividing_by_zero() -> None:
    report = await _harness((), {}).execute()

    assert report.calls == 0
    assert report.coverage == pytest.approx(0.0)
    assert report.comparable is False


async def test_the_harness_applies_no_pass_mark() -> None:
    """Deliberately absent. Plan §8 gives "good enough" to Minnie with the
    numbers in hand, and a harness that graded its own subject would be the
    last place to notice it had the bar wrong.
    """
    report = await _harness((_answer("C-0001"),), {"C-0001": _extraction("C-0001")}).execute()

    assert not hasattr(report, "passed")
    assert not hasattr(report, "threshold")
    assert not any(hasattr(field, "acceptable") for field in report.fields)
