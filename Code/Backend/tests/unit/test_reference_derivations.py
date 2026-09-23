"""Employer figures derived from eligible/enrolled headcount, not read from
the workbook (its own cells are empty formulas) — see
`domain/reference_derivations.py`'s module docstring and rule P-33.
"""

from __future__ import annotations

import pytest

from domain.reference_derivations import (
    CAL_COBRA,
    FEDERAL_COBRA,
    annual_fee,
    annual_premium,
    calls_per_100,
    cobra_regime,
    fee_band,
    participation,
)


@pytest.mark.parametrize(
    ("eligible", "expected"),
    [
        (2, 25),
        (8, 25),  # top of the 2-8 band
        (9, 30),  # bottom of the 9-20 band
        (20, 30),  # top of the 9-20 band
        (21, 35),  # bottom of the 21-199 band
        (199, 35),  # top of the 21-199 band
        (200, 50),  # bottom of the 200+ band
        (500, 50),
    ],
)
def test_fee_band_boundaries(eligible: int, expected: int) -> None:
    assert fee_band(eligible) == expected


@pytest.mark.parametrize(
    ("eligible", "expected"),
    [
        (2, CAL_COBRA),
        (19, CAL_COBRA),  # top of Cal-COBRA
        (20, FEDERAL_COBRA),  # bottom of federal COBRA
        (500, FEDERAL_COBRA),
    ],
)
def test_cobra_regime_boundary_at_20(eligible: int, expected: str) -> None:
    assert cobra_regime(eligible) == expected


def test_participation_is_enrolled_over_eligible() -> None:
    assert participation(315, 420) == pytest.approx(0.75)


def test_participation_is_none_when_eligible_is_zero() -> None:
    assert participation(0, 0) is None


def test_annual_fee_is_the_monthly_fee_band_times_twelve() -> None:
    assert annual_fee(420) == fee_band(420) * 12
    assert annual_fee(5) == 25 * 12


def test_annual_premium_multiplies_enrolled_by_the_lever() -> None:
    assert annual_premium(315, 486) == 153090


def test_annual_premium_is_none_without_a_lever() -> None:
    assert annual_premium(315, None) is None


def test_annual_premium_is_none_with_no_enrolled_lives() -> None:
    assert annual_premium(0, 486) is None


def test_calls_per_100_scales_planned_calls_to_the_enrolled_population() -> None:
    assert calls_per_100(36, 315) == pytest.approx(11.43, abs=0.01)


def test_calls_per_100_is_none_when_enrolled_is_zero() -> None:
    assert calls_per_100(10, 0) is None
