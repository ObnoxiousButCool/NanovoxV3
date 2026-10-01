"""The action centre's write side (Revised plan Phase 4, D6).

- `GET /insights/actions/board` — every persisted action, with the lanes.
  `?employer=` scopes it to one account and adds each card's share of it
- `POST /insights/actions` — raise one, from a playbook or by hand
- `GET /insights/actions/{id}` — one action
- `PATCH /insights/actions/{id}` — move, assign, tick, log, record

`GET /insights/actions` (in `actions.py`) is untouched and still returns
derived findings with no status. The two are different objects: a finding is
what the calls say, an action is what somebody is doing about it. Merging
them is how a finding acquires a fake status.

## What the responses say about themselves

- `recommendation.claim` is always `recommendation` (D14, C3a).
- `pastDue` is computed from the due date, beside the lane someone chose —
  "Overdue" stays a lane cards are moved into, as the prototype has it.
- Every board carries `trustNote`: there is no sign-in, and anyone who can
  reach the service can edit (D14, R9).
- A move the lifecycle refuses — to monitoring or completed without a
  measurement — is a 400 naming what is missing.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, status
from pydantic import Field

from application.use_cases.manage_actions import CreateActionRequest
from domain.actions import Action, ActionChange, Lifecycle, MeasurementWindow, Priority, past_due
from frameworks_drivers.api.camel import CamelModel
from frameworks_drivers.api.dependencies import (
    ActionContextDep,
    CreateActionDep,
    GetActionDep,
    ListActionsDep,
    UpdateActionDep,
)
from frameworks_drivers.api.v1.insights.query import InsightsQueryDep

router = APIRouter(prefix="/insights", tags=["actions"])

PriorityValue = Literal["high", "medium", "low"]


class RecommendationResponse(CamelModel):
    text: str
    claim: Literal["recommendation"] = Field(
        default="recommendation",
        description="A suggestion, never a measurement (D14, C3a).",
    )


class LaneResponse(CamelModel):
    code: str
    label: str
    open: bool = Field(description="Still being worked. Open and past due reads as past due.")
    requires: list[str] = Field(
        description="What an action must carry to sit here, e.g. a measurement window."
    )


class StepResponse(CamelModel):
    text: str
    done: bool


class LogEntryResponse(CamelModel):
    at: datetime
    text: str


class MeasurementWindowBody(CamelModel):
    start: date
    end: date


class ActionResponse(CamelModel):
    id: int
    reference: str = Field(description="The board's display id, e.g. ACT-007.")
    title: str
    source_kind: str
    source_detail: str | None
    issue_key: str | None
    evidence: str
    recommendation: RecommendationResponse | None
    owner_team: str
    owner: str | None
    priority: PriorityValue
    status: str
    status_label: str
    past_due: bool
    employer_ref: str | None
    broker_ref: str | None
    call_ids: list[str]
    steps: list[StepResponse]
    log: list[LogEntryResponse] = Field(description="Oldest first. Append-only.")
    created_at: datetime
    assigned_on: date | None
    due: date | None
    action_taken: str | None
    outcome: str | None
    measurement_window: MeasurementWindowBody | None
    label: str | None = Field(
        default=None,
        description=(
            "The action's name with no count in it — the playbook's own label, "
            "which `title` was composed from before '— N calls' was appended. Sent "
            "on the board only. A screen showing its own figure beside the card's "
            "needs the name without a number in it, and the alternative is the "
            "client cutting the count back off prose the server wrote."
        ),
    )
    calls_on_account: int | None = Field(
        default=None,
        description=(
            "How many of this action's cited calls belong to the account the board "
            "was scoped to. Null on the unscoped board, where there is no account to "
            "count against — never nought, which would read as a card touching none "
            "of an account's calls. "
            "**The card's own figures stay corpus-wide.** `title` counts every call "
            "that raised the signal, because that is the piece of work: one card, one "
            "owner team, worked once. Re-counting it per account would describe a "
            "different job from the one on the board and make the same card disagree "
            "with itself between two screens. This travels beside that number so an "
            "account page can show both rather than presenting the book's figure as "
            "the account's."
        ),
    )


class ActionBoardResponse(CamelModel):
    lanes: list[LaneResponse] = Field(description="In board order, from configuration.")
    actions: list[ActionResponse] = Field(description="Newest first.")
    trust_note: str


class CreateActionBody(CamelModel):
    title: str
    issue_key: str | None = Field(
        default=None,
        description="Prefills steps, owner team, priority and description from its playbook.",
    )
    call_ids: list[str] = Field(default_factory=list)
    evidence: str | None = None
    owner_team: str | None = None
    owner: str | None = None
    priority: PriorityValue | None = None
    status: str | None = Field(default=None, description="Defaults to the lifecycle's first lane.")
    due: date | None = None
    steps: list[str] | None = None
    employer_ref: str | None = None


class TickBody(CamelModel):
    index: int
    done: bool


class UpdateActionBody(CamelModel):
    status: str | None = None
    owner: str | None = None
    clear_owner: bool = False
    due: date | None = None
    clear_due: bool = False
    action_taken: str | None = None
    outcome: str | None = None
    measurement_window: MeasurementWindowBody | None = None
    ticks: list[TickBody] = Field(default_factory=list)
    note: str | None = Field(default=None, description="Appended to the activity log as written.")


@router.get(
    "/actions/board",
    response_model=ActionBoardResponse,
    status_code=status.HTTP_200_OK,
    summary="Every action being worked, with the board's lanes",
)
async def read_board(
    use_case: ListActionsDep,
    query: InsightsQueryDep,
) -> ActionBoardResponse:
    """Scoped by the shared filter bar, like every other screen.

    It was not, and the board sat under a bar reading "87 calls in scope"
    showing work on every account in the book, with nothing saying the two
    were answering different questions.

    The employer case is no longer a parameter of its own. `employer` is one
    of the shared filters and repeatable there, where this took a single
    string and silently used the last one sent -- so picking two accounts in
    the bar scoped the board to an arbitrary one of them.
    """
    board = await use_case.execute(query.to_request())
    return ActionBoardResponse(
        lanes=[
            LaneResponse(
                code=state.code,
                label=state.label,
                open=state.open,
                requires=sorted(req.value for req in state.requires),
            )
            for state in board.lifecycle.states
        ],
        actions=[
            _action(
                action,
                board.lifecycle,
                board.today,
                calls_on_account=board.calls_on_account.get(action.id),
                label=board.labels.get(action.id),
            )
            for action in board.actions
        ],
        trust_note=board.trust_note,
    )


@router.post(
    "/actions",
    response_model=ActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Raise an action, from a playbook or by hand",
)
async def create_action(
    body: CreateActionBody, use_case: CreateActionDep, context: ActionContextDep
) -> ActionResponse:
    created = await use_case.execute(
        CreateActionRequest(
            title=body.title,
            call_references=tuple(body.call_ids),
            issue_key=body.issue_key,
            evidence=body.evidence,
            owner_team=body.owner_team,
            owner=body.owner,
            priority=Priority(body.priority) if body.priority else None,
            status=body.status,
            due=body.due,
            steps=tuple(body.steps) if body.steps is not None else None,
            employer_ref=body.employer_ref,
        )
    )
    return _action(created, context.lifecycle, context.today)


@router.get(
    "/actions/{action_id}",
    response_model=ActionResponse,
    status_code=status.HTTP_200_OK,
    summary="One action, with its checklist and activity",
)
async def read_action(
    action_id: int, use_case: GetActionDep, context: ActionContextDep
) -> ActionResponse:
    action = await use_case.execute(action_id)
    return _action(action, context.lifecycle, context.today)


@router.patch(
    "/actions/{action_id}",
    response_model=ActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Move, assign, tick, log or record what was done and what changed",
)
async def update_action(
    action_id: int, body: UpdateActionBody, use_case: UpdateActionDep, context: ActionContextDep
) -> ActionResponse:
    window = body.measurement_window
    updated = await use_case.execute(
        action_id,
        ActionChange(
            status=body.status,
            owner=body.owner,
            clear_owner=body.clear_owner,
            due=body.due,
            clear_due=body.clear_due,
            action_taken=body.action_taken,
            outcome=body.outcome,
            measurement=MeasurementWindow(start=window.start, end=window.end) if window else None,
            ticks={tick.index: tick.done for tick in body.ticks},
            note=body.note,
        ),
    )
    return _action(updated, context.lifecycle, context.today)


def _action(
    action: Action,
    lifecycle: Lifecycle,
    today: date,
    *,
    calls_on_account: int | None = None,
    label: str | None = None,
) -> ActionResponse:
    measurement = action.measurement
    return ActionResponse(
        calls_on_account=calls_on_account,
        label=label,
        id=action.id,
        reference=action.reference,
        title=action.title,
        source_kind=action.source_kind.value,
        source_detail=action.source_detail,
        issue_key=action.issue_key,
        evidence=action.evidence,
        recommendation=(
            RecommendationResponse(text=action.recommendation) if action.recommendation else None
        ),
        owner_team=action.owner_team,
        owner=action.owner,
        priority=action.priority.value,
        status=action.status,
        status_label=lifecycle.state(action.status).label,
        past_due=past_due(action, lifecycle, today),
        employer_ref=action.employer_ref,
        broker_ref=action.broker_ref,
        call_ids=list(action.call_references),
        steps=[StepResponse(text=step.text, done=step.done) for step in action.steps],
        log=[LogEntryResponse(at=entry.at, text=entry.text) for entry in action.log],
        created_at=action.created_at,
        assigned_on=action.assigned_on,
        due=action.due,
        action_taken=action.action_taken,
        outcome=action.outcome,
        measurement_window=(
            MeasurementWindowBody(start=measurement.start, end=measurement.end)
            if measurement
            else None
        ),
    )
