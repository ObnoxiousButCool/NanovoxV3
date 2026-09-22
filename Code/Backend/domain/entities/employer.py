"""An employer group.

Employer Master sheet. The join point for everything (Data Model sheet):
Member and EmployerContact both reference an employer, and the employer
alone carries the broker of record — a member never stores a broker
(`Member` has no broker field; see that entity's docstring).

Referenced by `complaint`, `touchpoint`, `broker_named_aloud` and every other
per-call tag once a call is resolved to its caller's employer via
`caller_ref` (Call Tag Schema field 13) → Member/Contact → Employer.

Several fields are formulas in the source workbook with no cached value —
Eligible employees and Enrolled lives are real; `participation`, `fee_band`,
`cobra_regime`, `annual_fee`, `annual_premium` and `calls_per_100` are
**derived** here, by `domain/reference_derivations.py`, and stored as plain
columns rather than recomputed on every read — labelled derived wherever the
UI shows them (plan §2A.2), never confused with a workbook-supplied fact.

`design_churn_profile` is stored and must never be read by any calculation:
it is the label the corpus was *generated* from, and scoring an account on
it would be circular (plan principle 6; enforced by
`tests/unit/test_no_circular_scoring.py`).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Employer:
    """Reference is the business key, e.g. ``EMP-1001``."""

    reference: str
    name: str
    industry: str
    design_churn_profile: str
    eligible: int
    enrolled: int
    region: str
    renewal_month: str
    broker_ref: str
    dental_sponsorship: str
    lines_held: str
    planned_calls: int
    planned_member_calls: int
    planned_employer_calls: int

    # --- Derived (domain/reference_derivations.py); stored, never re-read
    # from the workbook because the workbook's own cells are empty formulas.
    participation: float | None
    fee_band: int
    annual_fee: int
    annual_premium: float | None
    cobra_regime: str
    calls_per_100: float | None
