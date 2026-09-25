"""Which calls came back, and which of those came back because we failed.

Metric 4's linkage. Deterministic and model-free: a call is a repeat if the
same caller contacted us again inside the exposure period, which is a
comparison of two dates and a caller reference.

**Never read the tracker's "Repeat of" column.** The linkage is computed
from our own extracted `outcome` and Phase 2's `caller_ref`/`occurred_on`,
never from the Transcript Tracker. That column is answer-key material Stream
B's `ground_truth` owns, and using it here would both violate the
"extraction cannot read the answer key" contract in spirit and make the
pipeline's own repeat detection circular — Phase 5 would then be measuring
the agreement of a value with itself.

**Consolidated 2026-09-23.** Stream A's A4 and Stream B's B3 each built this, because
the two stream documents both claimed it — A4 as a deterministic derivation,
B3 because metric 5's first component is failure-driven repeats and
self-inflicted demand cannot be published without it. The two agreed on
every rule and differed only in types. This is the surviving one;
`domain/derivations/repeat_contact.py` is gone. Import this rather than
writing a third: two implementations of a 14-day boundary eventually
disagree on one day, and nothing says which is right.

Three definitions that are narrower than they look, all from the Metrics
sheet's own build notes:

- **The repeat need not be about the same thing.** "Same category" is not a
  workbook condition and was deliberately dropped. A member who calls about
  a denial and then about an ID card still called twice.
- **The denominator excludes the last 14 days of the window.** Those calls
  have not had an exposure period yet, so counting them drags every rate
  toward zero as the window's end approaches — and does it silently, because
  the shape of the trend does not change.
- **Repeat contact for any reason is not a quality signal.** The Metrics
  sheet dropped it as a metric precisely because it can rise when service
  improves. It survives here only as context inside metric 4, which is why
  `repeats()` is separate from `failure_driven_repeats()` and neither is
  published on its own.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta

from domain.aggregation.call_tags import CallContext, Window
from domain.aggregation.figure import Figure
from domain.aggregation.patterns import share
from domain.dashboard_config import DashboardConfig
from domain.value_objects.outcome import Outcome

#: The exposure period, from metric 3's numerator and metric 4's: a contact
#: from the same caller within fourteen days.
EXPOSURE_DAYS = 14


@dataclass(frozen=True)
class RepeatPair:
    """A call and the contact that followed it."""

    first: CallContext
    next_contact: CallContext

    @property
    def days_between(self) -> int:
        return (self.next_contact.occurred_on - self.first.occurred_on).days


def repeats(
    calls: Sequence[CallContext], *, within_days: int = EXPOSURE_DAYS
) -> tuple[RepeatPair, ...]:
    """Every call followed by another contact from the same caller.

    Context only. The Metrics sheet dropped repeat-contact-for-any-reason as
    a published metric because it can rise when service improves, so nothing
    should surface this as a rate of its own.

    A call with no `caller_ref` cannot be linked to anything and is skipped
    rather than guessed at — an unresolved caller is a known gap that the
    Phase 5 diagnostics count, not something to paper over here.
    """
    pairs: list[RepeatPair] = []
    for call in calls:
        follow_up = _first_follow_up(call, calls, within_days)
        if follow_up is not None:
            pairs.append(RepeatPair(first=call, next_contact=follow_up))
    return tuple(pairs)


def failure_driven_repeats(
    calls: Sequence[CallContext], *, within_days: int = EXPOSURE_DAYS
) -> tuple[CallContext, ...]:
    """Metric 4's numerator: UNRESOLVED calls the caller came back about.

    "When we fail to fix it, how often does the person come back." The
    outcome filter is what separates this from plain repeat contact, and it
    is the reason this one *is* a quality signal where the other is not.
    """
    return tuple(
        pair.first for pair in repeats(calls, within_days=within_days) if _unresolved(pair.first)
    )


def exposed_unresolved(
    calls: Sequence[CallContext], window: Window, *, within_days: int = EXPOSURE_DAYS
) -> tuple[CallContext, ...]:
    """Metric 4's denominator: UNRESOLVED calls that have had time to come back.

    The last `within_days` of the window are excluded. A call from yesterday
    has not had its fourteen days, and counting it as a non-repeat asserts
    something nobody knows yet.
    """
    cutoff = window.end - timedelta(days=within_days)
    return tuple(
        call
        for call in calls
        if _unresolved(call) and window.contains(call.occurred_on) and call.occurred_on <= cutoff
    )


def failure_driven_repeat_rate(
    config: DashboardConfig, calls: Sequence[CallContext], window: Window
) -> Figure:
    """Metric 4, over whichever calls are handed in.

    One function so the executive scorecard and an account page cannot
    produce different numbers for the same metric. The scorecard computed
    this inline until the account page needed it too, which is the moment a
    second definition usually appears — §9's own warning about a scorecard
    that recomputes its own versions of the screens it links to.

    The denominator is `exposed_unresolved`, not every unresolved call: a
    call from yesterday has not had its fourteen days to come back, and
    counting it as a non-repeat asserts something nobody knows yet.
    """
    exposed = exposed_unresolved(calls, window)
    returned = {call.reference for call in exposed}
    return share(
        config.metric("failure_driven_repeat_rate"),
        numerator=[call for call in failure_driven_repeats(calls) if call.reference in returned],
        denominator=exposed,
    )


def resolution_denominator(calls: Sequence[CallContext]) -> tuple[CallContext, ...]:
    """Metric 3's denominator: every call with a resolution outcome.

    "PARTIALLY_RESOLVED and ESCALATED sit in the denominator, not the
    numerator. One denominator across the whole platform." All four outcomes
    are resolution outcomes; a call with no outcome tagged is not yet
    classified and belongs in neither.
    """
    return tuple(call for call in calls if call.tags.outcome is not None)


def first_contact_resolutions(
    calls: Sequence[CallContext], *, within_days: int = EXPOSURE_DAYS
) -> tuple[CallContext, ...]:
    """Metric 3's numerator: RESOLVED, and nobody called back about it.

    Resolution alone is not first-contact resolution. A call marked RESOLVED
    that the same caller followed within fourteen days did not end the
    problem, whatever it was tagged.
    """
    came_back = {pair.first.reference for pair in repeats(calls, within_days=within_days)}
    return tuple(
        call
        for call in calls
        if call.tags.outcome is Outcome.RESOLVED and call.reference not in came_back
    )


def _unresolved(call: CallContext) -> bool:
    return call.tags.outcome is Outcome.UNRESOLVED


def _first_follow_up(
    call: CallContext, calls: Sequence[CallContext], within_days: int
) -> CallContext | None:
    caller = call.tags.caller_ref
    if caller is None:
        return None
    limit = call.occurred_on + timedelta(days=within_days)
    later = [
        other
        for other in calls
        if other.reference != call.reference
        and other.tags.caller_ref == caller
        and call.occurred_on < other.occurred_on <= limit
    ]
    return min(later, key=lambda other: (other.occurred_on, other.reference), default=None)


def repeat_references(
    corpus: Sequence[CallContext], *, within_days: int = EXPOSURE_DAYS
) -> frozenset[str]:
    """Calls that are themselves a follow-up, by reference.

    The *second* call of each pair, not the first. "Show me the repeat
    calls" means the ones where the caller had already been in touch — the
    earlier call was not a repeat when it happened.

    **Computed over the whole corpus, deliberately.** A repeat is a
    relationship between two calls, and the antecedent may not survive the
    filters: narrowing to one category would otherwise make a repeat stop
    being a repeat because the call it followed was filtered out. The
    caller therefore passes the corpus here and applies the result as a
    second stage over the filtered calls, which is the arrangement
    `filters.py` describes for every derived filter.
    """
    return frozenset(
        pair.next_contact.reference for pair in repeats(corpus, within_days=within_days)
    )
