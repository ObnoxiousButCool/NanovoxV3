"""`GET /api/v1/insights/actions` — the action centre, read side.

## There is no status on an item, and the response must not imply one

`actions.html` draws a board with lifecycle states, owners and resolutions.
None of that is stored: the write path is Phase 9 and decision D6. An item
here therefore carries what the signal itself says — what was found, who it
routes to, how serious the taxonomy says it is, and the calls behind it —
and nothing about where it has got to.

A default `status: "open"` would be a lifecycle claim no record supports,
and the first person to filter the board by status would be filtering on a
constant. The field is absent instead.

## Compliance exposure is reported by type, never blended

Metric 7's build note: "Report by exception type, not as one blended
number." A single compliance rate hides which control failed, which is the
only part anyone can fix. The denominator caveat travels with it, because
the Metrics sheet asks for calls *requiring* that control and v9 records no
such thing — so each rate is a floor on the true one, and says so.

## The withheld panel is part of the screen

Insight 22 — did the fix work — is withheld for a reason unlike the others:
the fields exist, but a second batch does not. It ships as a panel stating
the question, why it cannot be answered, and what would unlock it, rather
than being silently absent from a screen it belongs on.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from frameworks_drivers.api.dependencies import GetActionsDep
from frameworks_drivers.api.v1.insights.envelope import FigureResponse, ScopeResponse
from frameworks_drivers.api.v1.insights.query import InsightsQueryDep

if TYPE_CHECKING:
    from domain.aggregation.actions import ActionItem

router = APIRouter(prefix="/insights", tags=["insights"])


class ActionItemResponse(BaseModel):
    """One finding. No status — see this module's docstring."""

    signal: str
    severity: str
    owner_team: str = Field(
        description="From the Signal Taxonomy's Owner column, which the sheet calls mandatory."
    )
    calls: int
    call_ids: list[str]


class OwnerWorkloadResponse(BaseModel):
    owner_team: str
    critical: int
    calls: int = Field(
        description=(
            "Distinct calls behind this team's items. One call raising two signals for "
            "the same team counts once."
        )
    )
    items: list[ActionItemResponse]


class ControlExceptionResponse(BaseModel):
    exception_type: str
    figure: FigureResponse


class WithheldPanelResponse(BaseModel):
    insight: int
    question: str
    why: str
    unlocked_by: str


class ActionsResponse(BaseModel):
    scope: ScopeResponse
    as_of: str
    window_weeks: int
    items: list[ActionItemResponse] = Field(
        description=(
            "Every signal raised, worst severity first and heaviest within a severity. "
            "A signal nobody raised is absent, not present at zero."
        )
    )
    owners: list[OwnerWorkloadResponse] = Field(
        description="The same items routed, teams with critical work first."
    )
    control_exceptions: list[ControlExceptionResponse] = Field(
        description="Metric 7 by type. Never blended into one compliance rate."
    )
    control_denominator_caveat: str
    did_it_work: WithheldPanelResponse = Field(
        description="Insight 22, withheld until a comparable before and after exist."
    )


@router.get(
    "/actions",
    response_model=ActionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Findings to act on, routed, with compliance exposure",
)
async def read_actions(
    use_case: GetActionsDep,
    query: InsightsQueryDep,
) -> ActionsResponse:
    view = await use_case.execute(query.to_request())
    return ActionsResponse(
        scope=ScopeResponse.of(view.scope.corpus, view.scope.filtered, query.corpus_query()),
        as_of=view.scope.as_of.isoformat(),
        window_weeks=round(view.window.weeks),
        items=[_item(item) for item in view.items],
        owners=[
            OwnerWorkloadResponse(
                owner_team=load.owner_team,
                critical=load.critical,
                calls=load.calls,
                items=[_item(item) for item in load.items],
            )
            for load in view.owners
        ],
        control_exceptions=[
            ControlExceptionResponse(
                exception_type=exception.value, figure=FigureResponse.of(figure)
            )
            for exception, figure in view.control_exceptions
        ],
        control_denominator_caveat=view.control_denominator_caveat,
        did_it_work=WithheldPanelResponse(
            insight=view.did_it_work.insight,
            question=view.did_it_work.question,
            why=view.did_it_work.why,
            unlocked_by=view.did_it_work.unlocked_by,
        ),
    )


def _item(item: ActionItem) -> ActionItemResponse:
    return ActionItemResponse(
        signal=item.signal.value,
        severity=item.severity.value,
        owner_team=item.owner_team,
        calls=item.calls,
        call_ids=list(item.call_ids),
    )
