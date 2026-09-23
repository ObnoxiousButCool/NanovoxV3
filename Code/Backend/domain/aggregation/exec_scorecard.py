"""Group 5 — the executive scorecard.

The handful of figures `exec.html` leads with, each already gated and each
carrying its own evidence. Nothing new is measured here: this composes the
metrics the other groups define, which is the point — a scorecard that
recomputed its own versions would be a second set of numbers that disagree
with the screens they link to.

**Escalation integrity is shown both ways, labelled.** §9 asks for the pair
side by side, and `exec.html` already does it: handled over triggered is the
control measure, and escalations over all calls is the context. Against all
calls a rate near zero reads as good news; against warranted calls it reads
as the control failure it is. Publishing only the second would be
misleading, and publishing only the first loses the scale. So both, named.

**Commercial intent's finding is the routed flag, not the count.** Metric
11's build note: "in the current service model, none of it reaches sales."
The scorecard carries the count of calls stating intent; whether any was
routed is not a v9 field, and `intent_routed` is therefore withheld with a
NO_FIELD reason rather than reported as zero — zero would assert that we
checked and found none, which is a stronger claim than the data supports.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from domain.aggregation.call_tags import CallContext, Window
from domain.aggregation.figure import Figure, WithheldReason, no_field_caveat
from domain.aggregation.patterns import share
from domain.aggregation.repeat_contact import (
    exposed_unresolved,
    failure_driven_repeats,
    first_contact_resolutions,
    resolution_denominator,
)
from domain.dashboard_config import DashboardConfig
from domain.value_objects.intent_type import IntentType

#: The three intent types that are commercial. `none` is the fourth value of
#: schema field 9 and means the caller stated no intent, so it is not one.
COMMERCIAL_INTENTS = (IntentType.EXPANSION, IntentType.MARKET_TEST, IntentType.CANCELLATION)


@dataclass(frozen=True)
class ExecScorecard:
    """What the executive screen leads with, all of it gated and evidenced."""

    calls: int
    first_contact_resolution: Figure
    failure_driven_repeat_rate: Figure
    #: Handled over triggered — the control measure (metric 6).
    escalation_integrity: Figure
    #: Triggered over all calls — the context, so a reader can see how much
    #: of the book the control measure rests on. Never shown alone.
    escalation_incidence: Figure
    knowledge_failure_rate: Figure
    commercial_intent_capture: Figure
    #: Withheld, always, on this data: whether an intent reached sales is
    #: not a v9 field.
    intent_routed: Figure


def exec_scorecard(
    config: DashboardConfig, calls: Sequence[CallContext], window: Window
) -> ExecScorecard:
    in_window = window.calls_in(tuple(calls))

    triggered = [
        call
        for call in in_window
        if call.tags.escalation is not None and call.tags.escalation.triggered
    ]
    handled = [call for call in triggered if call.tags.escalation and call.tags.escalation.handled]

    intent = [
        call
        for call in in_window
        if any(statement.type in COMMERCIAL_INTENTS for statement in call.tags.intent)
    ]

    failures = [
        call
        for call in in_window
        if call.tags.knowledge_failure is not None and call.tags.knowledge_failure.present
    ]

    exposed = exposed_unresolved(in_window, window)
    return ExecScorecard(
        calls=len(in_window),
        first_contact_resolution=share(
            config.metric("first_contact_resolution"),
            numerator=first_contact_resolutions(in_window),
            denominator=resolution_denominator(in_window),
        ),
        failure_driven_repeat_rate=share(
            config.metric("failure_driven_repeat_rate"),
            numerator=[
                call
                for call in failure_driven_repeats(in_window)
                if call.reference in {c.reference for c in exposed}
            ],
            denominator=exposed,
        ),
        escalation_integrity=share(
            config.metric("escalation_integrity"), numerator=handled, denominator=triggered
        ),
        escalation_incidence=share(
            config.metric("escalation_integrity"), numerator=triggered, denominator=in_window
        ),
        knowledge_failure_rate=share(
            config.metric("knowledge_failure_rate"), numerator=failures, denominator=in_window
        ),
        commercial_intent_capture=share(
            config.metric("commercial_intent_capture"), numerator=intent, denominator=in_window
        ),
        intent_routed=Figure.withheld(
            WithheldReason.NO_FIELD,
            tuple(call.reference for call in intent),
            caveats=(
                no_field_caveat(
                    "whether commercial intent reached anyone who could sell to the account",
                    "a routing field on the intent tag, which the v9 schema does not have",
                ),
            ),
        ),
    )


def escalation_integrity_pair(scorecard: ExecScorecard) -> tuple[tuple[str, Figure], ...]:
    """The two escalation figures, labelled, in the order they are read.

    Returned together so a screen cannot take one and leave the other. The
    labels are here rather than in the frontend because which is which is a
    definition, not a presentation choice.
    """
    return (
        ("Handled, of escalations that were warranted", scorecard.escalation_integrity),
        ("Escalations warranted, of all calls", scorecard.escalation_incidence),
    )
