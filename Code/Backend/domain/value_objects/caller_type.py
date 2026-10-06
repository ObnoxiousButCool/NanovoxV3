"""Whether a call came from a member or an employer-side contact.

The transcript header's own field (legitimate input, §6.3) — distinct from
`caller_ref`'s format (`CB-` vs `CON-`), which implies the same thing but
is checked separately so a mismatch between the two is a resolution failure,
not a silent pick of one over the other.
"""

from __future__ import annotations

from enum import StrEnum


class CallerType(StrEnum):
    MEMBER = "MEMBER"
    EMPLOYER = "EMPLOYER"
