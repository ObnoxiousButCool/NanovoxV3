"""The category carrying the most unresolved calls, and how its escalations fared.

`exec.html`'s "Area of concern" box names one call topic by two counts that
are already computed elsewhere on this screen — unresolved outcome
(`distributions.py`'s `OutcomeCount`) and escalation triggered/handled
(`exec_scorecard.py`) — but nothing before this module ties them to one
**category** rather than to the whole book. That is the one piece
"What went well / Area of concern" needed that `trends.movements` cannot
already answer: a movement is one measure across every call, and this is the
same two measures broken out by the category driving them.

## Counts, not shares, matching `Emerging`

A *rate* is gated by the Signal Taxonomy sheet's five-call floor; a *count*
of unresolved calls has no such floor, the same reasoning as
`distributions.py`'s `OutcomeCount` and `trends.emerging`. Two unresolved
calls in a rare category is a fact worth naming, and suppressing it below
some invented minimum would be inventing a floor nobody asked for.

## `None` rather than a manufactured finding

A book with no unresolved calls anywhere has no area of concern to name.
Picking a category anyway — the one with the most calls, say — would be the
same mistake `trends.movement` exists to prevent: reporting a "worst"
category when nothing here is actually bad.

## Ties break on the unhandled escalation gap, not on the category name

`exec.html`'s own tie-break is most unresolved first, then the widest gap
between escalations triggered and handled. Sorting on unresolved count alone
would let a category with a clean escalation record crowd out, on a tied
unresolved count, one where callers who asked for a supervisor did not get
one — the more serious fact of the two.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from domain.aggregation.call_tags import CallContext
from domain.value_objects.outcome import Outcome


@dataclass(frozen=True)
class CategoryConcern:
    """One call topic, and the two counts that make it the period's concern."""

    category: str
    calls: int
    unresolved: int
    escalations_triggered: int
    escalations_handled: int


def _concern_for(category: str, entries: Sequence[CallContext]) -> CategoryConcern:
    unresolved = len([call for call in entries if call.tags.outcome is Outcome.UNRESOLVED])
    triggered = [
        call
        for call in entries
        if call.tags.escalation is not None and call.tags.escalation.triggered
    ]
    handled = [call for call in triggered if call.tags.escalation and call.tags.escalation.handled]
    return CategoryConcern(
        category=category,
        calls=len(entries),
        unresolved=unresolved,
        escalations_triggered=len(triggered),
        escalations_handled=len(handled),
    )


def worst_category(calls: Sequence[CallContext]) -> CategoryConcern | None:
    """The category with the most unresolved calls, or `None` if none had any.

    Sorted by unresolved count, then by the gap between escalations
    triggered and handled in that category, then by name for a stable order
    between requests when both counts tie.
    """
    by_category: dict[str, list[CallContext]] = {}
    for call in calls:
        if call.tags.category is not None:
            by_category.setdefault(call.tags.category.value, []).append(call)

    candidates = [
        concern
        for category, entries in by_category.items()
        if (concern := _concern_for(category, entries)).unresolved > 0
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda c: (
            -c.unresolved,
            -(c.escalations_triggered - c.escalations_handled),
            c.category,
        ),
    )
