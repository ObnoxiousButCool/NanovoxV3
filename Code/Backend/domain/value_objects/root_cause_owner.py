"""Call Tag Schema field 17 (v10) — who could have prevented this call.

Populated on every call, not only where a complaint exists — the sheet's
own note: "a third of calls carried no owner at all" was the gap this
field closes. `MEMBER_MISUNDERSTANDING` is the fallback when nothing else
attributes the call: the member was not wrong to ring, they were not told.

Four of the seven values are exactly `ComplaintAttribution`'s own names
(`CHOICE`, `BROKER`, `CARRIER`, `PROVIDER`) — deliberately: a complaint's
attribution, when one exists, *is* the root cause, not a different
opinion about it. See `domain/derivations/root_cause.py`.
"""

from __future__ import annotations

from enum import StrEnum


class RootCauseOwner(StrEnum):
    CHOICE = "CHOICE"
    BROKER = "BROKER"
    CARRIER = "CARRIER"
    PROVIDER = "PROVIDER"
    EMPLOYER = "EMPLOYER"
    SYSTEM = "SYSTEM"
    MEMBER_MISUNDERSTANDING = "MEMBER_MISUNDERSTANDING"
