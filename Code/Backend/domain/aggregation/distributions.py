"""How calls ended, and how that shape moved week by week.

The v2 risk page carries three panels this serves: "Calls each week",
"Resolved and good-quality calls", and the outcome half of "How calls
ended". They answer a question the account list cannot — whether the book
is getting better or worse — and they do it in shape rather than level.

## Counts have no minimum, shares do

Call volume is a count of things that happened, so zero is a real answer
and no floor applies. A *share* of those calls is a rate, and at about
eight calls a week a rate moves two points per call.

The floor is **five calls**, which is the prototype's own and is written
down there: *"Weeks with fewer than five calls are left blank rather than
shown as a swing."* The same five-call floor is already used by the
indicator families. Borrowed, not invented.

## The two kinds of nothing

`WeekShare` carries both, and they are different fields on purpose:

- `calls is None` — the corpus is silent about that week. No calls at all.
- `share is None` — calls happened, but too few to publish a rate.

A chart draws the first as a gap in the line and the second as a gap in
the share while still showing the count. Collapsing them into one null
would make "we had a quiet week" and "we had a week we cannot describe"
render identically.

## The handling distribution is not here

The prototype's "How calls ended" has two halves: Outcome and Handling.
Handling is `archetype`, which is **not one of the sixteen schema fields**
and has no workbook source — conflict **C8a**. Building it would mean
inventing the definition §2A.4 forbids, so this module serves the outcome
half and the screen says the other is missing rather than showing an empty
chart beside a full one.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from domain.aggregation.call_tags import CallContext, Window
from domain.aggregation.trends import weeks_in
from domain.dashboard_config import QualityBands
from domain.value_objects.outcome import Outcome
from domain.value_objects.quality_band import QualityBand

#: Below this a week's share is withheld. The prototype's own floor.
SHARE_MIN_CALLS = 5

Measure = Callable[[CallContext], bool]


@dataclass(frozen=True)
class OutcomeCount:
    """One outcome and how many calls ended that way."""

    outcome: Outcome
    calls: int


def outcome_counts(calls: Sequence[CallContext]) -> tuple[OutcomeCount, ...]:
    """Every outcome, **including the ones at zero**.

    In the workbook's order rather than by size: a bar chart whose
    categories reorder as the data moves is one a reader cannot compare
    against last week's. Outcomes with no calls are kept because their
    absence is a finding — no escalations at all is worth seeing, and a
    chart that silently dropped the category would not show it.

    A call with no outcome recorded is counted in neither: it is not a
    fifth outcome and it is not a resolved call.
    """
    tally = dict.fromkeys(Outcome, 0)
    for call in calls:
        if call.tags.outcome is not None:
            tally[call.tags.outcome] += 1
    return tuple(OutcomeCount(outcome=outcome, calls=count) for outcome, count in tally.items())


@dataclass(frozen=True)
class WeekShare:
    """One week's count, and a share of it where there is enough to say."""

    start: str
    end: str
    #: `None` when the corpus is silent about the week — no calls at all.
    calls: int | None
    #: How many of them matched. `None` for a silent week, never zero for
    #: one, because "no calls" and "no matches" are different facts.
    matched: int | None
    #: `matched / calls`, or `None` when the week is below the floor. A
    #: week with four calls has a share; it does not have a publishable
    #: one, and showing it would be a swing invented from one call.
    share: float | None


def weekly_shares(
    calls: Sequence[CallContext], window: Window, measure: Measure
) -> tuple[WeekShare, ...]:
    """A share per week, withheld where the week is too small to carry one."""
    weeks: list[WeekShare] = []
    for week in weeks_in(window):
        in_week = week.calls_in(tuple(calls))
        if not in_week:
            weeks.append(
                WeekShare(
                    start=week.start.isoformat(),
                    end=week.end.isoformat(),
                    calls=None,
                    matched=None,
                    share=None,
                )
            )
            continue
        matched = len([call for call in in_week if measure(call)])
        weeks.append(
            WeekShare(
                start=week.start.isoformat(),
                end=week.end.isoformat(),
                calls=len(in_week),
                matched=matched,
                share=(matched / len(in_week)) if len(in_week) >= SHARE_MIN_CALLS else None,
            )
        )
    return tuple(weeks)


def resolved(call: CallContext) -> bool:
    """Resolved on the first contact, as the outcome records it."""
    return call.tags.outcome is Outcome.RESOLVED


def unresolved(call: CallContext) -> bool:
    return call.tags.outcome is Outcome.UNRESOLVED


def good_quality(bands: QualityBands) -> Measure:
    """A call the Call Quality Framework grades GOOD.

    Takes the bands rather than hard-coding 86: the threshold is a workbook
    value (`QualityBands.good_min`), and a copy of it here would be a second
    definition that stops agreeing with the sheet the day it moves.

    A call with **no score recorded** is not good quality and is not poor
    quality — it is unscored. It counts in the week's denominator, because
    it is a call that happened, and not in the numerator, because nobody
    graded it. That makes the share a floor rather than an estimate, which
    is the same direction every other partial figure here leans.
    """

    def measure(call: CallContext) -> bool:
        score = call.tags.quality_score
        return score is not None and bands.band_for(score) is QualityBand.GOOD

    return measure
