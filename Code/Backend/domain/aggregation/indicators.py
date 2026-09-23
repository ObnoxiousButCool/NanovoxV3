"""The ten indicator families — "other conditions observed".

Ported from `NV.INDICATORS` in `Prototype/app.js`, where there are exactly
ten. **Informational. They do not set the risk flag.** D2 makes the flag
metric 10's four named conditions and nothing else; nothing in
`risk_flag.py` imports this module, and the dependency runs one way only.
Two scoring systems on one page, one quietly feeding the other, is how a
yes/no flag turns back into the band D2 removed.

## Three things the port changed, all of them deliberate

**1. They are gated now.** The prototype's `indicatorsFor` keeps any family
with a single hit. plan.md §8 asks for "an absolute floor **and** a rate",
so `IndicatorGates` applies both. The floor of five calls is the
prototype's own — `agents.html` calls it "the five-call floor the rest of
the cockpit uses" — but the rate has no source at all and is the weakest
number in `dashboard.yaml`.

**2. One family cannot be computed and says so.** `high_effort` reads the
prototype's `effort_band`. Member effort is *our composite*, not a v9 field
— Stream A's A4 owns it and it is not built. A family that returns zero
because its input does not exist reads as "no high-effort calls here", which
is a false statement about the account. So it returns `computable=False`
and the page shows it as unavailable.

**3. One family is relabelled.** The prototype labels `knowledge_failure`
"Agent stated a published rule incorrectly" — but that is the definition of
the `knowledge_error` *signal*, not of schema field 8. D7 is open with Karim
on precisely that conflation, and carrying the prototype's wording across
would silently resolve it in code. The family keeps the field it reads and
loses the label: it says a knowledge failure was recorded, and says nothing
about the agent.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from domain.aggregation.call_tags import CallContext, EmployerFacts, Window
from domain.aggregation.repeat_contact import repeats
from domain.dashboard_config import DashboardConfig
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.intent_type import IntentType
from domain.value_objects.outcome import Outcome
from domain.value_objects.signal_code import Severity, SignalCode, severity_of

Predicate = Callable[[CallContext], bool]


@dataclass(frozen=True)
class Family:
    """One indicator family: what it reads, and whether v9 carries it."""

    code: str
    label: str
    #: `None` for a family that is not a per-call test: repeat contact is
    #: derived across an employer's calls, and high effort has no v9 field.
    matches: Predicate | None = None
    #: False when the family needs a field v9 does not have. Such a family
    #: is reported as unavailable, never as zero.
    computable: bool = True
    #: Why it cannot be computed, for the page to show instead of a count.
    unavailable_because: str = ""


@dataclass(frozen=True)
class Observation:
    """One family's standing for one employer."""

    family: Family
    call_ids: tuple[str, ...]
    employer_calls: int
    observed: bool

    @property
    def hits(self) -> int:
        return len(self.call_ids)

    @property
    def rate(self) -> float | None:
        if not self.employer_calls or not self.family.computable:
            return None
        return self.hits / self.employer_calls


def _critical_signal(call: CallContext) -> bool:
    return any(severity_of(code) is Severity.CRITICAL for code in call.tags.signals)


def _complaint_against_choice(call: CallContext) -> bool:
    complaint = call.tags.complaint
    return (
        complaint is not None
        and complaint.present
        and complaint.attributed_to is ComplaintAttribution.CHOICE
    )


def _escalation_missed(call: CallContext) -> bool:
    return call.tags.escalation is not None and call.tags.escalation.missed


def _exit_language(call: CallContext) -> bool:
    return any(
        statement.type in (IntentType.MARKET_TEST, IntentType.CANCELLATION)
        for statement in call.tags.intent
    )


def _knowledge_failure(call: CallContext) -> bool:
    failure = call.tags.knowledge_failure
    return failure is not None and failure.present


#: The ten, in the prototype's own order.
FAMILIES: tuple[Family, ...] = (
    Family("unresolved", "Unresolved outcome", lambda c: c.tags.outcome is Outcome.UNRESOLVED),
    Family("escalation_missed", "Escalation warranted, not handled", _escalation_missed),
    Family("complaint_choice", "Complaint attributed to Choice", _complaint_against_choice),
    # Repeat contact is derived, not tagged — `repeat_of` is a Transcript
    # Tracker column and not one of the sixteen schema fields. The set is
    # computed per employer in `observe()`, so this predicate is never used.
    Family("repeat_contact", "Repeat contact from the same caller"),
    Family("exit_language", "Exit or market-test language, verbatim", _exit_language),
    Family("critical_signal", "Critical-severity signal raised", _critical_signal),
    Family(
        "control_exception",
        "Compliance control exception",
        lambda c: bool(c.tags.control_exceptions),
    ),
    # NOT "agent stated a published rule incorrectly" — that is the
    # `knowledge_error` signal's definition, and D7 is open on the two being
    # conflated. This family reads schema field 8 and says only that.
    Family("knowledge_failure", "Knowledge failure recorded against a rule", _knowledge_failure),
    Family(
        "high_effort",
        "High member effort",
        computable=False,
        unavailable_because=(
            "Member effort is a derived composite, not a v9 field. Stream A's "
            "deterministic derivations (A4) own it and it is not built, so this "
            "condition cannot be observed — which is not the same as it being absent."
        ),
    ),
    Family(
        "broker_adverse",
        "Broker named adversely by the caller",
        lambda c: SignalCode.BROKER_CONDUCT_ADVERSE in c.tags.signals,
    ),
)


def observe(
    config: DashboardConfig,
    employer: EmployerFacts,
    calls: Sequence[CallContext],
    window: Window,
) -> tuple[Observation, ...]:
    """Every family's standing for one employer, observed or not.

    All ten are returned, including the ones that did not fire and the one
    that cannot be computed. A list of only the families that fired cannot
    tell a reader whether the others were checked and clear, or never
    checked at all — which on a page headed "other conditions observed" is
    the whole question.
    """
    mine = [
        call for call in window.calls_in(tuple(calls)) if call.employer_ref == employer.reference
    ]
    repeat_refs = {pair.first.reference for pair in repeats(mine)}

    observations: list[Observation] = []
    for family in FAMILIES:
        if not family.computable:
            observations.append(
                Observation(family=family, call_ids=(), employer_calls=len(mine), observed=False)
            )
            continue
        if family.matches is None:
            hits = tuple(sorted(repeat_refs))
        else:
            matches = family.matches
            hits = tuple(sorted(call.reference for call in mine if matches(call)))
        observations.append(
            Observation(
                family=family,
                call_ids=hits,
                employer_calls=len(mine),
                observed=config.indicators.fires(len(hits), len(mine)),
            )
        )
    return tuple(observations)


def observed(observations: Sequence[Observation]) -> tuple[Observation, ...]:
    """Only the families that fired, worst-severity-of-evidence aside.

    Ordered by hits rather than by any severity of their own: the families
    are not ranked anywhere in the workbook, and inventing an order would be
    a judgement about which condition matters most — which is the band D2
    removed, rebuilt as a sort.
    """
    return tuple(
        sorted(
            (observation for observation in observations if observation.observed),
            key=lambda observation: (-observation.hits, observation.family.code),
        )
    )


def unavailable(observations: Sequence[Observation]) -> tuple[Observation, ...]:
    """Families that could not be checked, so the page can say which."""
    return tuple(observation for observation in observations if not observation.family.computable)
