"""`GET /api/v1/insights/demand` — where the calls come from.

## Four figures that are never collapsed into one

`self_inflicted` carries its three components and a total, and the total is
**not their sum**. It is the share of calls meeting *any* component, over
distinct calls: a call can be a repeat and carry a process gap, and adding
the three would count it twice. A client that summed them to check would
get a larger number and conclude something was wrong.

## The complaint cut stays labelled as a different measure

`complaints_about_us` answers "how often did someone complain about us",
which §9 insight 15 is explicit is *related to but not the same as* "how
much of this volume did we create". A member can cost us work without
complaining, and can complain about a call we handled well. Presenting them
as one number would make both unarguable, so they arrive as separate
fields with separate names.

## Touchpoints are counts, never rates

There is no per-touchpoint population to divide by — the denominator would
have to be "calls that could have originated here", which nothing records.
The unattributed bucket is read off the same ranking rather than recomputed,
so insight 16 and insight 18 cannot report different numbers for one set of
calls.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import Field

from frameworks_drivers.api.camel import CamelModel
from frameworks_drivers.api.dependencies import GetDemandDep
from frameworks_drivers.api.v1.insights.envelope import FigureResponse, ScopeResponse
from frameworks_drivers.api.v1.insights.labels import CodedValue, coded, coded_touchpoint
from frameworks_drivers.api.v1.insights.query import InsightsQueryDep

router = APIRouter(prefix="/insights", tags=["insights"])


class SelfInflictedResponse(CamelModel):
    failure_driven_repeats: FigureResponse
    chasing_submitted_action: FigureResponse
    logged_process_defect: FigureResponse
    total: FigureResponse = Field(
        description=(
            "Calls meeting ANY component, over distinct calls. Not the sum of the "
            "three — a call can be both a repeat and a process defect."
        )
    )


class AttributionCountResponse(CamelModel):
    attributed_to: CodedValue
    calls: int


class TouchpointRowResponse(CamelModel):
    touchpoint: CodedValue
    calls: int
    call_ids: list[str]
    attribution: list[AttributionCountResponse] = Field(
        description="Complaints here by party, published as a split and never reduced."
    )
    without_complaint: int = Field(
        description=(
            "Calls here with no complaint tagged. Not the same as a complaint with no "
            "attribution, which the schema does not allow."
        )
    )


class PromiseGapResponse(CamelModel):
    touchpoint: CodedValue
    proposed_change: str
    calls: int
    call_ids: list[str]
    minutes: float = Field(
        description=(
            "Talk time across those calls — a floor, since AHT excludes hold and after-call work."
        )
    )


class DemandResponse(CamelModel):
    scope: ScopeResponse
    as_of: str
    window_weeks: int
    self_inflicted: SelfInflictedResponse
    complaints_about_us: FigureResponse = Field(
        description=(
            "Complaints attributed to Choice. A different measure from self-inflicted "
            "demand, deliberately kept apart."
        )
    )
    touchpoints: list[TouchpointRowResponse] = Field(
        description="Busiest first. Counts, not rates."
    )
    unattributed: list[str] = Field(
        description="Calls with no touchpoint tagged — insight 18's residual bucket."
    )
    promise_gaps: list[PromiseGapResponse] = Field(
        description="Proposed changes at the enrolment touchpoints, most-proposed first."
    )


@router.get(
    "/demand",
    response_model=DemandResponse,
    status_code=status.HTTP_200_OK,
    summary="Self-inflicted demand, touchpoints and enrolment promise gaps",
)
async def read_demand(
    use_case: GetDemandDep,
    query: InsightsQueryDep,
) -> DemandResponse:
    view = await use_case.execute(query.to_request())
    demand = view.self_inflicted
    return DemandResponse(
        scope=ScopeResponse.of(
            view.scope.corpus,
            view.scope.filtered,
            query.corpus_query(),
        ),
        as_of=view.scope.as_of.isoformat(),
        window_weeks=round(view.window.weeks),
        self_inflicted=SelfInflictedResponse(
            failure_driven_repeats=FigureResponse.of(demand.failure_driven_repeats),
            chasing_submitted_action=FigureResponse.of(demand.chasing_submitted_action),
            logged_process_defect=FigureResponse.of(demand.logged_process_defect),
            total=FigureResponse.of(demand.total),
        ),
        complaints_about_us=FigureResponse.of(view.complaints_about_us),
        touchpoints=[
            TouchpointRowResponse(
                touchpoint=coded_touchpoint(row.touchpoint),
                calls=row.calls,
                call_ids=list(row.call_ids),
                attribution=[
                    AttributionCountResponse(attributed_to=coded(party), calls=count)
                    for party, count in row.attribution
                ],
                without_complaint=row.without_complaint,
            )
            for row in view.touchpoints
        ],
        unattributed=list(view.unattributed),
        promise_gaps=[
            PromiseGapResponse(
                touchpoint=coded_touchpoint(gap.touchpoint),
                proposed_change=gap.proposed_change,
                calls=gap.calls,
                call_ids=list(gap.call_ids),
                minutes=gap.minutes,
            )
            for gap in view.promise_gaps
        ],
    )
