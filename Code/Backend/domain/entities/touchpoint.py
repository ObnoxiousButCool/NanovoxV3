"""A point in the member/employer journey where a failure can originate.

Touchpoints sheet (12 rows). "Where a failure originated, as distinct from
where it surfaced" — a member confused about a waiting period surfaced the
problem on a call, but the failure happened at the enrolment meeting, in the
enrolment material, or in a denial letter.

Referenced directly by `touchpoint` (Call Tag Schema field 16) and by
`process_gap.touchpoint` (field 15). `owner` is the team insight 16
(touchpoint defect ranking) and insight 23 (rules we fail to explain) group
by; `controls` names who actually owns the content at that touchpoint (the
broker, Choice, or the carrier) — distinct from `owner`, which is the
internal team accountable for fixing it.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Touchpoint:
    """Reference is the business key, e.g. ``enrolment_meeting``."""

    reference: str
    owner: str
    controls: str
