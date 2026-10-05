"""`GET /api/v1/insights/agents` — agent conduct and handling.

## Events, not scores

The prototype's own framing, and §9 insight 28 follows it: agent conduct is
read from the `knowledge_error` signal — an agent stated a published rule
incorrectly — rather than from metric 12. So each agent leads with what
happened on their calls, and the score range sits beside it as context.

## The score range is not a ranking, and says so

`quality` carries a median rather than a mean, because one refused-evidence
call at the bottom of the range moves a mean and does not move a median.
Its caveat is computed from the agent's own `n` and states plainly that a
distribution this small cannot separate one agent from another. At batch-1
volume that is the truthful reading of every agent on the screen.

The Metrics sheet gives `agent_quality_score` no window — a score is a
property of the call, not of a period — so `quality_window_weeks` is null.
The events beside it *are* counts over a period and carry the knowledge
failure rate's window, stated rather than assumed.

## The whole roster is here, including the agents who took no calls

`agents.html` draws a coverage bar per agent against the roster's own
minimum for an agent-level rate. A bar counts *towards* something, so an
agent with nothing in the window is a row reading nought of thirty rather
than a row that is not there — the reader can see that nobody is close,
which is the page's main finding at batch-1 volume.

## The roster's expected score is design input, and is labelled as such

It was written before the calls and the corpus was generated from it, so
an agent matching their expected score is the data agreeing with itself.
It travels for display beside what happened and is never scored against.
`dominant_pattern` does not travel at all: unlike a number, it has no
honest use on a screen, being the instruction the generator followed.

## Why there is no "coach the agent, or fix the rule?" here

The prototype's panel asks how many distinct agents got each rule wrong,
and answers it from schema field 8 — which **D7 forbids attributing to an
agent anywhere**, this module included. The `knowledge_error` signal is
the agent-conduct event and carries no rule id, so the join the panel
needs does not exist on either field without resolving D7 in code. It is
rolled up by rule and by touchpoint on `/rules` instead.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import Field

from frameworks_drivers.api.camel import CamelModel
from frameworks_drivers.api.dependencies import GetAgentsDep
from frameworks_drivers.api.v1.insights.envelope import FigureResponse, ScopeResponse
from frameworks_drivers.api.v1.insights.labels import CodedValue, coded
from frameworks_drivers.api.v1.insights.query import InsightsQueryDep

router = APIRouter(prefix="/insights", tags=["insights"])


class ControlExceptionCountResponse(CamelModel):
    exception_type: CodedValue
    calls: int


class AgentQualityResponse(CamelModel):
    """Metric 12 as a range, never as a ranking position."""

    scored_calls: list[str]
    median_score: float | None = Field(
        default=None, description="Median, not mean. Null when no call was scored."
    )
    lowest: int | None = None
    highest: int | None = None
    caveat: str = Field(
        description=(
            "Computed from this agent's own n. Says plainly that a distribution this "
            "small cannot separate one agent from another."
        )
    )


class AgentRosterResponse(CamelModel):
    """One agent as the Agent Roster has them."""

    agent_ref: str
    name: str
    band: str
    expected_score: float | None = Field(
        default=None,
        description=(
            "Design input, not a measurement: the roster was written before the calls "
            "and the corpus was generated from it. For display beside what happened, "
            "never to score against."
        ),
    )
    score_variance: float | None = None


class BandRowResponse(CamelModel):
    """One experience band, pooled.

    Admissible where an employer roll-up is not: the Metrics sheet forbids
    averaging metric 12 to employer, product line or broker, and a band is
    none of those. The floor still applies.
    """

    band: str
    agents: int
    calls: int
    events: int
    scored_calls: int
    median_score: float | None = Field(
        default=None, description="Null under the floor — never a mean of four calls."
    )
    hard_call_share: float | None = Field(
        default=None,
        description=(
            "Always null. Complexity is a derived composite and is not wired to the "
            "corpus; see `complexityUnavailable` for the sentence to show instead."
        ),
    )


class AgentResponse(CamelModel):
    agent_ref: str
    calls: list[str]
    knowledge_errors: list[str] = Field(
        description="Calls where this agent stated a published rule incorrectly."
    )
    escalations_missed: list[str] = Field(
        description=(
            "Calls where an escalation was warranted and not handled -- "
            "`Escalation.missed`, the same set the risk screen counts."
        )
    )
    control_exceptions: list[ControlExceptionCountResponse]
    knowledge_error_rate: FigureResponse
    quality: AgentQualityResponse


class AgentsResponse(CamelModel):
    scope: ScopeResponse
    as_of: str
    window_weeks: int = Field(description="The period the events are counted over.")
    quality_window_weeks: int | None = Field(
        default=None,
        description=(
            "Null: a quality score is a property of the call, not of a period, so the "
            "Metrics sheet gives metric 12 no window."
        ),
    )
    agents: list[AgentResponse] = Field(
        description="Every agent on the roster or with a call in the window, by reference."
    )
    roster: list[AgentRosterResponse] = Field(
        description="The Agent Roster: who each reference is, and what band they are in."
    )
    bands: list[BandRowResponse] = Field(
        description="Bands with a call in the window, most events first."
    )
    escalations_refused: list[str] = Field(
        description=(
            "Calls where the caller asked for a supervisor and did not get one. Narrower "
            "than 'warranted', which is a judgement: this is what happened."
        )
    )
    min_calls_for_a_rate: int | None = Field(
        default=None,
        description=(
            "The minimum an agent needs before a rate is published for them. Null if the "
            "metric stops carrying one, in which case there is no coverage bar to draw."
        ),
    )
    complexity_unavailable: str


@router.get(
    "/agents",
    response_model=AgentsResponse,
    status_code=status.HTTP_200_OK,
    summary="Agent events, with each agent's own score range",
)
async def read_agents(
    use_case: GetAgentsDep,
    query: InsightsQueryDep,
) -> AgentsResponse:
    view = await use_case.execute(query.to_request())
    return AgentsResponse(
        scope=ScopeResponse.of(
            view.scope.corpus,
            view.scope.filtered,
            query.corpus_query(),
        ),
        as_of=view.scope.as_of.isoformat(),
        window_weeks=round(view.window.weeks),
        quality_window_weeks=view.quality_window_weeks,
        roster=[
            AgentRosterResponse(
                agent_ref=agent.reference,
                name=agent.name,
                band=agent.band,
                expected_score=agent.expected_score,
                score_variance=agent.score_variance,
            )
            for agent in view.roster
        ],
        bands=[
            BandRowResponse(
                band=row.band,
                agents=row.agents,
                calls=row.calls,
                events=row.events,
                scored_calls=row.scored_calls,
                median_score=row.median_score,
                hard_call_share=row.hard_call_share,
            )
            for row in view.bands
        ],
        escalations_refused=list(view.escalations_refused),
        min_calls_for_a_rate=view.min_calls_for_a_rate,
        complexity_unavailable=view.complexity_unavailable,
        agents=[
            AgentResponse(
                agent_ref=entry.events.agent_ref,
                calls=list(entry.events.calls),
                knowledge_errors=list(entry.events.knowledge_errors),
                escalations_missed=list(entry.events.escalations_missed),
                control_exceptions=[
                    ControlExceptionCountResponse(exception_type=coded(exception), calls=count)
                    for exception, count in entry.events.control_exceptions
                ],
                knowledge_error_rate=FigureResponse.of(entry.events.knowledge_error_rate),
                quality=AgentQualityResponse(
                    scored_calls=list(entry.quality.scored_calls),
                    median_score=entry.quality.median_score,
                    lowest=entry.quality.lowest,
                    highest=entry.quality.highest,
                    caveat=entry.quality.caveat,
                ),
            )
            for entry in view.agents
        ],
    )
