"""An employer-side caller — an HR, finance or owner contact, not the group itself.

Employer Contacts sheet. Like `Member`, carries no broker field of its own;
broker of record is inherited through `Employer.broker_ref`.

Referenced by `caller_ref` (Call Tag Schema field 13) when the caller is a
contact: `CON-nnn`. `authority` decides what an agent may action without a
second approval, and gates insight 3 — exit or market-test intent only
counts toward the exit family from a `CAN_BIND` contact; a `CANNOT_BIND`
contact's exit language is shown, not counted.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.value_objects.authority import Authority


@dataclass(frozen=True)
class EmployerContact:
    """Reference is the business key, e.g. ``CON-101``."""

    reference: str
    name: str
    role: str
    authority: Authority
    employer_ref: str
    planned_calls: int
