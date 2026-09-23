"""Member effort and complexity — our own composites, ported formula for
formula from Prototype/tools/03_join_corpus.py, never re-derived.
"""

from __future__ import annotations

import pytest

from domain.derivations.member_effort_complexity import (
    complexity_score,
    effort_score,
    percentile_rank,
)
from domain.value_objects.derived_band import DerivedBand, band_for
from domain.value_objects.outcome import Outcome


class TestPercentileRank:
    def test_the_lowest_value_in_the_corpus_ranks_at_zero(self) -> None:
        corpus = [10.0, 20.0, 30.0, 40.0]

        assert percentile_rank(corpus, 10.0) == 0.0

    def test_the_highest_value_in_the_corpus_ranks_at_one(self) -> None:
        corpus = [10.0, 20.0, 30.0, 40.0]

        assert percentile_rank(corpus, 40.0) == 1.0

    def test_a_middling_value_ranks_by_the_share_strictly_below_it(self) -> None:
        corpus = [10.0, 20.0, 30.0, 40.0]

        # Two of four values (10, 20) sit strictly below 30, over a corpus
        # of size 4 (divisor is len - 1 = 3).
        assert percentile_rank(corpus, 30.0) == pytest.approx(2 / 3)

    def test_ties_rank_at_the_share_below_them_not_alongside_them(self) -> None:
        corpus = [10.0, 20.0, 20.0, 30.0]

        assert percentile_rank(corpus, 20.0) == pytest.approx(1 / 3)

    def test_a_single_call_corpus_does_not_divide_by_zero(self) -> None:
        assert percentile_rank([15.0], 15.0) == 0.0

    def test_a_value_outside_the_corpus_still_ranks_by_what_it_exceeds(self) -> None:
        corpus = [10.0, 20.0, 30.0]

        assert percentile_rank(corpus, 100.0) == 1.0


class TestEffortScore:
    def _baseline(self, **overrides: object) -> int:
        kwargs: dict[str, object] = {
            "aht_percentile": 0.0,
            "is_failure_driven_repeat": False,
            "escalation_requested_by_caller": False,
            "outcome": Outcome.RESOLVED,
            "escalation_triggered": False,
            "escalation_handled": False,
        }
        kwargs.update(overrides)
        return effort_score(**kwargs)  # type: ignore[arg-type]

    def test_a_call_at_the_bottom_of_every_factor_scores_zero(self) -> None:
        assert self._baseline() == 0

    def test_aht_percentile_contributes_45_points_at_the_top(self) -> None:
        assert self._baseline(aht_percentile=1.0) == 45

    def test_a_failure_driven_repeat_adds_20(self) -> None:
        assert self._baseline(is_failure_driven_repeat=True) == 20

    def test_a_caller_requested_escalation_adds_12(self) -> None:
        assert self._baseline(escalation_requested_by_caller=True) == 12

    def test_an_unresolved_outcome_adds_18(self) -> None:
        assert self._baseline(outcome=Outcome.UNRESOLVED) == 18

    def test_a_partially_resolved_outcome_adds_8(self) -> None:
        assert self._baseline(outcome=Outcome.PARTIALLY_RESOLVED) == 8

    def test_a_resolved_outcome_adds_nothing(self) -> None:
        assert self._baseline(outcome=Outcome.RESOLVED) == 0

    def test_a_triggered_but_unhandled_escalation_adds_10(self) -> None:
        assert self._baseline(escalation_triggered=True, escalation_handled=False) == 10

    def test_a_triggered_and_handled_escalation_adds_nothing(self) -> None:
        assert self._baseline(escalation_triggered=True, escalation_handled=True) == 0

    def test_every_factor_stacked_together_is_capped_at_100(self) -> None:
        score = self._baseline(
            aht_percentile=1.0,
            is_failure_driven_repeat=True,
            escalation_requested_by_caller=True,
            outcome=Outcome.UNRESOLVED,
            escalation_triggered=True,
            escalation_handled=False,
        )

        assert score == 100


class TestComplexityScore:
    def _baseline(self, **overrides: object) -> int:
        kwargs: dict[str, object] = {
            "aht_percentile": 0.0,
            "turn_count_percentile": 0.0,
            "rule_ref_count": 0,
            "signal_count": 0,
        }
        kwargs.update(overrides)
        return complexity_score(**kwargs)  # type: ignore[arg-type]

    def test_a_call_at_the_bottom_of_every_factor_scores_zero(self) -> None:
        assert self._baseline() == 0

    def test_aht_percentile_contributes_55_points_at_the_top(self) -> None:
        assert self._baseline(aht_percentile=1.0) == 55

    def test_turn_count_percentile_contributes_45_points_at_the_top(self) -> None:
        assert self._baseline(turn_count_percentile=1.0) == 45

    def test_two_or_more_rule_references_add_8(self) -> None:
        assert self._baseline(rule_ref_count=2) == 8

    def test_a_single_rule_reference_adds_nothing(self) -> None:
        assert self._baseline(rule_ref_count=1) == 0

    def test_two_or_more_signals_add_6(self) -> None:
        assert self._baseline(signal_count=2) == 6

    def test_a_single_signal_adds_nothing(self) -> None:
        assert self._baseline(signal_count=1) == 0

    def test_every_factor_stacked_together_is_capped_at_100(self) -> None:
        score = self._baseline(
            aht_percentile=1.0,
            turn_count_percentile=1.0,
            rule_ref_count=5,
            signal_count=5,
        )

        assert score == 100


class TestDerivedBand:
    def test_a_score_of_60_is_high(self) -> None:
        assert band_for(60) is DerivedBand.HIGH

    def test_a_score_of_59_is_medium(self) -> None:
        assert band_for(59) is DerivedBand.MEDIUM

    def test_a_score_of_35_is_medium(self) -> None:
        assert band_for(35) is DerivedBand.MEDIUM

    def test_a_score_of_34_is_low(self) -> None:
        assert band_for(34) is DerivedBand.LOW

    def test_a_score_of_zero_is_low(self) -> None:
        assert band_for(0) is DerivedBand.LOW

    def test_a_score_of_100_is_high(self) -> None:
        assert band_for(100) is DerivedBand.HIGH
