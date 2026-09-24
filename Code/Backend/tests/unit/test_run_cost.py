"""What a run cost, and the three different things a zero can mean.

Every test here is about not understating a figure. A cost that reads as
precise when half its providers reported nothing is the same class of
mistake as a withheld figure rendered as zero — the format tells the reader
something the number cannot support.
"""

from __future__ import annotations

import pytest

from domain.run_cost import run_cost
from domain.value_objects.token_usage import TokenUsage


def test_usages_sum() -> None:
    total = TokenUsage.total(
        [
            TokenUsage(input_tokens=100, output_tokens=20),
            TokenUsage(input_tokens=50, output_tokens=5),
        ]
    )

    assert (total.input_tokens, total.output_tokens) == (150, 25)
    assert total.total_tokens == 175


def test_one_unreported_part_makes_the_whole_total_a_floor() -> None:
    """The provider spent the tokens; nobody counted them. A sum that
    dropped this would report a run costing twice what it claims as if it
    were exact.
    """
    total = TokenUsage(input_tokens=100, output_tokens=20) + TokenUsage.unreported()

    assert total.reported is False
    assert total.total_tokens == 120, "still the best figure available, just not the whole one"


def test_a_cached_stage_is_a_reported_zero_not_an_unknown() -> None:
    """The stage cache answered and no provider was called, so the call
    genuinely cost nothing. Conflating that with an unreported provider
    would mark every cached run as unmeasurable.
    """
    cached = TokenUsage()

    assert cached.reported is True
    assert (cached + TokenUsage(input_tokens=10, output_tokens=2)).reported is True


def test_an_empty_run_is_a_reported_zero() -> None:
    assert TokenUsage.total([]).reported is True


def test_a_complete_run_states_its_cost_plainly() -> None:
    cost = run_cost(
        [TokenUsage(input_tokens=100, output_tokens=20) for _ in range(3)],
        [120.0, 130.0, 110.0],
    )

    assert cost.complete is True
    assert cost.usage.total_tokens == 360
    assert cost.duration_ms == pytest.approx(360.0)
    assert "360 tokens across 3 call(s)" in cost.summary
    assert "At least" not in cost.summary


def test_a_run_with_an_unreported_item_says_at_least() -> None:
    """The word is the whole point. A reader shown a precise-looking number
    for a run half of whose providers reported nothing has been misled by
    the format rather than by the figure.
    """
    cost = run_cost([TokenUsage(input_tokens=100, output_tokens=20), TokenUsage.unreported()])

    assert cost.complete is False
    assert cost.unreported_items == 1
    assert cost.summary.startswith("At least")
    assert "so this is a floor" in cost.summary


def test_a_run_nothing_ran_in_says_so_rather_than_costing_nothing() -> None:
    cost = run_cost([])

    assert cost.items == 0
    assert cost.summary == "No item in this run recorded a token cost."


def test_items_without_a_duration_do_not_count_as_zero_time() -> None:
    """A pending item has no duration. Summing it as 0.0 would be harmless
    for the total but is wrong in principle and would spoil any average.
    """
    cost = run_cost([TokenUsage(input_tokens=1, output_tokens=1)] * 2, [100.0, None])

    assert cost.duration_ms == pytest.approx(100.0)


def test_thousands_are_separated_because_a_reader_has_to_scan_it() -> None:
    cost = run_cost([TokenUsage(input_tokens=1_234_567, output_tokens=0)])

    assert "1,234,567 tokens" in cost.summary
