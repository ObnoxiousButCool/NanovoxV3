"""A broker of record.

Broker Master sheet. An employer has exactly one broker of record
(`Employer.broker_ref`); a broker has many employers. Book size
(`groups_in_book`) comes from this record, never from call counts — deriving
it from calls would make broker-book rates self-referential (Broker Master
sheet's own note, echoed in Metrics sheet metric 2's build note).

Referenced by `broker_named_aloud.broker_ref` (Call Tag Schema field 14),
joined through `Employer.broker_ref` per the Data Model sheet's join path:
Call → Member/Contact → Employer → Broker.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Broker:
    """Reference is the business key, e.g. ``BRK-12``."""

    reference: str
    name: str
    agency: str
    region: str
    groups_in_book: int
    signal_profile: str
