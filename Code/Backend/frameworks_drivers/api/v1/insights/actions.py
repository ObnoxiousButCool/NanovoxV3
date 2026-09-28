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
from pydantic import Field

from frameworks_drivers.api.camel import CamelModel
from frameworks_drivers.api.dependencies import GetActionsDep
from frameworks_drivers.api.v1.insights.envelope import FigureResponse, ScopeResponse
from frameworks_drivers.api.v1.insights.labels import CodedValue, coded
from frameworks_drivers.api.v1.insights.query import InsightsQueryDep

if TYPE_CHECKING:
    from application.use_cases.read_insights import IssueRow
    from domain.aggregation.actions import ActionItem

router = APIRouter(prefix="/insights", tags=["insights"])


class ActionItemResponse(CamelModel):
    """One finding. No status — see this module's docstring."""

    signal: CodedValue
    severity: CodedValue
    owner_team: str = Field(
        description="From the Signal Taxonomy's Owner column, which the sheet calls mandatory."
    )
    calls: int
    call_ids: list[str]


class IssueAccountResponse(CamelModel):
    """One account's share of an issue, for "where it shows up"."""

    employer_ref: str
    name: str
    region: str
    broker_ref: str
    renewal_month: str
    calls: int
    renewal_in_months: int | None = Field(
        description="Whole months to the next renewal. Null when the month is unreadable."
    )


class IssueResponse(CamelModel):
    """One row of the issues-to-act-on list.

    Keyed by playbook, not by signal: `key` is exactly what
    `/actions?focus=<key>` takes and what `GET /insights/playbooks/{key}`
    resolves, so a row is never a number the reader cannot act on. The
    meaning and the suggested owner ride along so the panel needs one
    request rather than fourteen.
    """

    key: str = Field(description="The playbook key. Also the value of ?focus= on this screen.")
    label: str
    meaning: str
    owner_team: str = Field(description="The playbook's suggested owner, not a routing decision.")
    severity: str
    unit: str = Field(description="What `references` are: 'calls' or 'accounts'.")
    count: int | None = Field(
        description="Absent when the condition cannot be observed at all — never zero for it."
    )
    references: list[str] = Field(
        description="The calls or accounts behind the count, in the unit named above."
    )
    accounts: list[IssueAccountResponse] = Field(
        description=(
            "Where it shows up, most calls first then soonest renewal. A call with no "
            "employer is absent here and still present in the count."
        )
    )
    computable: bool
    unavailable_because: str | None = Field(
        description="Why there is no count, when there is none. Null when there is one."
    )


class OwnerWorkloadResponse(CamelModel):
    owner_team: str
    critical: int
    calls: int = Field(
        description=(
            "Distinct calls behind this team's items. One call raising two signals for "
            "the same team counts once."
        )
    )
    items: list[ActionItemResponse]


class ControlExceptionResponse(CamelModel):
    exception_type: CodedValue
    figure: FigureResponse


class WithheldPanelResponse(CamelModel):
    insight: int
    question: str
    why: str
    unlocked_by: str


class ActionsResponse(CamelModel):
    scope: ScopeResponse
    as_of: str
    window_weeks: int
    issues: list[IssueResponse] = Field(
        description=(
            "Every playbook key with something behind it, worst severity first and "
            "heaviest within a severity. A key that counted nothing is absent; a key "
            "that cannot be counted is present and says so."
        )
    )
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
        scope=ScopeResponse.of(
            view.scope.corpus,
            view.scope.filtered,
            query.corpus_query(),
            windows=[("Action items", view.window)],
        ),
        as_of=view.scope.as_of.isoformat(),
        window_weeks=round(view.window.weeks),
        issues=[_issue(row) for row in view.issues],
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
                exception_type=coded(exception), figure=FigureResponse.of(figure)
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


def _issue(row: IssueRow) -> IssueResponse:
    return IssueResponse(
        key=row.playbook.key,
        label=row.playbook.label,
        meaning=row.playbook.meaning,
        owner_team=row.playbook.owner_team,
        severity=row.playbook.severity.value,
        unit=row.issue.unit,
        count=row.issue.count if row.issue.computable else None,
        references=list(row.issue.references),
        accounts=[
            IssueAccountResponse(
                employer_ref=account.reference,
                name=account.name,
                region=account.region,
                broker_ref=account.broker_ref,
                renewal_month=account.renewal_month,
                calls=account.calls,
                renewal_in_months=account.months_to_renewal,
            )
            for account in row.issue.accounts
        ],
        computable=row.issue.computable,
        unavailable_because=row.issue.unavailable_because or None,
    )


def _item(item: ActionItem) -> ActionItemResponse:
    return ActionItemResponse(
        signal=coded(item.signal),
        severity=coded(item.severity),
        owner_team=item.owner_team,
        calls=item.calls,
        call_ids=list(item.call_ids),
    )
