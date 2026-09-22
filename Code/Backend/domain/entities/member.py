"""A covered member (employee or dependent).

Member Master sheet. **Broker is deliberately absent** — the modelling rule
(README sheet, Data Model sheet): a member belongs to an employer, an
employer has exactly one broker of record, and the member never stores its
own copy, so a broker-of-record change corrects in one place and every
historical call re-attributes automatically. Reproducing that rule is the
point of this entity having no `broker_ref` field at all — not an oversight
to fill in later.

Referenced by `caller_ref` (Call Tag Schema field 13) when the caller is a
member: `CB-nnnnnnn`, resolved to this entity, then to `Employer`, then to
`Broker`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Member:
    """Reference is the business key, e.g. ``CB-7700205``."""

    reference: str
    name: str
    age: int
    employer_ref: str
    primary_line: str
    planned_calls: int
    repeat_caller: bool
