"""Call Tag Schema field 15, new in v8.

"A structural improvement proposed or implied inside a call." Distinct from
the `process_breakdown` signal, which means something *failed*; a gap means
something is missing or unclear by design. Conflating them turns a backlog
of fixable documents into a list of incidents.

The status is the point. The sheet: "a tag without a lifecycle is a note
nobody reads." Seven calls proposing the same change to the same document is
a prioritised backlog item with evidence and cost attached, which is why
aggregation is by touchpoint and proposed change rather than by call.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ProcessGapStatus(str, Enum):
    UNVALIDATED = "UNVALIDATED"
    VALIDATED = "VALIDATED"
    ACTIONED = "ACTIONED"
    REJECTED = "REJECTED"


class RaisedBy(str, Enum):
    AGENT = "AGENT"
    CALLER = "CALLER"


@dataclass(frozen=True)
class ProcessGap:
    present: bool
    gap_type: str | None = None
    #: Where the gap originated, not where it surfaced — a touchpoint
    #: reference from the Touchpoints sheet. A gap with no touchpoint cannot
    #: be routed to the person who controls the content, which is the only
    #: thing that makes it actionable outside the call centre.
    touchpoint: str | None = None
    proposed_change: str | None = None
    raised_by: RaisedBy | None = None
    status: ProcessGapStatus | None = None

    def __post_init__(self) -> None:
        if self.present and self.status is None:
            raise ValueError(
                "A process gap must carry a status — a tag without a lifecycle is a note."
            )
        if not self.present and any(
            field is not None
            for field in (
                self.gap_type,
                self.touchpoint,
                self.proposed_change,
                self.raised_by,
                self.status,
            )
        ):
            raise ValueError("An absent process gap must not carry any of its other fields.")
