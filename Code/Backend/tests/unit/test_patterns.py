"""The four calculation patterns, and the build notes they enforce.

Two of the Metrics sheet's build notes describe mistakes you make by passing
the wrong argument — the classic denominator error, and measuring
escalations against all calls. Both are tested here rather than in each of
the seven metrics that would otherwise repeat them.
"""

from __future__ import annotations

import pytest

from domain.aggregation.figure import Basis, WithheldReason
from domain.aggregation.patterns import normalised_rate, share, time_aggregate
from domain.dashboard_config import MetricThreshold
from tests.fixtures.tagged_calls import call, calls


def _threshold(*, min_n: int | None = 30, counts: str = "calls") -> MetricThreshold:
    return MetricThreshold(
        key="contact_rate",
        sheet_row="1",
        name="Contact rate",
        window_weeks=12,
        min_n=min_n,
        counts=counts,
    )


# --- Normalised rate (metrics 1 and 2) -------------------------------------


def test_a_rate_is_annualised_from_the_windows_own_length() -> None:
    """30 calls over 12 weeks from 1,000 lives is 130 per 1,000 per year.

    30 x (52/12) = 130, over 1,000/1,000 = 1. A window measured wrongly
    scales every annualised figure by the same factor, and the shape of the
    chart does not change, so nothing looks wrong.
    """
    figure = normalised_rate(
        _threshold(), matching=calls(30), population=1_000, per=1_000, weeks=12
    )

    assert figure.value == pytest.approx(130.0)
    assert figure.basis is Basis.OBSERVED


def test_the_population_divides_as_per_thousand_not_as_a_headcount() -> None:
    """Halving the population doubles the rate — the whole point of
    normalising is that a big employer and a small one become comparable.
    """
    small = normalised_rate(_threshold(), matching=calls(30), population=500, per=1_000, weeks=12)
    large = normalised_rate(_threshold(), matching=calls(30), population=1_000, per=1_000, weeks=12)

    assert small.value == pytest.approx(2 * (large.value or 0))


def test_a_population_of_zero_is_withheld_rather_than_divided_by() -> None:
    """Undefined, not unreliable — so the reason is NO_DENOMINATOR and the
    page says the population is missing rather than that the sample is small.
    """
    figure = normalised_rate(_threshold(), matching=calls(30), population=0, per=1_000, weeks=12)

    assert figure.withheld_reason is WithheldReason.NO_DENOMINATOR
    assert figure.value is None


def test_a_rate_below_min_n_is_withheld_even_with_a_population() -> None:
    figure = normalised_rate(
        _threshold(), matching=calls(29), population=1_000, per=1_000, weeks=12
    )

    assert figure.withheld_reason is WithheldReason.BELOW_MIN_N


# --- Share (metrics 3-8 and 11) --------------------------------------------


def test_a_share_is_gated_on_the_denominator_not_the_numerator() -> None:
    """Escalation integrity again: 7 handled of 11 triggered is a sample of
    11, not of 7, and not of the 100 calls it sits inside.
    """
    triggered = calls(11, prefix="T")
    figure = share(_threshold(counts="triggers"), numerator=triggered[:7], denominator=triggered)

    assert figure.value is None
    assert figure.n == 11
    assert "11 triggers" in figure.caveats[0]


def test_a_share_publishes_once_the_denominator_clears_min_n() -> None:
    denominator = calls(40)
    figure = share(_threshold(), numerator=denominator[:10], denominator=denominator)

    assert figure.value == pytest.approx(0.25)
    assert figure.n == 40


def test_an_empty_denominator_is_withheld_not_divided_by() -> None:
    figure = share(_threshold(), numerator=(), denominator=())

    assert figure.withheld_reason is WithheldReason.NO_DENOMINATOR


def test_a_numerator_outside_its_denominator_is_a_programming_error() -> None:
    """It would produce a share above 1, which no reader would question
    because rates above 100% are usually explained away as rounding.
    """
    with pytest.raises(ValueError, match="not in the denominator"):
        share(_threshold(), numerator=(call("C-9999"),), denominator=calls(40))


def test_the_evidence_of_a_share_is_its_denominator() -> None:
    """A reader disputing "7 of 11 handled" needs the 11, not the 7. The
    four that were not handled are the ones worth opening.
    """
    denominator = calls(40)
    figure = share(_threshold(), numerator=denominator[:10], denominator=denominator)

    assert len(figure.call_ids) == 40


# --- Time aggregate (metric 9) ---------------------------------------------


def test_cost_to_serve_is_minutes_per_life_per_year() -> None:
    """30 calls of 600s over 12 weeks, 100 lives:
    30 x 600 x (52/12) / 60 / 100 = 13 minutes per life per year.
    """
    figure = time_aggregate(
        _threshold(), calls=calls(30, aht_seconds=600), population=100, weeks=12
    )

    assert figure.value == pytest.approx(13.0)


def test_cost_to_serve_says_it_is_a_floor() -> None:
    """AHT is talk time only. A reader who takes it for the whole cost of
    serving an account is reading it as more than it is.
    """
    figure = time_aggregate(
        _threshold(), calls=calls(30, aht_seconds=600), population=100, weeks=12
    )

    assert any("floor" in caveat for caveat in figure.caveats)


def test_calls_with_no_talk_time_are_excluded_rather_than_counted_as_zero() -> None:
    """Counting an untimed call as zero seconds understates cost to serve
    and does it invisibly — the call is in n, contributing nothing.
    """
    timed = calls(30, aht_seconds=600)
    untimed = calls(10, prefix="U", aht_seconds=None)

    figure = time_aggregate(_threshold(), calls=(*timed, *untimed), population=100, weeks=12)

    assert figure.n == 30
    assert figure.value == pytest.approx(13.0)


def test_a_window_with_no_timed_call_at_all_is_withheld() -> None:
    figure = time_aggregate(
        _threshold(), calls=calls(30, aht_seconds=None), population=100, weeks=12
    )

    assert figure.withheld_reason is WithheldReason.NO_DENOMINATOR


def test_cost_to_serve_without_enrolled_lives_is_withheld() -> None:
    figure = time_aggregate(_threshold(), calls=calls(30), population=0, weeks=12)

    assert figure.withheld_reason is WithheldReason.NO_DENOMINATOR
