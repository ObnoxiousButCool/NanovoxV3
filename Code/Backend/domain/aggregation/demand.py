"""Group 6 — self-inflicted demand (metric 5) and its minutes view (metric 9).

"How much of our call volume we caused ourselves rather than the member
needing something new." Roughly one call in five, per the Intelligence
Register.

**The three components are published separately and never blended.** That is
the Metrics sheet's own build note — "Publish the three components
separately so a reader can dispute one without discarding the total" — and
it is the reason this module returns a `SelfInflictedDemand` with four
figures rather than one number. An executive who disputes the process-defect
component can discard it and keep the other two; given one blended figure
they discard all of it.

Distinct calls are the unit, not records. A call that is both a
failure-driven repeat and carries a process gap is one self-inflicted call,
and adding the components would count it twice — which is why `total` is
computed over the union rather than by summing the three.

## The second component, and what is honestly known about it

The sheet's middle component is "calls chasing an already-submitted action".
§9 insight 15 flags this as unsettled and asks for it to be checked against
the Metrics sheet rather than assumed, and the check says the two are not
the same condition:

- A **logged process defect** is `process_gap.present` — something missing
  or unclear by design.
- **Chasing an already-submitted action** is the `process_breakdown` signal
  — "an internal process accepted an input and failed to act on it", whose
  typical triggers are a portal submission not applied, an ID never issued,
  a termination still billing. That is precisely a member chasing something
  they already did.

So they are mapped to two different fields here, and the commit that
introduces this says so, because Stream A's A3 was asked to settle the same
question from the extraction side and the two answers have to agree.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from domain.aggregation.call_tags import CallContext, EmployerFacts, Window
from domain.aggregation.figure import Figure
from domain.aggregation.patterns import share, time_aggregate
from domain.aggregation.repeat_contact import failure_driven_repeats
from domain.dashboard_config import DashboardConfig
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.signal_type import SignalType


@dataclass(frozen=True)
class SelfInflictedDemand:
    """Metric 5, as four figures that are never collapsed into one.

    `total` is not the sum of the three. It is the share of calls that meet
    *any* of them, over distinct calls — a call can be a repeat and carry a
    process gap, and summing would count it twice.
    """

    failure_driven_repeats: Figure
    chasing_submitted_action: Figure
    logged_process_defect: Figure
    total: Figure


def self_inflicted_demand(
    config: DashboardConfig, calls: Sequence[CallContext], window: Window
) -> SelfInflictedDemand:
    """The three components and their union, all gated on metric 5's min n of 60."""
    threshold = config.metric("self_inflicted_demand")
    in_window = window.calls_in(tuple(calls))

    repeats = failure_driven_repeats(in_window)
    chasing = tuple(call for call in in_window if SignalType.PROCESS_BREAKDOWN in call.tags.signals)
    defects = tuple(
        call
        for call in in_window
        if call.tags.process_gap is not None and call.tags.process_gap.present
    )

    caused = {call.reference for group in (repeats, chasing, defects) for call in group}
    union = tuple(call for call in in_window if call.reference in caused)

    return SelfInflictedDemand(
        failure_driven_repeats=share(threshold, numerator=repeats, denominator=in_window),
        chasing_submitted_action=share(threshold, numerator=chasing, denominator=in_window),
        logged_process_defect=share(threshold, numerator=defects, denominator=in_window),
        total=share(threshold, numerator=union, denominator=in_window),
    )


def complaint_attributed_to_choice(
    config: DashboardConfig, calls: Sequence[CallContext], window: Window
) -> Figure:
    """The complaint-based cut of the same question, kept deliberately apart.

    §9 insight 15: this "stays labelled as a different measure". It answers
    "how often did someone complain about *us*", which is related to but not
    the same as "how much of this volume did we create" — a member can cause
    us work without complaining, and can complain about a call we handled
    well. Presenting them as one number would make both unarguable.
    """
    in_window = window.calls_in(tuple(calls))
    ours = tuple(
        call
        for call in in_window
        if call.tags.complaint is not None
        and call.tags.complaint.present
        and call.tags.complaint.attributed_to is ComplaintAttribution.CHOICE
    )
    return share(config.metric("complaint_rate"), numerator=ours, denominator=in_window)


def cost_to_serve(
    config: DashboardConfig,
    employer: EmployerFacts,
    calls: Sequence[CallContext],
    window: Window,
) -> Figure:
    """Metric 9 — minutes of our people per covered life, per year.

    Self-inflicted demand's second view (§9 insight 15, view 2), and the
    margin metric in its own right: the admin fee is flat per group
    regardless of service consumed, so this is margin variance made visible.

    Minutes, never money. D4 leaves `cost_per_call` null and insight 15 is
    explicit that money stays out of this view entirely rather than
    appearing withheld — so no money figure is computed here at all, not
    even a suppressed one.
    """
    mine = [
        call for call in window.calls_in(tuple(calls)) if call.employer_ref == employer.reference
    ]
    return time_aggregate(
        config.metric("cost_to_serve"),
        calls=mine,
        population=employer.enrolled,
        weeks=window.weeks,
    )
