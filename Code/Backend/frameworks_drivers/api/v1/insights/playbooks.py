"""`GET /api/v1/insights/playbooks[/{key}]` — the issue-key registry (I3).

Every red or orange number on a screen links to the focused action view for
an issue key, and the view reads the playbook for it from here. Keys are
defined once, in `config/playbooks.yaml`; a key that resolves to nothing is a
404 rather than an empty panel.

## Every playbook is labelled a recommendation

`claim` is always `recommendation` and `reviewed` says whether the owning
teams have reviewed the steps. They have not: they are the prototype's
generic starting playbook (R7). A suggested step must not be readable back
as a measurement or as a team's own procedure (D14, C3a).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, status
from pydantic import Field

from domain.errors import NotFoundError
from domain.playbooks import Playbook
from frameworks_drivers.api.camel import CamelModel
from frameworks_drivers.api.dependencies import GetPlaybookDep, ListPlaybooksDep

router = APIRouter(prefix="/insights", tags=["insights"])


class PlaybookResponse(CamelModel):
    key: str
    label: str
    unit: Literal["calls", "accounts", "actions"]
    owner_team: str = Field(
        description=(
            "The suggested owner. For a touchpoint or signal key this is the workbook's "
            "own owner (Touchpoints sheet, Signal Taxonomy)."
        )
    )
    severity: Literal["high", "medium"]
    meaning: str
    why: str
    steps: list[str]
    source: str | None = Field(
        description="The kind of action this issue produces, when it produces one."
    )
    dynamic: bool = Field(
        description="Built from a template for one touchpoint, category, signal or product line."
    )
    claim: Literal["recommendation"] = Field(
        default="recommendation",
        description="Always a recommendation, never a measurement (D14, C3a).",
    )
    reviewed: bool = Field(
        description="Whether the owning teams have reviewed these steps. False until they do."
    )


class DynamicKindResponse(CamelModel):
    prefix: Literal["tp", "cat", "sig", "pl"]
    noun: str


class HeldBackResponse(CamelModel):
    key: str
    reason: str


class PlaybookCatalogueResponse(CamelModel):
    version: str
    reviewed: bool
    review_note: str
    playbooks: list[PlaybookResponse] = Field(description="Every static key.")
    dynamic_kinds: list[DynamicKindResponse] = Field(
        description="Key prefixes resolved per value, e.g. tp_denial_letter_eob."
    )
    held_back: list[HeldBackResponse] = Field(
        description="Prototype keys deliberately not shipped, and the decision that holds each."
    )


@router.get(
    "/playbooks",
    response_model=PlaybookCatalogueResponse,
    status_code=status.HTTP_200_OK,
    summary="Every issue key a screen can link to, and what each means",
)
async def list_playbooks(use_case: ListPlaybooksDep) -> PlaybookCatalogueResponse:
    catalogue = use_case.execute()
    return PlaybookCatalogueResponse(
        version=catalogue.version,
        reviewed=catalogue.reviewed,
        review_note=catalogue.review_note,
        playbooks=[_playbook(p, catalogue.reviewed) for p in catalogue.playbooks],
        dynamic_kinds=[
            DynamicKindResponse(prefix=t.kind.value, noun=t.noun) for t in catalogue.templates
        ],
        held_back=[HeldBackResponse(key=h.key, reason=h.reason) for h in catalogue.held_back],
    )


@router.get(
    "/playbooks/{key}",
    response_model=PlaybookResponse,
    status_code=status.HTTP_200_OK,
    summary="The playbook for one issue key",
)
async def get_playbook(
    key: str, use_case: GetPlaybookDep, catalogue: ListPlaybooksDep
) -> PlaybookResponse:
    resolution = await use_case.execute(key)
    if resolution.held_back_reason is not None:
        raise NotFoundError(
            f"The issue key {key!r} is held back.", detail=resolution.held_back_reason
        )
    if resolution.playbook is None:
        raise NotFoundError(f"There is no playbook for the issue key {key!r}.")
    return _playbook(resolution.playbook, catalogue.execute().reviewed)


def _playbook(playbook: Playbook, reviewed: bool) -> PlaybookResponse:
    return PlaybookResponse(
        key=playbook.key,
        label=playbook.label,
        unit=playbook.unit.value,
        owner_team=playbook.owner_team,
        severity=playbook.severity.value,
        meaning=playbook.meaning,
        why=playbook.why,
        steps=list(playbook.steps),
        source=playbook.source.value if playbook.source else None,
        dynamic=playbook.dynamic,
        reviewed=reviewed,
    )
