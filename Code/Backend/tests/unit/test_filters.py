"""Filters slice, never hide.

Most of what follows tests one distinction: a call excluded because its
value *differs* versus a call excluded because its value is *unknown*. Any
filter can narrow a list; the reason this module exists is that it refuses
to report the second as though it were the first.
"""

from __future__ import annotations

from datetime import date

import pytest

from domain.aggregation.call_tags import CallContext, CallTags, EmployerFacts
from domain.aggregation.filters import (
    NO_FILTERS,
    AppliedFilter,
    InsightFilters,
)
from domain.dashboard_config import QualityBands
from domain.value_objects.category import Category
from domain.value_objects.complaint import Complaint
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.escalation import Escalation
from domain.value_objects.intent_statement import IntentStatement
from domain.value_objects.intent_type import IntentType
from domain.value_objects.outcome import Outcome
from domain.value_objects.product_line import ProductLine
from domain.value_objects.quality_band import QualityBand
from domain.value_objects.signal_type import SignalType

BANDS = QualityBands(good_min=86, average_min=60)

EMPLOYERS = (
    EmployerFacts(
        reference="EMP-1",
        name="Northwind",
        enrolled=120,
        region="West",
        industry="Retail",
        renewal_month="January",
        broker_ref="BRK-1",
    ),
    EmployerFacts(
        reference="EMP-2",
        name="Eastgate",
        enrolled=40,
        region="East",
        industry="Logistics",
        renewal_month="June",
        broker_ref="BRK-2",
    ),
)


def call(reference: str = "C-1", **tag_overrides: object) -> CallContext:
    """A call that passes every filter unless a test takes something away."""
    context_keys = {"employer_ref", "broker_of_record_ref", "agent_ref", "occurred_on"}
    context = {key: tag_overrides.pop(key) for key in list(tag_overrides) if key in context_keys}
    defaults: dict[str, object] = {
        "outcome": Outcome.RESOLVED,
        "category": Category.CLAIMS_AND_EOB,
        "product_lines": (ProductLine.DENTAL,),
        "complaint": Complaint(present=True, attributed_to=ComplaintAttribution.BROKER),
        "signals": frozenset({SignalType.PROCESS_BREAKDOWN}),
        "escalation": Escalation(triggered=True),
        "control_exceptions": frozenset(),
        "intent": (IntentStatement(type=IntentType.EXPANSION, quote="q", turn_seq=1),),
        "quality_score": 90,
        "touchpoint": "Enrolment",
    }
    defaults.update(tag_overrides)
    return CallContext(
        tags=CallTags(reference=reference, **defaults),  # type: ignore[arg-type]
        occurred_on=context.get("occurred_on", date(2025, 3, 1)),  # type: ignore[arg-type]
        employer_ref=context.get("employer_ref", "EMP-1"),  # type: ignore[arg-type]
        agent_ref=context.get("agent_ref", "AG-1"),  # type: ignore[arg-type]
    )


class TestNoNarrowing:
    def test_empty_selection_keeps_everything(self) -> None:
        result = NO_FILTERS.apply([call("C-1"), call("C-2")])

        assert result.matched == 2
        assert result.considered == 2
        assert result.unmeasurable == ()

    def test_empty_selection_is_falsy(self) -> None:
        assert not InsightFilters()
        assert InsightFilters(regions=frozenset({"West"}))

    def test_summary_stays_quiet_when_nothing_is_missing(self) -> None:
        assert NO_FILTERS.apply([call()]).summary() == "1 of 1 calls"


class TestDiffersVersusUnknown:
    """The distinction the module exists for."""

    def test_a_different_value_is_out_of_scope_not_unmeasurable(self) -> None:
        filters = InsightFilters(categories=frozenset({Category.CLAIMS_AND_EOB}))

        result = filters.apply([call(category=Category.BILLING_AND_PREMIUM)])

        assert result.matched == 0
        assert result.unmeasurable == ()

    def test_an_absent_value_is_reported_not_silently_dropped(self) -> None:
        filters = InsightFilters(categories=frozenset({Category.CLAIMS_AND_EOB}))

        result = filters.apply([call(category=None)])

        assert result.matched == 0
        assert result.unmeasurable_calls == 1
        assert result.unmeasurable[0].field == "categories"

    def test_the_two_are_counted_apart_in_one_pass(self) -> None:
        filters = InsightFilters(outcomes=frozenset({Outcome.RESOLVED}))

        result = filters.apply(
            [
                call("C-1"),
                call("C-2", outcome=Outcome.UNRESOLVED),
                call("C-3", outcome=None),
            ]
        )

        assert result.matched == 1
        assert result.considered == 3
        assert result.unmeasurable_calls == 1

    def test_summary_names_the_field_that_cost_the_calls(self) -> None:
        filters = InsightFilters(touchpoints=frozenset({"Enrolment"}))

        summary = filters.apply([call("C-1"), call("C-2", touchpoint=None)]).summary()

        assert summary.startswith("1 of 2 calls")
        assert "touchpoints (1)" in summary

    def test_a_call_is_blamed_on_one_field_only(self) -> None:
        """Per-field counts sum to the total rather than double counting."""
        filters = InsightFilters(
            categories=frozenset({Category.CLAIMS_AND_EOB}),
            outcomes=frozenset({Outcome.RESOLVED}),
        )

        result = filters.apply([call(category=None, outcome=None)])

        assert result.unmeasurable_calls == 1
        assert len(result.unmeasurable) == 1

    def test_unmeasurable_is_ordered_by_field_not_by_count(self) -> None:
        filters = InsightFilters(
            categories=frozenset({Category.CLAIMS_AND_EOB}),
            outcomes=frozenset({Outcome.RESOLVED}),
        )

        result = filters.apply(
            [call("C-1", outcome=None), call("C-2", outcome=None), call("C-3", category=None)]
        )

        assert [entry.field for entry in result.unmeasurable] == ["categories", "outcomes"]


class TestCollections:
    def test_product_lines_match_on_membership_not_primary(self) -> None:
        filters = InsightFilters(product_lines=frozenset({ProductLine.VISION}))

        result = filters.apply([call(product_lines=(ProductLine.DENTAL, ProductLine.VISION))])

        assert result.matched == 1

    def test_no_product_line_at_all_is_unmeasurable(self) -> None:
        filters = InsightFilters(product_lines=frozenset({ProductLine.DENTAL}))

        result = filters.apply([call(product_lines=())])

        assert result.unmeasurable_calls == 1

    def test_no_signals_is_a_real_answer_not_a_gap(self) -> None:
        """The recorded ambiguity: an empty signal set reads as "none raised"."""
        filters = InsightFilters(signals=frozenset({SignalType.PROCESS_BREAKDOWN}))

        result = filters.apply([call(signals=frozenset())])

        assert result.matched == 0
        assert result.unmeasurable == ()

    def test_intent_matches_any_statement_on_the_call(self) -> None:
        filters = InsightFilters(intents=frozenset({IntentType.CANCELLATION}))
        statements = (
            IntentStatement(type=IntentType.EXPANSION, quote="a", turn_seq=1),
            IntentStatement(type=IntentType.CANCELLATION, quote="b", turn_seq=4),
        )

        assert filters.apply([call(intent=statements)]).matched == 1
        assert filters.apply([call(intent=())]).matched == 0


class TestAccountScope:
    def test_region_resolves_through_reference_data(self) -> None:
        filters = InsightFilters(regions=frozenset({"East"}))

        result = filters.apply(
            [call("C-1", employer_ref="EMP-1"), call("C-2", employer_ref="EMP-2")],
            employers=EMPLOYERS,
        )

        assert [c.reference for c in result.calls] == ["C-2"]

    def test_broker_filter_uses_the_broker_of_record(self) -> None:
        filters = InsightFilters(broker_refs=frozenset({"BRK-2"}))

        result = filters.apply([call(employer_ref="EMP-2")], employers=EMPLOYERS)

        assert result.matched == 1

    def test_a_call_with_no_employer_is_unmeasurable_against_a_region(self) -> None:
        filters = InsightFilters(regions=frozenset({"West"}))

        result = filters.apply([call(employer_ref=None)], employers=EMPLOYERS)

        assert result.unmeasurable_calls == 1

    def test_an_unresolvable_employer_is_unmeasurable_not_excluded(self) -> None:
        filters = InsightFilters(regions=frozenset({"West"}))

        result = filters.apply([call(employer_ref="EMP-UNKNOWN")], employers=EMPLOYERS)

        assert result.unmeasurable[0].field == "regions"

    def test_employer_filter_needs_no_reference_data(self) -> None:
        filters = InsightFilters(employer_refs=frozenset({"EMP-1"}))

        assert filters.apply([call(employer_ref="EMP-1")]).matched == 1

    def test_agent_filter(self) -> None:
        filters = InsightFilters(agent_refs=frozenset({"AG-9"}))

        assert filters.apply([call(agent_ref="AG-9")]).matched == 1
        assert filters.apply([call(agent_ref=None)]).unmeasurable_calls == 1

    def test_scope_is_blamed_before_attributes(self) -> None:
        """An out-of-scope call is not reported as missing a category."""
        filters = InsightFilters(
            employer_refs=frozenset({"EMP-1"}),
            categories=frozenset({Category.CLAIMS_AND_EOB}),
        )

        result = filters.apply([call(employer_ref="EMP-2", category=None)])

        assert result.unmeasurable == ()


class TestMissingContext:
    def test_region_without_reference_data_raises(self) -> None:
        filters = InsightFilters(regions=frozenset({"West"}))

        with pytest.raises(ValueError, match="employer reference data"):
            filters.apply([call()])

    def test_broker_without_reference_data_raises(self) -> None:
        filters = InsightFilters(broker_refs=frozenset({"BRK-1"}))

        with pytest.raises(ValueError, match="employer reference data"):
            filters.apply([call()])

    def test_quality_band_without_thresholds_raises(self) -> None:
        filters = InsightFilters(quality_bands=frozenset({QualityBand.GOOD}))

        with pytest.raises(ValueError, match="band thresholds"):
            filters.apply([call()])


class TestComplaintTarget:
    def test_matches_the_attributed_party(self) -> None:
        filters = InsightFilters(complaint_targets=frozenset({ComplaintAttribution.BROKER}))

        assert filters.apply([call()]).matched == 1

    def test_no_complaint_is_out_of_scope_not_unmeasurable(self) -> None:
        filters = InsightFilters(complaint_targets=frozenset({ComplaintAttribution.BROKER}))

        result = filters.apply([call(complaint=Complaint(present=False))])

        assert result.matched == 0
        assert result.unmeasurable == ()

    def test_a_present_complaint_always_has_a_target(self) -> None:
        """Why the filter has no "complained, target unknown" case."""
        with pytest.raises(ValueError, match="must carry an attribution"):
            Complaint(present=True)

    def test_no_complaint_field_at_all_is_unmeasurable(self) -> None:
        filters = InsightFilters(complaint_targets=frozenset({ComplaintAttribution.BROKER}))

        assert filters.apply([call(complaint=None)]).unmeasurable_calls == 1


class TestQualityBand:
    @pytest.mark.parametrize(
        ("score", "band", "matches"),
        [
            (90, QualityBand.GOOD, True),
            (70, QualityBand.GOOD, False),
            (70, QualityBand.AVERAGE, True),
        ],
    )
    def test_score_is_placed_in_a_band(self, score: int, band: QualityBand, matches: bool) -> None:
        filters = InsightFilters(quality_bands=frozenset({band}))

        result = filters.apply([call(quality_score=score)], quality_bands=BANDS)

        assert bool(result.matched) is matches

    def test_an_unscored_call_is_unmeasurable(self) -> None:
        filters = InsightFilters(quality_bands=frozenset({QualityBand.GOOD}))

        result = filters.apply([call(quality_score=None)], quality_bands=BANDS)

        assert result.unmeasurable[0].field == "quality_bands"


class TestYesNoFilters:
    def test_false_is_a_selection_not_an_unset_filter(self) -> None:
        filters = InsightFilters(escalated=False)

        result = filters.apply(
            [
                call("C-1", escalation=Escalation(triggered=True)),
                call("C-2", escalation=Escalation(triggered=False)),
            ]
        )

        assert [c.reference for c in result.calls] == ["C-2"]

    def test_a_missing_escalation_field_is_unmeasurable(self) -> None:
        assert InsightFilters(escalated=True).apply([call(escalation=None)]).unmeasurable_calls == 1

    def test_complaint_presence(self) -> None:
        filters = InsightFilters(complaint_present=False)

        assert filters.apply([call(complaint=Complaint(present=False))]).matched == 1
        assert filters.apply([call(complaint=None)]).unmeasurable_calls == 1

    def test_compliance_exception_is_never_unmeasurable(self) -> None:
        """An empty exception set is a real answer, so there is no unknown case."""
        filters = InsightFilters(compliance_exception=True)

        result = filters.apply([call(control_exceptions=frozenset())])

        assert result.matched == 0
        assert result.unmeasurable == ()


class TestAppliedRow:
    def test_reports_only_active_filters(self) -> None:
        filters = InsightFilters(regions=frozenset({"West"}), escalated=True)

        assert filters.applied() == (
            AppliedFilter("regions", ("West",)),
            AppliedFilter("escalated", ("yes",)),
        )

    def test_enum_values_read_as_the_sheet_words_them(self) -> None:
        filters = InsightFilters(categories=frozenset({Category.CLAIMS_AND_EOB}))

        assert filters.applied() == (AppliedFilter("categories", ("Claims & EOB",)),)

    def test_values_are_sorted_so_the_row_is_stable(self) -> None:
        filters = InsightFilters(regions=frozenset({"West", "East", "North"}))

        assert filters.applied()[0].values == ("East", "North", "West")

    def test_no_is_rendered_for_a_false_selection(self) -> None:
        assert InsightFilters(complaint_present=False).applied() == (
            AppliedFilter("complaint_present", ("no",)),
        )

    def test_the_row_travels_with_the_result(self) -> None:
        filters = InsightFilters(employer_refs=frozenset({"EMP-1"}))

        assert filters.apply([call()]).applied == filters.applied()
