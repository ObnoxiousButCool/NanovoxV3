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
from datetime import date

from domain.aggregation.call_tags import CallContext, EmployerFacts, Window
from domain.aggregation.repeat_contact import repeats
from domain.aggregation.trends import slice_window
from domain.dashboard_config import DashboardConfig
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.intent_type import IntentType
from domain.value_objects.outcome import Outcome
from domain.value_objects.signal_severity import SignalSeverity
from domain.value_objects.signal_type import SignalType, severity_of

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

    def tests(self, call: CallContext) -> bool:
        """Whether this call matches, for a caller that has one call in hand.

        False for a family that is not a per-call test, which is the honest
        answer to "does this call match": repeat contact is a relationship
        across an employer's calls and high effort has no field to read.
        """
        return self.matches is not None and self.matches(call)


@dataclass(frozen=True)
class Observation:
    """One family's standing for one employer.

    **`observed=False` has two causes and they are not the same statement.**
    Either the family was tested against this employer and did not clear its
    gates, or the employer has too few calls for any family to be tested at
    all. The first is a finding about the account; the second is a fact
    about how much we have of it. `assessable` is what tells them apart, and
    without it a count of nought reads as "nothing here" in both cases --
    the withheld-is-not-zero mistake, one level down.
    """

    family: Family
    call_ids: tuple[str, ...]
    employer_calls: int
    observed: bool
    #: False when the employer is under `IndicatorGates.min_employer_calls`,
    #: so no family could fire whatever its hits. The hits are still carried:
    #: they are real calls, and a page saying "2 of 3 calls, not assessed" is
    #: both true and useful, where "not observed" would be false.
    assessable: bool = True
    #: Why not, in a reader's words. Empty when `assessable`.
    unassessable_because: str = ""

    @property
    def hits(self) -> int:
        return len(self.call_ids)

    @property
    def rate(self) -> float | None:
        if not self.employer_calls or not self.family.computable:
            return None
        return self.hits / self.employer_calls


def _critical_signal(call: CallContext) -> bool:
    return any(severity_of(code) is SignalSeverity.CRITICAL for code in call.tags.signals)


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
        lambda c: SignalType.BROKER_CONDUCT_ADVERSE in c.tags.signals,
    ),
)


def family(code: str) -> Family:
    """One family by code, so a screen counting it cannot invent its own test.

    The risk screen's exit-language tile read the `retention_risk` signal
    while the drivers list beside it read this family's intent test, so the
    same screen reported 24 and 41 for the same named thing and the tile
    linked to the playbook for the other one. A caller that wants a family's
    count asks for the family.
    """
    for candidate in FAMILIES:
        if candidate.code == code:
            return candidate
    raise KeyError(f"No indicator family with code {code!r}.")


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
    assessable = config.indicators.assessable(len(mine))
    # Written once, with the floor in it, rather than left to each caller to
    # phrase: the number is config and a page that hard-coded "five" would
    # go quietly wrong the day it is calibrated.
    unassessable_because = (
        ""
        if assessable
        else (
            f"This account has {len(mine)} "
            f"{'call' if len(mine) == 1 else 'calls'} in the window and the ten "
            f"families are assessed from {config.indicators.min_employer_calls}. They "
            "were not checked, which is not the same as none being present."
        )
    )

    observations: list[Observation] = []
    for family in FAMILIES:
        if not family.computable:
            observations.append(
                Observation(
                    family=family,
                    call_ids=(),
                    employer_calls=len(mine),
                    observed=False,
                    assessable=assessable,
                    unassessable_because=unassessable_because,
                )
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
                assessable=assessable,
                unassessable_because=unassessable_because,
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


def assessed(observations: Sequence[Observation]) -> bool:
    """Whether the families were tested against this employer at all.

    A caller counting `observed()` needs this beside the count, because nought
    of ten means two different things without it.
    """
    return all(observation.assessable for observation in observations)


#: The window is cut into this many slices and only the last one counts as
#: "recently". Three, so a 12-week window gives the prototype's own "Wk
#: 9-12" -- expressed as a ratio, like `risk_drivers._PARTS`, so it survives
#: a change to the window's length rather than hard-coding four weeks.
_RECENT_PARTS = 3


@dataclass(frozen=True)
class NewlyFlagged:
    """Accounts whose **first** indicator falls in the recent slice.

    Not "accounts flagged recently": the flag is metric 10 and this is not
    it (D12). This counts an account's first appearance of any of the ten
    indicator families, which is the question the tile asks -- who is new to
    the list, rather than who is on it.

    Counted across the whole book and deliberately unfiltered, which is the
    one place on this screen where that is true. An account's first
    indicator is a fact about the account, not about the slice a reader is
    looking through: narrowing to a region would make an account "new"
    because the reader changed a dropdown, which is the opposite of what the
    tile says.

    `since` travels with the count because a bare "7" is unreadable -- the
    number means nothing without the date it counts from.
    """

    employers: tuple[str, ...]
    since: date
    #: How many weeks the recent slice spans, for a screen that wants to say
    #: "in the last four weeks" without recomputing it.
    weeks: int

    @property
    def count(self) -> int:
        return len(self.employers)


def first_indicator_on(calls: Sequence[CallContext]) -> date | None:
    """The date of the earliest call raising any indicator, or `None`.

    Reads the same `FAMILIES` predicates `observe` does, including the
    repeat-contact set it has to compute rather than match, so "an
    indicator" means one thing on this screen. A family that cannot be
    computed contributes nothing here and is not treated as absent -- it is
    simply not evidence of a first anything.
    """
    mine = tuple(calls)
    if not mine:
        return None
    repeat_refs = {pair.first.reference for pair in repeats(mine)}
    hits = [
        call.occurred_on
        for call in mine
        if call.reference in repeat_refs
        or any(family.matches(call) for family in FAMILIES if family.computable and family.matches)
    ]
    return min(hits) if hits else None


def newly_flagged(
    calls: Sequence[CallContext], window: Window, *, parts: int = _RECENT_PARTS
) -> NewlyFlagged | None:
    """Accounts whose first indicator lands in the last slice of `window`.

    `None` where the window is too short to slice, rather than nought: a
    window that cannot be cut has not told us that nobody is new.
    """
    slices = slice_window(window, parts)
    if not slices:
        return None
    recent = slices[-1]
    by_employer: dict[str, list[CallContext]] = {}
    for call in window.calls_in(tuple(calls)):
        if call.employer_ref is not None:
            by_employer.setdefault(call.employer_ref, []).append(call)
    new = [
        reference
        for reference, mine in by_employer.items()
        if (first := first_indicator_on(mine)) is not None and first >= recent.start
    ]
    return NewlyFlagged(
        employers=tuple(sorted(new)),
        since=recent.start,
        weeks=round(((recent.end - recent.start).days + 1) / 7),
    )
