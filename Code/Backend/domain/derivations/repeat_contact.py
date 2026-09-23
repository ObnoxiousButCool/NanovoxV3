"""Failure-driven repeat contact (Metrics sheet metric 4).

"UNRESOLVED calls followed by a contact from the same caller <=14 days" —
computed from our own extracted `outcome` (L2) and Phase 2's own
`caller_ref`/`occurred_at`, never from the Transcript Tracker's "Repeat
of" column. That column is ground truth Stream B's answer key owns; using
it here would both violate the "extraction cannot read the answer key"
contract in spirit and make the pipeline's own repeat-detection circular
— measuring agreement between a value and itself.

**Same category is deliberately not a condition.** The plan is explicit
that requiring a category match was this project's own earlier addition,
not the workbook's, and was dropped.

**The window's last 14 days give no exposure.** A call from that recent
has not had the full 14 days needed to prove or disprove a repeat yet, so
counting it either way would understate the rate. That exclusion is
relative to whatever reporting window is being measured, which is why
it's a separate function here rather than folded into
`failure_driven_repeats` — the aggregation is Stream B's, not a property
of the call alone.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

REPEAT_WINDOW = timedelta(days=14)


@dataclass(frozen=True)
class CallForRepeatContact:
    """The three facts metric 4's test needs, and nothing else."""

    reference: str
    caller_ref: str
    occurred_at: datetime
    is_unresolved: bool


def failure_driven_repeats(calls: Sequence[CallForRepeatContact]) -> frozenset[str]:
    """References of every UNRESOLVED call a same-caller contact follows
    within 14 days."""
    by_caller: dict[str, list[CallForRepeatContact]] = defaultdict(list)
    for call in calls:
        by_caller[call.caller_ref].append(call)

    repeats: set[str] = set()
    for call in calls:
        if not call.is_unresolved:
            continue
        window_end = call.occurred_at + REPEAT_WINDOW
        for other in by_caller[call.caller_ref]:
            if other.reference == call.reference:
                continue
            if call.occurred_at < other.occurred_at <= window_end:
                repeats.add(call.reference)
                break

    return frozenset(repeats)


def has_full_exposure_window(occurred_at: datetime, window_end: datetime) -> bool:
    """Whether this call's 14-day repeat-contact window has fully elapsed
    by `window_end` — false for calls too recent to have had the chance
    to repeat yet."""
    return occurred_at + REPEAT_WINDOW <= window_end
