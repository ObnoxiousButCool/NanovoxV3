"""Group 3 — agent events, from the `knowledge_error` signal.

Ports `agents.html`, and D7 is the reason this module is careful.

**`knowledge_error` is not `knowledge_failure`.** The signal — "an agent
stated a published rule incorrectly", MEDIUM, owner Knowledge Management —
is the genuine agent-conduct event, and it is what this module counts. Schema
field 8's `knowledge_failure` tag is a different thing that the workbook
contradicts itself about: call C-0001 is RESOLVED, scores 91, is archetyped
"Competent and resolved", and still carries one. **D7 is open with Karim and
must not be resolved in code.** So field 8 is rolled up by rule id and by
touchpoint (see `rules.py` and `touchpoints.py`) and is never attributed to
an agent anywhere, including here.

Two things this module deliberately does not do:

- **It does not average quality scores to anything.** Metric 12 is "a
  property of the call and the agent" and the sheet says it is "never
  averaged to employer, product line or broker." Per agent it is admissible,
  and `agent_quality` returns the distribution with its own caveat rather
  than a bare mean — the prototype's own `agents.html` warns that an average
  over this many calls has a confidence interval wide enough to make the
  ranking meaningless.
- **It does not rank agents.** Counts and rates per agent, sorted by
  reference. Ordering people by a number this thin is the use the prototype
  itself cautions against, and if a screen wants it, that is a decision made
  on the screen with the caveat visible, not baked in here.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from statistics import median

from domain.aggregation.call_tags import AgentFacts, CallContext, Window
from domain.aggregation.figure import Figure
from domain.aggregation.patterns import share
from domain.dashboard_config import DashboardConfig
from domain.value_objects.control_exception_type import ControlExceptionType
from domain.value_objects.signal_type import SignalType


@dataclass(frozen=True)
class AgentEvents:
    """One agent's events in the window. Counts lead; the rate is gated."""

    agent_ref: str
    calls: tuple[str, ...]
    #: Calls where this agent stated a published rule incorrectly.
    knowledge_errors: tuple[str, ...]
    #: Calls where an explicit escalation request went nowhere.
    escalations_missed: tuple[str, ...]
    control_exceptions: tuple[tuple[ControlExceptionType, int], ...]
    knowledge_error_rate: Figure


@dataclass(frozen=True)
class AgentQuality:
    """Metric 12 per agent, as a distribution rather than a single mean.

    `median` rather than a mean because one refused-evidence call at the
    bottom of the range moves a mean and does not move a median, and the
    caveat is computed from `n` rather than written, so it stays true as the
    corpus grows.
    """

    agent_ref: str
    scored_calls: tuple[str, ...]
    median_score: float | None
    lowest: int | None
    highest: int | None

    @property
    def caveat(self) -> str:
        n = len(self.scored_calls)
        if n == 0:
            return "No scored call for this agent in the window."
        return (
            f"{n} scored call(s). A distribution this small cannot separate one "
            "agent from another; read it as this agent's own range, not a ranking."
        )


def agent_events(
    config: DashboardConfig, agent_ref: str, calls: Sequence[CallContext], window: Window
) -> AgentEvents:
    """Everything `agents.html` shows for one agent, for one window."""
    mine = [call for call in window.calls_in(tuple(calls)) if call.agent_ref == agent_ref]

    errors = tuple(call for call in mine if SignalType.KNOWLEDGE_ERROR in call.tags.signals)
    # `Escalation.missed`, not the `escalation_missed` signal. The two are
    # not the same set: a call can carry the signal and still record the
    # escalation as handled, and this counted two such calls against one
    # agent while the risk screen, the executive trend strip and the account
    # profile — all of which read `missed` — counted neither. Escalation is
    # not the `knowledge_error` case above: there the signal is the conduct
    # event and the schema field is the one in dispute, whereas here the
    # schema already says whether a warranted escalation was handled, so the
    # signal is a second opinion about a fact the data states outright.
    missed = tuple(call for call in mine if call.tags.escalation and call.tags.escalation.missed)

    exceptions = dict.fromkeys(ControlExceptionType, 0)
    for call in mine:
        for exception in call.tags.control_exceptions:
            exceptions[exception] += 1

    return AgentEvents(
        agent_ref=agent_ref,
        calls=tuple(call.reference for call in mine),
        knowledge_errors=tuple(call.reference for call in errors),
        escalations_missed=tuple(call.reference for call in missed),
        control_exceptions=tuple(
            (exception, count) for exception, count in exceptions.items() if count
        ),
        knowledge_error_rate=share(
            config.metric("knowledge_failure_rate"), numerator=errors, denominator=mine
        ),
    )


def agent_quality(agent_ref: str, calls: Sequence[CallContext], window: Window) -> AgentQuality:
    """Metric 12 for one agent: the range of their scored calls.

    Per agent only. Rolling this up to an employer, a product line or a
    broker is forbidden by the Metrics sheet, and there is no function here
    that would let a caller do it by accident.
    """
    scored = [
        call
        for call in window.calls_in(tuple(calls))
        if call.agent_ref == agent_ref and call.tags.quality_score is not None
    ]
    scores = [call.tags.quality_score for call in scored if call.tags.quality_score is not None]
    return AgentQuality(
        agent_ref=agent_ref,
        scored_calls=tuple(call.reference for call in scored),
        median_score=median(scores) if scores else None,
        lowest=min(scores, default=None),
        highest=max(scores, default=None),
    )


#: The prototype's floor for publishing a band's median score. It has no
#: workbook source — the Metrics sheet sets minimums per metric and none of
#: them is "a band" — so it sits here named and commented rather than
#: inline in the calculation where nobody could argue with it.
BAND_MIN_SCORED = 5

#: Why the prototype's "hard calls" column cannot be filled. Complexity is
#: our composite, not a v9 field, and `indicators.py` already refuses to
#: report the matching effort family as zero for the same reason. A share
#: of high-complexity calls computed from nothing would read as "this band
#: handles easy work", which is a claim about people.
COMPLEXITY_UNAVAILABLE = (
    "Call complexity is a derived composite, not a v9 field. Stream A's deterministic "
    "derivations own it and it is not wired to the corpus, so the share of harder calls "
    "cannot be observed — which is not the same as the calls being easy."
)


@dataclass(frozen=True)
class BandRow:
    """One experience band, pooled.

    Grouping is what recovers the sample a single agent lacks: a band
    pools thirty-odd calls where an agent has three. It is admissible
    where an employer roll-up is not — the Metrics sheet forbids averaging
    metric 12 to employer, product line or broker, and a band is none of
    those — but the floor still applies, and a band under it publishes no
    score rather than a mean of four.
    """

    band: str
    agents: int
    calls: int
    events: int
    scored_calls: int
    median_score: float | None
    #: Always `None`. Kept as a field rather than dropped so the response
    #: can carry the reason beside it — see `COMPLEXITY_UNAVAILABLE`.
    hard_call_share: float | None = None


@dataclass
class _BandTally:
    """A band's running totals while `band_rows` walks the calls."""

    agents: int = 0
    calls: int = 0
    events: int = 0
    scores: list[int] = field(default_factory=list)


def band_rows(
    roster: Sequence[AgentFacts],
    events: Sequence[AgentEvents],
    calls: Sequence[CallContext],
    window: Window,
) -> tuple[BandRow, ...]:
    """Every band with a call in the window, most events first.

    Bands with nothing in scope are dropped rather than shown at nought:
    unlike an agent, a band is not a person anybody is accountable for,
    and an empty row invites a comparison between a band that did well and
    one that was not on shift.
    """
    band_of = {agent.reference: agent.band for agent in roster}
    events_of = {
        entry.agent_ref: len(entry.knowledge_errors)
        + len(entry.escalations_missed)
        + sum(count for _, count in entry.control_exceptions)
        for entry in events
    }

    tallies: dict[str, _BandTally] = {}
    for agent in roster:
        tally = tallies.setdefault(agent.band, _BandTally())
        tally.agents += 1
        tally.events += events_of.get(agent.reference, 0)

    for call in window.calls_in(tuple(calls)):
        band = band_of.get(call.agent_ref or "")
        if band is None:
            continue
        tally = tallies[band]
        tally.calls += 1
        if call.tags.quality_score is not None:
            tally.scores.append(call.tags.quality_score)

    rows = [
        BandRow(
            band=band,
            agents=tally.agents,
            calls=tally.calls,
            events=tally.events,
            scored_calls=len(tally.scores),
            median_score=(median(tally.scores) if len(tally.scores) >= BAND_MIN_SCORED else None),
        )
        for band, tally in tallies.items()
        if tally.calls > 0
    ]
    return tuple(sorted(rows, key=lambda row: (-row.events, -row.calls, row.band)))


def escalations_refused(calls: Sequence[CallContext], window: Window) -> tuple[str, ...]:
    """Calls where the caller asked for a supervisor and did not get one.

    The narrowest and least arguable conduct event on the page: not "a
    supervisor was warranted" — a judgement — but "somebody asked, and was
    refused", which is a fact about what happened on the call.
    """
    return tuple(
        call.reference
        for call in window.calls_in(tuple(calls))
        if call.tags.escalation is not None
        and call.tags.escalation.requested_by_caller
        and not call.tags.escalation.handled
    )


def control_exception_rates(
    config: DashboardConfig, calls: Sequence[CallContext], window: Window
) -> tuple[tuple[ControlExceptionType, Figure], ...]:
    """Metric 7, by exception type — never as one blended number.

    The sheet's build note: "Deterministic — no model judgement. Owner is
    Compliance, not the call centre. Report by exception type, not as one
    blended number." A single compliance rate hides which control failed,
    which is the only part anyone can fix.

    The denominator is every call in the window. The sheet's own is "all
    calls requiring that control", and nothing in v9 records which controls
    a given call required — so this is stated as the wider denominator it
    is, in the caveat, rather than quietly presented as the sheet's.
    """
    in_window = window.calls_in(tuple(calls))
    threshold = config.metric("control_exception_rate")
    return tuple(
        (
            exception,
            share(
                threshold,
                numerator=[call for call in in_window if exception in call.tags.control_exceptions],
                denominator=in_window,
            ),
        )
        for exception in ControlExceptionType
    )


CONTROL_DENOMINATOR_CAVEAT = (
    "Denominator is all calls in the window. The Metrics sheet asks for calls "
    "requiring that control, which v9 does not record, so this rate is a floor "
    "on the true exception rate rather than the rate itself."
)
