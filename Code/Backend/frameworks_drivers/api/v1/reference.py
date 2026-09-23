"""Reference-data import.

Idempotent by design: re-running an import updates existing rows in place
rather than duplicating them, so this is safe to call again after the
workbook is re-issued.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import BaseModel

from frameworks_drivers.api.dependencies import ImportReferenceDataDep

router = APIRouter(prefix="/reference", tags=["reference"])


class ImportCountsResponse(BaseModel):
    brokers: int
    employers: int
    members: int
    employer_contacts: int
    agents: int
    rules: int
    touchpoints: int


class ImportReferenceResponse(BaseModel):
    counts: ImportCountsResponse
    warnings: list[str]


@router.post(
    "/import",
    response_model=ImportReferenceResponse,
    status_code=status.HTTP_200_OK,
    summary="Import the workbook's reference (master-data) sheets",
)
async def import_reference_data(use_case: ImportReferenceDataDep) -> ImportReferenceResponse:
    result = await use_case.execute()
    return ImportReferenceResponse(
        counts=ImportCountsResponse(
            brokers=result.counts.brokers,
            employers=result.counts.employers,
            members=result.counts.members,
            employer_contacts=result.counts.employer_contacts,
            agents=result.counts.agents,
            rules=result.counts.rules,
            touchpoints=result.counts.touchpoints,
        ),
        warnings=list(result.warnings),
    )
