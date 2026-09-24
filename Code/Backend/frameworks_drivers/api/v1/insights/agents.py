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

## Agents with no calls in the window are absent

Unlike the employer tree, where a quiet account is a finding, an agent who
took no calls in the window has nothing to report and no baseline to be
missing from. The list is built from the calls themselves.
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


class AgentResponse(CamelModel):
    agent_ref: str
    calls: list[str]
    knowledge_errors: list[str] = Field(
        description="Calls where this agent stated a published rule incorrectly."
    )
    escalations_missed: list[str] = Field(
        description="Calls where an explicit escalation request went nowhere."
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
        description="Agents with calls in the window, by reference."
    )


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
        scope=ScopeResponse.of(view.scope.corpus, view.scope.filtered, query.corpus_query()),
        as_of=view.scope.as_of.isoformat(),
        window_weeks=round(view.window.weeks),
        quality_window_weeks=view.quality_window_weeks,
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
