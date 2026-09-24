"""`GET /api/v1/insights/exec` — the executive scorecard.

## Why every figure states its own window

The Metrics sheet gives each metric its own `window_weeks`, and this one
screen spans two: first contact resolution and knowledge failure rate look
back four weeks, escalation integrity and commercial intent twelve. So the
response cannot carry a single period next to a row of figures — it would
be right about three of them and wrong about two, and nothing on the wire
would say which.

Each metric therefore arrives as its own entry carrying `key`, the sheet's
own `name`, its `window_weeks`, and the figure. `as_of` is the one date
they share: every window ends there.

## Escalation is a pair and stays a pair

`escalation_integrity_pair` returns both views with their labels because
which is which is a definition, not a presentation choice. Handled over
warranted is the control measure; warranted over all calls is the scale it
rests on. A client that took the first alone would publish a number that
reads as good news at exactly the moment it is worst, so they travel
together in one field rather than as two entries a client can pick between.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from domain.aggregation.exec_scorecard import SCORECARD_METRICS, escalation_integrity_pair
from frameworks_drivers.api.dependencies import DashboardConfigDep, GetExecScorecardDep
from frameworks_drivers.api.v1.insights.envelope import FigureResponse, ScopeResponse
from frameworks_drivers.api.v1.insights.query import InsightsQueryDep

router = APIRouter(prefix="/insights", tags=["insights"])


class MetricFigureResponse(BaseModel):
    """One published metric, with the window it was computed over."""

    key: str = Field(description="The metric's key in dashboard.yaml.")
    name: str = Field(description="The Metrics sheet's own name for it.")
    window_weeks: int | None = Field(
        default=None,
        description=(
            "How far back this metric looks from `as_of`. Metrics on one screen "
            "differ; null means the metric is not windowed at all."
        ),
    )
    figure: FigureResponse


class LabelledFigureResponse(BaseModel):
    label: str
    figure: FigureResponse


class ExecScorecardResponse(BaseModel):
    scope: ScopeResponse
    as_of: str = Field(description="The date every window on this screen ends on.")
    calls: int = Field(
        description=(
            "Calls in the longest window on the screen, which contains every other. "
            "Never the sample behind any one figure — read that figure's own `n`."
        )
    )
    metrics: list[MetricFigureResponse]
    escalation: list[LabelledFigureResponse] = Field(
        description=(
            "Both escalation views, in reading order. Handled over warranted is the "
            "control measure; warranted over all calls is its scale. Shown together "
            "because either alone misleads."
        )
    )
    intent_routed: FigureResponse = Field(
        description=(
            "Always withheld on v9 data: whether commercial intent reached anyone who "
            "could act on it is not a field. Zero would claim we checked."
        )
    )


@router.get(
    "/exec",
    response_model=ExecScorecardResponse,
    status_code=status.HTTP_200_OK,
    summary="The executive scorecard",
)
async def read_exec_scorecard(
    use_case: GetExecScorecardDep,
    config: DashboardConfigDep,
    query: InsightsQueryDep,
) -> ExecScorecardResponse:
    result = await use_case.execute(query.to_request())
    card = result.scorecard
    figures = {
        "first_contact_resolution": card.first_contact_resolution,
        "failure_driven_repeat_rate": card.failure_driven_repeat_rate,
        "escalation_integrity": card.escalation_integrity,
        "knowledge_failure_rate": card.knowledge_failure_rate,
        "commercial_intent_capture": card.commercial_intent_capture,
    }
    return ExecScorecardResponse(
        scope=ScopeResponse.of(result.scope.corpus, result.scope.filtered, query.corpus_query()),
        as_of=card.as_of.isoformat(),
        calls=card.calls,
        metrics=[
            MetricFigureResponse(
                key=key,
                name=config.metric(key).name,
                window_weeks=config.metric(key).window_weeks,
                figure=FigureResponse.of(figures[key]),
            )
            for key in SCORECARD_METRICS
        ],
        escalation=[
            LabelledFigureResponse(label=label, figure=FigureResponse.of(figure))
            for label, figure in escalation_integrity_pair(card)
        ],
        intent_routed=FigureResponse.of(card.intent_routed),
    )
