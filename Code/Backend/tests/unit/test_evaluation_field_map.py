"""The answer-key-to-pipeline mapping, and the four traps it settles.

Each trap is a pairing that produces a plausible number rather than an
error, so each has a test naming what the wrong answer would have looked
like. The `rule_refs` one is the sharpest: mapped to the knowledge-failure
rule id, it would report a pipeline doing nothing wrong as catastrophically
broken.
"""

from __future__ import annotations

from domain.entities.call_extraction import CallExtraction
from domain.entities.ground_truth import GroundTruth, GroundTruthSignal
from domain.evaluation.comparison import Comparison, MissingSide, SetComparison, Verdict
from domain.evaluation.field_map import (
    UNSCORED,
    Layer,
    MappedField,
    compare_call,
    fields_for,
)
from domain.value_objects.category import Category
from domain.value_objects.complaint import Complaint
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.control_exception_type import ControlExceptionType
from domain.value_objects.intent_statement import IntentStatement
from domain.value_objects.intent_type import IntentType
from domain.value_objects.knowledge_failure import KnowledgeFailure
from domain.value_objects.outcome import Outcome
from domain.value_objects.product_line import ProductLine
from domain.value_objects.score import Score
from domain.value_objects.signal import Signal
from domain.value_objects.signal_type import SignalType


def _comparison(mapped: tuple[MappedField, ...], field: str) -> Comparison | SetComparison:
    return next(m.comparison for m in mapped if m.field == field)


def _verdict(mapped: tuple[MappedField, ...], field: str) -> Verdict:
    return _comparison(mapped, field).verdict


def _exact(mapped: tuple[MappedField, ...], field: str) -> Comparison:
    comparison = _comparison(mapped, field)
    assert isinstance(comparison, Comparison)
    return comparison


# --- Trap 1: rule_refs -----------------------------------------------------


def test_cited_rules_are_not_scored_at_all() -> None:
    """A call can cite four rules and misstate none. Mapped to the
    knowledge-failure rule id, a correct pipeline would look catastrophically
    wrong — and in fact nothing in the pipeline produces cited rules, so
    there is nothing to compare.
    """
    truth = GroundTruth(
        reference="C-0001",
        rule_refs=("A-05", "A-06", "C-12"),
        knowledge_failure_present=True,
        knowledge_failure_rule_ref="C-12",
    )
    extraction = CallExtraction(
        call_reference="C-0001",
        knowledge_failure=KnowledgeFailure(present=True, rule_id="C-12"),
    )

    mapped = compare_call(truth, extraction)

    assert "rule_refs" not in {m.field for m in mapped}
    assert _verdict(mapped, "knowledge_failure.rule_id") is Verdict.AGREED


def test_the_unscored_columns_are_listed_with_their_reasons() -> None:
    """ "We did not score this" and "this scored badly" look identical in a
    report that omits one of them, and only the second is the pipeline's
    fault.
    """
    listed = {entry.field for entry in UNSCORED}

    assert listed == {"rule_refs", "archetype", "aht_seconds"}
    assert all(entry.why.strip() for entry in UNSCORED)


def test_control_exceptions_are_scored_as_a_set_of_types() -> None:
    """Metric 7 is reported by type, never as one blended number, so the
    types compare as a set and keep precision and recall apart.
    """
    truth = GroundTruth(reference="C-0001", control_exceptions=("no_recording_disclosure",))
    extraction = CallExtraction(
        call_reference="C-0001",
        control_exceptions=frozenset(
            {
                ControlExceptionType.NO_RECORDING_DISCLOSURE,
                ControlExceptionType.DISCLOSURE_BEFORE_VERIFICATION,
            }
        ),
    )

    comparison = _comparison(compare_call(truth, extraction), "control_exceptions")

    assert isinstance(comparison, SetComparison)
    assert comparison.matched == {"no_recording_disclosure"}
    assert comparison.spurious == {"disclosure_before_verification"}
    assert comparison.missed == frozenset()


def test_control_exceptions_belong_to_l1() -> None:
    mapped = compare_call(GroundTruth(reference="C-0001"), None)

    assert "control_exceptions" in {m.field for m in fields_for(Layer.L1, mapped)}


def test_control_exceptions_l1_never_ran_for_are_incomparable_not_empty() -> None:
    """A row written before L1's result was kept reads back as `None`, not
    as "found none" — scoring it as an empty set would credit the pipeline
    with every clean call it never looked at.
    """
    truth = GroundTruth(reference="C-0001")
    extraction = CallExtraction(call_reference="C-0001", control_exceptions=None)

    comparison = _comparison(compare_call(truth, extraction), "control_exceptions")

    assert comparison.missing is MissingSide.PIPELINE


def test_the_benefit_disclosure_type_nothing_produces_counts_as_missed() -> None:
    """Nothing emits `missing_benefit_disclosure` yet, so a tracker row
    carrying it is a real recall miss rather than something to map away.
    """
    truth = GroundTruth(reference="C-0001", control_exceptions=("missing_benefit_disclosure",))
    extraction = CallExtraction(call_reference="C-0001", control_exceptions=frozenset())

    comparison = _comparison(compare_call(truth, extraction), "control_exceptions")

    assert isinstance(comparison, SetComparison)
    assert comparison.missed == {"missing_benefit_disclosure"}


# --- Trap 2: product_line --------------------------------------------------


def test_a_multi_line_call_agrees_when_the_tracker_s_line_was_found() -> None:
    """The tracker holds one value and the schema an array, so exact-set
    comparison is impossible — the tracker cannot express a two-line call.
    """
    truth = GroundTruth(reference="C-0001", product_line="dental")
    extraction = CallExtraction(
        call_reference="C-0001",
        product_lines=(ProductLine.DENTAL, ProductLine.VISION),
    )

    assert _verdict(compare_call(truth, extraction), "product_line") is Verdict.AGREED


def test_over_emission_stays_visible_even_though_it_passes() -> None:
    """A pipeline emitting every line on every call passes membership. It
    has to do so *visibly*, so the whole extracted set travels in `actual`.
    """
    truth = GroundTruth(reference="C-0001", product_line="dental")
    extraction = CallExtraction(call_reference="C-0001", product_lines=tuple(ProductLine))

    comparison = _exact(compare_call(truth, extraction), "product_line")

    assert comparison.verdict is Verdict.AGREED
    assert "vision" in (comparison.actual or "")
    assert "chiro" in (comparison.actual or "")


def test_missing_the_tracker_s_line_disagrees() -> None:
    truth = GroundTruth(reference="C-0001", product_line="dental")
    extraction = CallExtraction(call_reference="C-0001", product_lines=(ProductLine.VISION,))

    assert _verdict(compare_call(truth, extraction), "product_line") is Verdict.DISAGREED


# --- Trap 4: score ---------------------------------------------------------


def test_score_is_flagged_derived_rather_than_treated_as_evidence() -> None:
    """The rubric is deterministic given the markers, so score agreement is
    a derived view of marker agreement — not a second opinion about it.
    """
    mapped = compare_call(GroundTruth(reference="C-0001", score=91), None)

    score = next(m for m in mapped if m.field == "score")

    assert score.derived is True
    assert all(not m.derived for m in mapped if m.field != "score")


# --- A pipeline that produced nothing --------------------------------------


def test_a_call_the_pipeline_never_reached_is_incomparable_not_wrong() -> None:
    """Every field comes back NOT_COMPARABLE naming the pipeline as the
    missing side, which is what stops a failed run reading as a set of
    fields nobody could score.
    """
    truth = GroundTruth(
        reference="C-0001",
        outcome=Outcome.RESOLVED,
        category=Category.CLAIMS_AND_EOB,
        complaint_present=True,
        complaint_attributed_to="CHOICE",
    )

    mapped = compare_call(truth, None)

    assert all(m.comparison.verdict is Verdict.NOT_COMPARABLE for m in mapped)
    assert _exact(mapped, "outcome").missing is MissingSide.PIPELINE


# --- Layers ----------------------------------------------------------------


def test_every_mapped_field_belongs_to_a_layer() -> None:
    """§8 asks for agreement per layer, and per layer is the half that says
    what to fix: L2 weak is a prompt to rewrite, L4 weak is a taxonomy
    problem.
    """
    mapped = compare_call(GroundTruth(reference="C-0001"), None)

    assert {m.layer for m in mapped} <= set(Layer)
    assert fields_for(Layer.L3, mapped), "L3 owns knowledge failure and the score"
    assert fields_for(Layer.L4, mapped), "L4 owns signals and gaps"


def test_the_complaint_detail_is_named_attribution_target() -> None:
    """The Metrics sheet's own word for this dimension. "Party" is §7A's v10
    fault-record vocabulary and does not exist in v9, so using it here sends
    a reader looking for a field that was never built.
    """
    mapped = compare_call(GroundTruth(reference="C-0001"), None)

    assert "complaint.attribution_target" in {m.field for m in mapped}
    assert not any("party" in m.field for m in mapped)


# --- Signals ---------------------------------------------------------------


def test_signals_compare_as_a_set_of_codes() -> None:
    truth = GroundTruth(
        reference="C-0001",
        signals=(
            GroundTruthSignal(code="billing_defect", severity="HIGH", owner_team="Operations"),
        ),
    )
    extraction = CallExtraction(
        call_reference="C-0001",
        signals=(Signal(type=SignalType.BILLING_DEFECT, quote="still billing", turn_seq=4),),
    )

    assert _verdict(compare_call(truth, extraction), "signals") is Verdict.AGREED


def test_a_complaint_and_its_target_are_compared_separately() -> None:
    truth = GroundTruth(
        reference="C-0001", complaint_present=True, complaint_attributed_to="CHOICE"
    )
    extraction = CallExtraction(
        call_reference="C-0001",
        complaint=Complaint(present=True, attributed_to=ComplaintAttribution.BROKER),
    )

    mapped = compare_call(truth, extraction)

    assert _verdict(mapped, "complaint.present") is Verdict.AGREED
    assert _verdict(mapped, "complaint.attribution_target") is Verdict.DISAGREED


# --- Intent, and the remaining "pipeline said nothing" branches -------------


def test_intent_agrees_when_the_trackers_type_is_among_the_extracted_ones() -> None:
    """Same shape as product line: the tracker names one, the schema allows
    several.
    """
    truth = GroundTruth(reference="C-0001", intent_type="market_test")
    extraction = CallExtraction(
        call_reference="C-0001",
        intent=(
            IntentStatement(type=IntentType.MARKET_TEST, quote="going out to bid", turn_seq=14),
        ),
    )

    assert _verdict(compare_call(truth, extraction), "intent") is Verdict.AGREED


def test_intent_disagrees_on_a_different_type() -> None:
    truth = GroundTruth(reference="C-0001", intent_type="cancellation")
    extraction = CallExtraction(
        call_reference="C-0001",
        intent=(IntentStatement(type=IntentType.EXPANSION, quote="add vision?", turn_seq=9),),
    )

    assert _verdict(compare_call(truth, extraction), "intent") is Verdict.DISAGREED


def test_a_layer_that_extracted_nothing_is_incomparable_not_a_disagreement() -> None:
    """The tracker recorded an intent and a product line; L2 ran and found
    neither. That is the pipeline having no value, not the pipeline being
    wrong — and crediting it either way would misreport L2.
    """
    truth = GroundTruth(reference="C-0001", intent_type="market_test", product_line="dental")
    extraction = CallExtraction(call_reference="C-0001", intent=(), product_lines=())

    mapped = compare_call(truth, extraction)

    assert _exact(mapped, "intent").missing is MissingSide.PIPELINE
    assert _exact(mapped, "product_line").missing is MissingSide.PIPELINE


def test_the_tracker_recording_no_intent_is_not_the_pipelines_problem() -> None:
    truth = GroundTruth(reference="C-0001", intent_type=None, product_line="")
    extraction = CallExtraction(
        call_reference="C-0001",
        intent=(IntentStatement(type=IntentType.EXPANSION, quote="add vision?", turn_seq=9),),
        product_lines=(ProductLine.DENTAL,),
    )

    mapped = compare_call(truth, extraction)

    assert _exact(mapped, "intent").missing is MissingSide.ANSWER_KEY
    assert _exact(mapped, "product_line").missing is MissingSide.ANSWER_KEY


def test_a_scored_call_compares_its_score() -> None:
    truth = GroundTruth(reference="C-0001", score=91)
    extraction = CallExtraction(call_reference="C-0001", quality_score=Score(91))

    assert _verdict(compare_call(truth, extraction), "score") is Verdict.AGREED
