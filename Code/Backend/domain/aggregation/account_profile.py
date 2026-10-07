"""What one account's own calls say, as counts rather than rates.

The tiles and the topic ranking on `Prototype/v2/employer.html`. Everything
here is a **count of things that happened**, which is why none of it carries
a minimum sample: `domain/aggregation/distributions.py` sets out the rule —
"Counts have no minimum, shares do" — and zero unresolved calls out of four
is a true and useful statement where a zero *rate* over four calls is not.

## The prototype's fifth tile is not here, and cannot be

`employer.html` shows **Average call quality** per account. This module does
not, and no amount of asking will make it: `agent_quality` in
`domain/aggregation/agent_events.py` states the constraint plainly —

    Per agent only. Rolling this up to an employer, a product line or a
    broker is forbidden by the Metrics sheet, and there is no function here
    that would let a caller do it by accident.

An account-level average is exactly that rollup. `Documents/notes/plan.md` §3.0 gives the
prototype the presentation authority and the workbook the definitions, and
this is a definition. Recorded as a conflict rather than quietly built.

What the sheet forbids is a **summary statistic over an employer**, not the
score itself: metric 12 is admissible as a property of the call, and every
one of this account's scores is already printed beside its call. So what is
counted here is `scored_calls` — how many of the account's calls carry a
score at all. That is coverage, not quality: it says how much of the window
the per-call scores cover, and it is the honest thing to put where the
prototype puts a mean. A count of calls below some threshold is *not* here,
because picking the threshold is the rollup again in different clothes.

## Nor a quality range, and this one was measured rather than argued

The obvious next proposal is a *range* — lowest and highest scored call —
on the grounds that `agent_quality` publishes exactly that per agent, and a
range is not an average, so the sheet's wording does not reach it. Measured
against this corpus on 2026-09-28, the range carries no information about an
account at all:

- **The high end is a constant.** 67% of the 238 scored calls score exactly
  100. Of the 16 accounts with three or more scored calls, **all 16** have a
  maximum of 100, and 100 is the only distinct maximum in the book. An
  account with three calls reaches it by luck 96% of the time.
- **The low end is sample size.** Correlation between an account's call
  count and its observed range is 0.67. Comparing each account against 4,000
  random draws of the same size from the book-wide pool, **every account's
  range falls inside the 5th-95th percentile of the random draw.** Not one
  is distinguishable from calls dealt at random.
- **59 accounts have one scored call**, where the range is zero by
  construction and would render as a single number that looks like a
  measurement and is a sample of one.

So a reader comparing "62-100" with "78-100" would be reading the difference
between sixteen calls and eighteen. The sheet's prohibition and the
statistics agree here, which is the usual sign that the sheet already knew.
The median does not rescue it either — the book-wide median is 100.

This closes the question rather than leaving it open for a person: it is not
a presentation disagreement to be settled by Minnie or Karim, it is a figure
that would vary only with call volume while looking like a judgement about
an account. What the page shows instead is the per-call scores in the calls
panel, where a 62 stays attached to the one call that earned it.

## Topics are what they called about, not which categories exist

The ranking lists only the categories this account actually raised, in
descending order. That is different from `outcome_counts`, which deliberately
includes zeros because "no escalations at all" is a finding. Here it is not:
an account that never asked about Life & Beneficiary has not told us
anything, and seven near-empty bars would bury the two that matter.

What the ranking *must* not do is lose a call. A call with no category is
counted in `uncategorised` rather than dropped, so the bars plus that number
always reconcile with the account's call count.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from domain.aggregation.call_tags import CallContext, Window
from domain.aggregation.repeat_contact import failure_driven_repeats
from domain.value_objects.category import Category
from domain.value_objects.outcome import Outcome


@dataclass(frozen=True)
class TopicCount:
    """One category this account called about, and how often."""

    category: Category
    calls: int


@dataclass(frozen=True)
class AccountProfile:
    """One account's own calls in the window, counted."""

    calls: int
    unresolved: int
    #: Metric 4's own numerator, restricted to this account — so the tile
    #: cannot disagree with the repeat-rate figure beside it.
    repeat_contacts: int
    escalations_missed: int
    #: Calls whose category the pipeline never filled. Present so the topic
    #: bars can be reconciled against `calls` rather than silently falling
    #: short of it.
    uncategorised: int
    #: How many of `calls` carry a quality score. Coverage of the per-call
    #: figure, never a summary of it — see the module docstring.
    scored_calls: int
    topics: tuple[TopicCount, ...]


def account_profile(calls: Sequence[CallContext], window: Window) -> AccountProfile:
    """Count one account's calls. `calls` must already be that account's."""
    mine = window.calls_in(tuple(calls))

    tally: dict[Category, int] = {}
    uncategorised = 0
    for call in mine:
        category = call.tags.category
        if category is None:
            uncategorised += 1
        else:
            tally[category] = tally.get(category, 0) + 1

    return AccountProfile(
        calls=len(mine),
        unresolved=len([call for call in mine if call.tags.outcome is Outcome.UNRESOLVED]),
        repeat_contacts=len(failure_driven_repeats(mine)),
        # `Escalation.missed` is warranted-and-not-handled, over the same
        # denominator escalation integrity uses. A call with no escalation
        # recorded is in neither, which is why this reads the object rather
        # than two loose booleans.
        escalations_missed=len(
            [
                call
                for call in mine
                if call.tags.escalation is not None and call.tags.escalation.missed
            ]
        ),
        uncategorised=uncategorised,
        scored_calls=len([call for call in mine if call.tags.quality_score is not None]),
        # Most first, then the workbook's own order for a tie, so two
        # categories on the same count do not swap places between reads.
        topics=tuple(
            TopicCount(category=category, calls=count)
            for category, count in sorted(
                tally.items(), key=lambda entry: (-entry[1], list(Category).index(entry[0]))
            )
        ),
    )
