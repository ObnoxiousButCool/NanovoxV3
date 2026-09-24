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

**The figures do not share a window, and must not be given one.** The
Metrics sheet sets `window_weeks` per metric and they differ across this
one screen: first contact resolution and knowledge failure rate are
four-week metrics, escalation integrity and commercial intent twelve-week.
So this takes an `as_of` date and resolves each metric's own window from
the config, rather than taking a window and applying it to everything.
Sharing one window would compute at least two figures over a period their
definition does not use, and publish them under a heading naming the other
period — the same class of error as rendering a withheld figure as zero,
and harder to spot.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from domain.aggregation.call_tags import CallContext, Window
from domain.aggregation.figure import Figure, WithheldReason, no_field_caveat
from domain.aggregation.patterns import share, window_for
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

#: The metrics whose windows this screen spans. Listed so the headline
#: count is derived from the same set the figures are, rather than from a
#: number someone has to remember to keep in step.
SCORECARD_METRICS = (
    "first_contact_resolution",
    "failure_driven_repeat_rate",
    "escalation_integrity",
    "knowledge_failure_rate",
    "commercial_intent_capture",
)


@dataclass(frozen=True)
class ExecScorecard:
    """What the executive screen leads with, all of it gated and evidenced."""

    #: The date every window ends on. Each figure looks back its own
    #: metric's `window_weeks` from here.
    as_of: date
    #: Calls in the longest window on the screen, which contains the rest.
    #: Never the sample behind any one figure — read each figure's own `n`.
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
    config: DashboardConfig, calls: Sequence[CallContext], as_of: date
) -> ExecScorecard:
    """The scorecard as at one date, each figure over its own window."""
    everything = tuple(calls)

    def scope(key: str) -> tuple[Window | None, tuple[CallContext, ...]]:
        window = window_for(config.metric(key), as_of)
        return window, everything if window is None else window.calls_in(everything)

    _, resolution_calls = scope("first_contact_resolution")
    repeat_window, repeat_calls = scope("failure_driven_repeat_rate")
    _, escalation_calls = scope("escalation_integrity")
    _, knowledge_calls = scope("knowledge_failure_rate")
    _, intent_calls = scope("commercial_intent_capture")

    if repeat_window is None:  # pragma: no cover - the config would have to drop the window
        raise ValueError(
            "Failure-driven repeat contact is defined over a window and the config gives it "
            "none; exposure to a repeat cannot be judged without a period to look forward in."
        )

    triggered = [
        call
        for call in escalation_calls
        if call.tags.escalation is not None and call.tags.escalation.triggered
    ]
    handled = [call for call in triggered if call.tags.escalation and call.tags.escalation.handled]

    intent = [
        call
        for call in intent_calls
        if any(statement.type in COMMERCIAL_INTENTS for statement in call.tags.intent)
    ]

    failures = [
        call
        for call in knowledge_calls
        if call.tags.knowledge_failure is not None and call.tags.knowledge_failure.present
    ]

    exposed = exposed_unresolved(repeat_calls, repeat_window)
    return ExecScorecard(
        as_of=as_of,
        calls=len(_widest(config, everything, as_of)),
        first_contact_resolution=share(
            config.metric("first_contact_resolution"),
            numerator=first_contact_resolutions(resolution_calls),
            denominator=resolution_denominator(resolution_calls),
        ),
        failure_driven_repeat_rate=share(
            config.metric("failure_driven_repeat_rate"),
            numerator=[
                call
                for call in failure_driven_repeats(repeat_calls)
                if call.reference in {c.reference for c in exposed}
            ],
            denominator=exposed,
        ),
        escalation_integrity=share(
            config.metric("escalation_integrity"), numerator=handled, denominator=triggered
        ),
        escalation_incidence=share(
            config.metric("escalation_integrity"),
            numerator=triggered,
            denominator=escalation_calls,
        ),
        knowledge_failure_rate=share(
            config.metric("knowledge_failure_rate"),
            numerator=failures,
            denominator=knowledge_calls,
        ),
        commercial_intent_capture=share(
            config.metric("commercial_intent_capture"),
            numerator=intent,
            denominator=intent_calls,
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


def _widest(
    config: DashboardConfig, calls: tuple[CallContext, ...], as_of: date
) -> tuple[CallContext, ...]:
    """Calls in the longest window any figure on this screen uses.

    The headline count cannot be "the calls behind the scorecard", because
    there is no single such set once the windows differ. It is the widest of
    them, which contains every other — derived from `SCORECARD_METRICS` so it
    moves when the screen does, and never mistaken for a figure's own `n`.
    """
    windows = [window_for(config.metric(key), as_of) for key in SCORECARD_METRICS]
    if any(window is None for window in windows):
        return calls
    widest = min(window.start for window in windows if window is not None)
    return Window(widest, as_of).calls_in(calls)


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
