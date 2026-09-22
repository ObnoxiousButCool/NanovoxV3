"""Transcript ingestion.

Idempotent: re-running an ingest updates existing calls in place rather
than duplicating them.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import BaseModel

from frameworks_drivers.api.dependencies import IngestTranscriptsDep

router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestCountsResponse(BaseModel):
    total: int
    resolved: int
    caller_unresolved: int
    agent_unknown: int
    speaker_unresolved: int


@router.post(
    "/transcripts",
    response_model=IngestCountsResponse,
    status_code=status.HTTP_200_OK,
    summary="Ingest every call from the configured transcript source",
)
async def ingest_transcripts(use_case: IngestTranscriptsDep) -> IngestCountsResponse:
    counts = await use_case.execute()
    return IngestCountsResponse(
        total=counts.total,
        resolved=counts.resolved,
        caller_unresolved=counts.caller_unresolved,
        agent_unknown=counts.agent_unknown,
        speaker_unresolved=counts.speaker_unresolved,
    )
