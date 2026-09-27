"""Call Tag Schema field 18 (v10) — a pure function of `root_cause_owner`.

CHOICE and SYSTEM are Yes; PROVIDER is No; the rest (BROKER, CARRIER,
EMPLOYER, MEMBER_MISUNDERSTANDING) are Partly, each with its own lever
named in the workbook ("Partly — communication", "Partly — broker
enablement", …). The lever text is not stored here: it is fully
determined by `root_cause_owner` and would be a second copy of the same
fact, not new information. Report the three buckets separately — the
sheet's own words: "a blended percentage invites an argument about the
middle."

See `domain/derivations/root_cause.py` for the mapping.
"""

from __future__ import annotations

from enum import Enum


class Preventable(str, Enum):
    YES = "Yes"
    PARTLY = "Partly"
    NO = "No"
