"""The decisions made from the thresholds, at their boundaries.

Every test here sits on an off-by-one, because that is the only way these
functions fail. A figure published one call below its min n does not look
wrong, it looks like a figure; an employer banded one life into the wrong
peer group is compared against the wrong median and nothing says so.
"""

from __future__ import annotations

import pytest

from domain.dashboard_config import (
    BrokerPatternTest,
    DashboardConfig,
    MetricThreshold,
    PeerSizeBand,
    QualityBands,
    RiskFlagConfig,
)
from domain.value_objects.quality_band import QualityBand


def _metric(*, key: str = "contact_rate", min_n: int | None = 30) -> MetricThreshold:
    return MetricThreshold(
        key=key,
        sheet_row="1",
        name="Contact rate",
        window_weeks=12,
        min_n=min_n,
        counts="calls",
    )


def _config(
    *, metrics: tuple[MetricThreshold, ...] = (), cost: float | None = None
) -> DashboardConfig:
    return DashboardConfig(
        version="1.0.0",
        metrics=metrics or (_metric(),),
        cost_per_call=cost,
        peer_size_bands=(
            PeerSizeBand(label="2-24 lives", min_lives=2, max_lives=24),
            PeerSizeBand(label="25-74 lives", min_lives=25, max_lives=74),
            PeerSizeBand(label="200+ lives", min_lives=200, max_lives=None),
        ),
        broker_ranking_floor_lives=150,
        broker_pattern_test=BrokerPatternTest(
            min_adverse_mentions=3, min_distinct_employers=2, window_weeks=12
        ),
        quality_bands=QualityBands(good_min=86, average_min=60),
        risk_flag=RiskFlagConfig(eligibility_min_calls=3, flag_threshold=2, quote_min_calls=10),
    )


# --- Withholding -----------------------------------------------------------


@pytest.mark.parametrize(("n", "expected"), [(0, True), (29, True), (30, False), (31, False)])
def test_a_figure_is_withheld_below_min_n_and_published_at_it(n: int, expected: bool) -> None:
    assert _metric().withheld(n) is expected


def test_a_metric_with_no_min_n_is_never_withheld() -> None:
    """The sheet's "n/a" and "—" rows: metric 12 is scored per call and call
    volume is cut any way, so neither has a sample that can be too small.
    """
    per_call = _metric(key="agent_quality_score", min_n=None)

    assert per_call.withheld(0) is False
    assert per_call.withheld(1) is False


def test_the_unit_of_n_is_carried_rather_than_dropped() -> None:
    """Escalation integrity's 30 is 30 warranted escalations, not 30 calls.

    Nothing computes from `counts` yet — it is B3's job to read it — but a
    config that flattened it away would leave an aggregation free to gate on
    a call count, which at batch-1 volume passes with 11 triggers behind it.
    """
    triggers = MetricThreshold(
        key="escalation_integrity",
        sheet_row="6",
        name="Escalation integrity",
        window_weeks=12,
        min_n=30,
        counts="triggers",
    )

    assert triggers.counts == "triggers"
    assert _metric().counts == "calls"


# --- Metric lookup ---------------------------------------------------------


def test_an_unknown_metric_raises_rather_than_defaulting() -> None:
    """A metric gated on a threshold nobody configured is a metric with no
    gate at all, so this must not fall back to a permissive default.
    """
    with pytest.raises(KeyError, match="contact_rate"):
        _config().metric("countact_rate")


def test_a_known_metric_is_returned() -> None:
    assert _config().metric("contact_rate").min_n == 30


# --- Peer size bands -------------------------------------------------------


@pytest.mark.parametrize(
    ("lives", "label"),
    [(2, "2-24 lives"), (24, "2-24 lives"), (25, "25-74 lives"), (74, "25-74 lives")],
)
def test_size_bands_are_inclusive_at_both_ends(lives: int, label: str) -> None:
    band = _config().size_band_for(lives)

    assert band is not None
    assert band.label == label


def test_the_top_band_is_open_ended() -> None:
    band = _config().size_band_for(20_000)

    assert band is not None
    assert band.label == "200+ lives"


def test_an_employer_below_the_first_band_has_no_peers() -> None:
    """None is an answer, not a failure. A group of one is not a group, and
    an employer with no peer set has nothing to be compared against — which
    the account page has to say rather than showing a bare rate.
    """
    assert _config().size_band_for(1) is None


def test_size_bands_are_not_the_fee_bands() -> None:
    """Rule P-33 bands the fee at 2-8 / 9-20 / 21-199 / 200+ *eligible
    employees*. These are 2-24 / 25-74 / ... *enrolled lives*. A 22-life
    group lands in the first peer band and the third fee band, and reading
    one for the other compares it against the wrong median silently.
    """
    from domain.reference_derivations import fee_band

    band = _config().size_band_for(22)

    assert band is not None
    assert band.label == "2-24 lives"
    assert fee_band(22) == 35


# --- Broker views ----------------------------------------------------------


@pytest.mark.parametrize(
    ("mentions", "employers", "fires"),
    [
        (3, 2, True),
        (2, 2, False),  # a bad week, not a pattern
        (3, 1, False),  # one disgruntled client
        (9, 1, False),  # still one client, however loud
        (4, 3, True),
    ],
)
def test_the_pattern_test_needs_both_counts(mentions: int, employers: int, fires: bool) -> None:
    assert _config().broker_pattern_test.fires(mentions, employers) is fires


@pytest.mark.parametrize(("lives", "ranked"), [(149, False), (150, True), (151, True)])
def test_no_book_under_the_floor_is_ranked(lives: int, ranked: bool) -> None:
    assert _config().ranks_broker(lives) is ranked


# --- Quality bands ---------------------------------------------------------


@pytest.mark.parametrize(
    ("score", "band"),
    [
        (100, QualityBand.GOOD),
        (86, QualityBand.GOOD),
        (85, QualityBand.AVERAGE),
        (60, QualityBand.AVERAGE),
        (59, QualityBand.POOR),
        (0, QualityBand.POOR),
    ],
)
def test_quality_bands_match_the_workbook_boundaries(score: int, band: QualityBand) -> None:
    assert _config().quality_bands.band_for(score) is band


# --- Risk flag (D2) --------------------------------------------------------


@pytest.mark.parametrize(("calls", "eligible"), [(0, False), (2, False), (3, True), (10, True)])
def test_eligibility_starts_at_three_calls(calls: int, eligible: bool) -> None:
    assert _config().risk_flag.eligible(calls) is eligible


@pytest.mark.parametrize(("met", "flagged"), [(0, False), (1, False), (2, True), (4, True)])
def test_the_flag_needs_two_of_the_four_conditions(met: int, flagged: bool) -> None:
    assert _config().risk_flag.flagged(met) is flagged


@pytest.mark.parametrize(("calls", "quotable"), [(9, False), (10, True)])
def test_quoting_needs_ten_calls(calls: int, quotable: bool) -> None:
    assert _config().risk_flag.quotable(calls) is quotable


def test_eligible_but_not_quotable_is_a_real_state() -> None:
    """The gap between 3 and 10 is the whole reason these are two numbers.

    An employer in it is assessed and may be flagged, but the flag may not be
    quoted as a figure. Collapsing them either suppresses the assessment or
    publishes a rate from four calls.
    """
    flag = _config().risk_flag

    assert flag.eligible(4) is True
    assert flag.quotable(4) is False


def test_an_ineligible_employer_is_not_the_same_as_an_unflagged_one() -> None:
    """At batch-1 volume most of the 92 employers with calls have exactly
    one, so most of the page is ineligible rather than reassuring. Nothing
    in this object lets a caller read "not eligible" as "not at risk" — that
    is why `eligible` is asked separately from `flagged`.
    """
    flag = _config().risk_flag

    assert flag.eligible(1) is False
    # ...and the flag itself has no opinion about a single-call employer,
    # because it is never asked.
    assert flag.flagged(2) is True


# --- Money (D4) ------------------------------------------------------------


def test_money_is_withheld_while_cost_per_call_is_unknown() -> None:
    assert _config().money_withheld is True


def test_money_is_published_once_finance_sets_a_number() -> None:
    assert _config(cost=4.75).money_withheld is False
