"""The wire format for every insights response.

`Figure` makes a withheld value impossible to construct. JSON hands that
guarantee back — `null` is one `?? 0` away from becoming a confident zero —
so most of these tests are about what a client can and cannot do with what
it receives.
"""

from __future__ import annotations

import json

from application.ports.insights_source import CorpusQuery, CorpusSlice
from domain.aggregation.figure import EpistemicClass, Figure, WithheldReason
from domain.aggregation.filters import AppliedFilter, FilteredCalls, Unmeasurable
from domain.value_objects.call_source import CallSource
from frameworks_drivers.api.v1.insights.envelope import FigureResponse, ScopeResponse


class TestWithheldNeverBecomesZero:
    def test_a_withheld_figure_serialises_value_as_null(self) -> None:
        figure = Figure.withheld(WithheldReason.BELOW_MIN_N, ("C-1", "C-2"))

        payload = json.loads(FigureResponse.of(figure).model_dump_json(by_alias=True))

        assert payload["value"] is None
        assert payload["value"] != 0

    def test_published_is_the_field_to_branch_on(self) -> None:
        """A client should not have to infer suppression from a missing value."""
        withheld = FigureResponse.of(Figure.withheld(WithheldReason.NO_FIELD))
        measured = FigureResponse.of(Figure.measured(0.0, ("C-1",)))

        assert withheld.published is False
        assert measured.published is True

    def test_a_real_zero_is_distinguishable_from_a_withheld_figure(self) -> None:
        """The distinction the whole envelope exists to preserve.

        A measured 0.0 and a withheld figure both render as "0" if a client
        coalesces null. They differ on `published`, which does not.
        """
        real_zero = FigureResponse.of(Figure.measured(0.0, ("C-1",)))
        withheld = FigureResponse.of(Figure.withheld(WithheldReason.BELOW_MIN_N, ("C-1",)))

        assert real_zero.value == 0.0
        assert real_zero.published is True
        assert withheld.value is None
        assert withheld.published is False

    def test_a_withheld_figure_always_carries_a_reason(self) -> None:
        payload = FigureResponse.of(Figure.withheld(WithheldReason.MONEY_UNKNOWN))

        assert payload.withheld_reason is not None
        assert payload.withheld_reason.code == "MONEY_UNKNOWN"
        assert payload.withheld_reason.label == "Cost per call not set"

    def test_a_published_figure_carries_no_reason(self) -> None:
        assert FigureResponse.of(Figure.measured(1.0, ("C-1",))).withheld_reason is None


class TestEvidence:
    def test_every_figure_opens_its_calls(self) -> None:
        figure = Figure.measured(0.25, ("C-1", "C-2", "C-3", "C-4"))

        payload = FigureResponse.of(figure)

        assert payload.call_ids == ["C-1", "C-2", "C-3", "C-4"]
        assert payload.n == 4

    def test_a_withheld_figure_keeps_its_evidence(self) -> None:
        """Told four calls is too few, a reader can still open those four."""
        figure = Figure.withheld(WithheldReason.BELOW_MIN_N, ("C-1", "C-2", "C-3", "C-4"))

        assert FigureResponse.of(figure).call_ids == ["C-1", "C-2", "C-3", "C-4"]

    def test_n_and_the_call_ids_cannot_disagree(self) -> None:
        payload = FigureResponse.of(Figure.measured(0.5, ("C-1", "C-2")))

        assert payload.n == len(payload.call_ids)

    def test_caveats_travel_with_the_figure(self) -> None:
        figure = Figure.measured(0.5, ("C-1",), caveats=("Talk time only.",))

        assert FigureResponse.of(figure).caveats == ["Talk time only."]


class TestEpistemicClass:
    def test_derived_is_labelled_on_the_wire(self) -> None:
        """Composites "must be labelled as derived wherever they surface"."""
        payload = json.loads(
            FigureResponse.of(Figure.derived(3.2, ("C-1",))).model_dump_json(by_alias=True)
        )

        assert payload["epistemic"] == {"code": "DERIVED", "label": "Derived"}

    def test_measured_and_withheld_serialise_as_their_names(self) -> None:
        measured = json.loads(
            FigureResponse.of(Figure.measured(1.0, ("C-1",))).model_dump_json(by_alias=True)
        )
        withheld = json.loads(
            FigureResponse.of(Figure.withheld(WithheldReason.NOT_ELIGIBLE)).model_dump_json(
                by_alias=True
            )
        )

        assert measured["epistemic"]["code"] == "MEASURED"
        assert withheld["epistemic"]["code"] == "WITHHELD"
        assert withheld["withheldReason"]["code"] == "NOT_ELIGIBLE"
        assert withheld["withheldReason"]["label"] == "Not enough calls to assess"

    def test_the_three_classes_are_the_whole_vocabulary(self) -> None:
        """Pinned deliberately: this enum has no source and needs confirming.

        If it changes, this test is the reminder that the wire format and
        every generated client change with it.
        """
        assert [member.value for member in EpistemicClass] == [
            "MEASURED",
            "DERIVED",
            "WITHHELD",
        ]


class TestScope:
    def test_scope_reports_both_counts_and_the_shortfall(self) -> None:
        filtered = FilteredCalls(
            calls=(),
            considered=100,
            unmeasurable=(Unmeasurable("categories", 7),),
            applied=(AppliedFilter("regions", ("West",)),),
        )

        scope = ScopeResponse.of(CorpusSlice(), filtered, CorpusQuery())

        assert scope.considered == 100
        assert scope.matched == 0
        assert scope.unmeasurable[0].field == "categories"
        assert scope.unmeasurable[0].calls == 7

    def test_the_applied_row_travels_out(self) -> None:
        filtered = FilteredCalls(
            calls=(),
            considered=0,
            applied=(AppliedFilter("categories", ("Claims & EOB",)),),
        )

        scope = ScopeResponse.of(CorpusSlice(), filtered, CorpusQuery())

        assert scope.applied_filters[0].field == "categories"
        assert scope.applied_filters[0].values == ["Claims & EOB"]

    def test_sources_are_echoed_back(self) -> None:
        query = CorpusQuery(sources=frozenset({CallSource.CORPUS_PDF, CallSource.AUDIO}))

        scope = ScopeResponse.of(CorpusSlice(), FilteredCalls((), 0), query)

        assert scope.sources == ["AUDIO", "CORPUS_PDF"]

    def test_no_source_selection_is_an_empty_list_meaning_all(self) -> None:
        scope = ScopeResponse.of(CorpusSlice(), FilteredCalls((), 0), CorpusQuery())

        assert scope.sources == []

    def test_corpus_exclusions_reach_the_response(self) -> None:
        corpus = CorpusSlice(
            undated=("C-9",),
            unanalysed=("C-8",),
            unavailable_fields=("control_exceptions",),
        )

        scope = ScopeResponse.of(corpus, FilteredCalls((), 0), CorpusQuery())

        assert scope.excluded_calls == 2
        assert any("no date" in caveat for caveat in scope.caveats)
        assert any("control_exceptions" in caveat for caveat in scope.caveats)

    def test_a_clean_corpus_carries_no_boilerplate(self) -> None:
        scope = ScopeResponse.of(CorpusSlice(), FilteredCalls((), 0), CorpusQuery())

        assert scope.caveats == []
        assert scope.excluded_calls == 0
