"""Employer figures the workbook stores as formulas with no cached value.

The source workbook is written by a tool that never evaluates formulas, so
roughly 1,500 cells — including every one of these — read as empty
(Employer Master sheet; ported from the prototype's `03_join_corpus.py`,
which discovered and documented this). Nothing here reads a workbook cell
for these fields; they are computed from `Eligible employees` and
`Enrolled lives`, which are real, plus rule P-33 for the fee band.

Every function cites the Metrics sheet or rule it implements. Pure,
deterministic, no I/O — called once at import time by
`infrastructure/reference/xlsx_reference_source.py` and stored on the
`Employer` entity, not recomputed on every read (plan §2A.2: no magic
numbers, cite the bible).
"""

from __future__ import annotations

# Rule P-33: the administration fee steps by headcount, never by service
# consumed. Bands and dollar amounts as published.
_FEE_BANDS: tuple[tuple[int, int], ...] = (
    (8, 25),
    (20, 30),
    (199, 35),
)
_FEE_BAND_DEFAULT = 50

# The COBRA regime boundary (README sheet, rule P-33's COBRA note): below 20
# eligible employees a group is under Cal-COBRA and ChoiceBuilder sends the
# election notice; at 20 and above it is federal COBRA and the duty is
# solely the employer's.
_CAL_COBRA_MAX_ELIGIBLE = 19
CAL_COBRA = "Cal-COBRA"
FEDERAL_COBRA = "Federal COBRA"

_MONTHS_PER_YEAR = 12
_PER_100 = 100


def fee_band(eligible: int) -> int:
    """The monthly administration fee, by rule P-33: $25 (2-8), $30 (9-20),
    $35 (21-199), $50 (200+) eligible employees.
    """
    for ceiling, fee in _FEE_BANDS:
        if eligible <= ceiling:
            return fee
    return _FEE_BAND_DEFAULT


def cobra_regime(eligible: int) -> str:
    """Cal-COBRA below 20 eligible employees, federal COBRA at 20 and above."""
    return CAL_COBRA if eligible <= _CAL_COBRA_MAX_ELIGIBLE else FEDERAL_COBRA


def participation(enrolled: int, eligible: int) -> float | None:
    """Enrolled ÷ eligible. `None` when eligible is zero — not a divide error."""
    if not eligible:
        return None
    return round(enrolled / eligible, 4)


def annual_fee(eligible: int) -> int:
    """The monthly fee band (rule P-33), annualised."""
    return fee_band(eligible) * _MONTHS_PER_YEAR


def annual_premium(enrolled: int, premium_per_life: float | None) -> float | None:
    """Enrolled lives x the per-life premium lever from Distribution Targets.

    Flat by design (Distribution Targets sheet, "Annual premium per enrolled
    life ($)"): premium per account is headcount in different units — good
    for a board total, not for ranking two accounts of the same size. `None`
    when the lever wasn't found or there are no enrolled lives, never a
    silent zero.
    """
    if not premium_per_life or not enrolled:
        return None
    return round(enrolled * premium_per_life)


def calls_per_100(planned_calls: int, enrolled: int) -> float | None:
    """Planned calls ÷ enrolled lives x 100. `None` when enrolled is zero."""
    if not enrolled:
        return None
    return round(planned_calls / enrolled * _PER_100, 2)
