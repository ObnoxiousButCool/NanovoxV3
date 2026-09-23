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
from dataclasses import dataclass
from statistics import median

from domain.aggregation.call_tags import CallContext, Window
from domain.aggregation.figure import Figure
from domain.aggregation.patterns import share
from domain.dashboard_config import DashboardConfig
from domain.value_objects.control_exception_type import ControlExceptionType
from domain.value_objects.signal_code import SignalCode


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

    errors = tuple(call for call in mine if SignalCode.KNOWLEDGE_ERROR in call.tags.signals)
    missed = tuple(call for call in mine if SignalCode.ESCALATION_MISSED in call.tags.signals)

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
