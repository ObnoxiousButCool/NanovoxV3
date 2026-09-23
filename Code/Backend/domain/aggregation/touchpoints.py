"""Groups 8 and 9 — touchpoint defect ranking, and the enrolment promise gap.

The touchpoint is where a failure *originated*, not where it surfaced. The
Touchpoints sheet: a member who does not understand a waiting period
surfaced it on a call, but the failure happened at the enrolment meeting, in
the enrolment material, or in a denial letter that said "ineligible" and
stopped. Tagging it is what turns a pile of calls into a ranked list of
documents to fix, actionable by someone who does not run the call centre.

## Group 8 — ranking, coloured by attribution

§9 insight 16: "Calls per touchpoint with owner team — unchanged,
`touchpoint` is a real single-valued field. Extension: coloured by
`complaint.attributed_to` where present (4 real values), **not** a 'dominant
party' model that assumes fault records."

The distinction is the point. A dominant-party model would pick one party
per touchpoint and label it; that needs per-fault records, which §7A
established do not exist in v9 and are the change `Insights-Worth-Building`
is *proposing*. So the split is published as a split — four counts a reader
can see — and nothing collapses it into a winner.

## Group 9 — the enrolment promise gap

Process gaps whose touchpoint is one of the enrolment moments: what we said
would happen at enrolment against what the member then met. Built from
`process_gap` plus `touchpoint`, which are the two fields v8 added and the
only two that can answer it.

## The unattributed bucket (insight 18)

§9 asks, of insight 18, to "check in Phase 6 that this doesn't just
duplicate insight 16's residual bucket before giving it a separate panel."
Checked: it does. `unattributed` below is insight 16's own residual — calls
whose touchpoint carries no clear upstream artefact — and a second panel
over the same set would be the same number twice under two headings. It is
exposed here as a field on the ranking rather than as its own aggregation,
and insight 18 needs no separate function.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from domain.aggregation.call_tags import CallContext, Window
from domain.value_objects.complaint_attribution import ComplaintAttribution

#: The touchpoints at which an enrolment promise is made. From the
#: Touchpoints sheet's own rows, whose "typical failures" for these three
#: are waiting periods denied, the employer/carrier waiting-period
#: distinction never drawn, and the waiver section left incomplete.
ENROLMENT_TOUCHPOINTS = ("enrolment_meeting", "enrolment_material", "enrolment_form")

#: What a call with no touchpoint tagged is filed under. Named rather than
#: dropped: calls with no upstream artefact at fault are a real and
#: interesting residual, and silently excluding them would make every
#: touchpoint's share of the total wrong.
UNATTRIBUTED = "unattributed"


@dataclass(frozen=True)
class TouchpointRow:
    """One touchpoint's calls, split by who the complaint was attributed to."""

    touchpoint: str
    call_ids: tuple[str, ...]
    #: Counts per attribution value, for the calls here that carry a
    #: complaint. Published as a split, never reduced to a dominant party.
    attribution: tuple[tuple[ComplaintAttribution, int], ...]
    #: Calls at this touchpoint with no complaint tagged at all. Not the
    #: same as a complaint with no attribution — the schema makes
    #: attribution mandatory whenever a complaint is present, so that second
    #: thing should not exist and is not modelled.
    without_complaint: int

    @property
    def calls(self) -> int:
        return len(self.call_ids)


def touchpoint_ranking(calls: Sequence[CallContext], window: Window) -> tuple[TouchpointRow, ...]:
    """Every touchpoint in the window, busiest first.

    Counts, not rates. There is no per-touchpoint population to divide by —
    the denominator would have to be "calls that could have originated
    here", which nothing records.
    """
    grouped: dict[str, list[CallContext]] = {}
    for call in window.calls_in(tuple(calls)):
        grouped.setdefault(call.tags.touchpoint or UNATTRIBUTED, []).append(call)

    rows = [
        TouchpointRow(
            touchpoint=touchpoint,
            call_ids=tuple(sorted(call.reference for call in group)),
            attribution=_attribution_split(group),
            without_complaint=sum(
                1
                for call in group
                if call.tags.complaint is None or not call.tags.complaint.present
            ),
        )
        for touchpoint, group in grouped.items()
    ]
    return tuple(sorted(rows, key=lambda row: (-row.calls, row.touchpoint)))


def unattributed_calls(ranking: Sequence[TouchpointRow]) -> tuple[str, ...]:
    """Insight 16's residual bucket, which insight 18 turned out to duplicate.

    See this module's docstring: kept as an accessor over the ranking rather
    than as a second aggregation, so the two insights cannot drift into
    reporting different numbers for the same set of calls.
    """
    for row in ranking:
        if row.touchpoint == UNATTRIBUTED:
            return row.call_ids
    return ()


@dataclass(frozen=True)
class PromiseGap:
    """One proposed change, and every call that proposed it.

    Aggregated by touchpoint and proposed change, exactly as schema field 15
    asks: "seven calls proposing the same change to the same document is a
    prioritised backlog item with evidence and cost attached."
    """

    touchpoint: str
    proposed_change: str
    call_ids: tuple[str, ...]
    #: Minutes of talk time across those calls — the "cost attached" half.
    #: A floor, because AHT excludes hold and after-call work.
    minutes: float

    @property
    def calls(self) -> int:
        return len(self.call_ids)


def enrolment_promise_gaps(
    calls: Sequence[CallContext],
    window: Window,
    *,
    touchpoints: Sequence[str] = ENROLMENT_TOUCHPOINTS,
) -> tuple[PromiseGap, ...]:
    """Process gaps raised at the enrolment touchpoints, most-proposed first.

    Grouped on the exact proposed change. Two callers proposing the same fix
    in different words will not group, and nothing here tries to cluster
    them — that would be a judgement about meaning, made silently, inside a
    function whose output is a prioritised backlog. Where the corpus repeats
    a proposal verbatim it groups; where it does not, a reader sees two rows
    and can decide they are one.
    """
    grouped: dict[tuple[str, str], list[CallContext]] = {}
    for call in window.calls_in(tuple(calls)):
        gap = call.tags.process_gap
        if gap is None or not gap.present or gap.touchpoint not in touchpoints:
            continue
        grouped.setdefault((gap.touchpoint or "", gap.proposed_change or ""), []).append(call)

    rows = [
        PromiseGap(
            touchpoint=touchpoint,
            proposed_change=change,
            call_ids=tuple(sorted(call.reference for call in group)),
            minutes=round(sum(call.tags.aht_seconds or 0 for call in group) / 60, 1),
        )
        for (touchpoint, change), group in grouped.items()
    ]
    return tuple(sorted(rows, key=lambda row: (-row.calls, row.touchpoint, row.proposed_change)))


def _attribution_split(
    calls: Sequence[CallContext],
) -> tuple[tuple[ComplaintAttribution, int], ...]:
    counts = dict.fromkeys(ComplaintAttribution, 0)
    for call in calls:
        complaint = call.tags.complaint
        if complaint is not None and complaint.present and complaint.attributed_to is not None:
            counts[complaint.attributed_to] += 1
    return tuple((attribution, counts[attribution]) for attribution in ComplaintAttribution)
