"""Extraction runs over the corpus (plan §8 Phase 3, "run orchestration").

Starting or resuming a run returns as soon as the work has begun in the
background of this process (`infrastructure.runner.background_runner`) —
the caller polls the status endpoint for progress rather than holding the
request open for however long the whole corpus takes.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import BaseModel

from domain.errors import NotFoundError
from frameworks_drivers.api.dependencies import RunExtractionOverCorpusDep

router = APIRouter(prefix="/runs", tags=["runs"])


class StartRunRequest(BaseModel):
    provider: str | None = None
    model: str | None = None


class StartRunResponse(BaseModel):
    id: int


class RunProgressResponse(BaseModel):
    total: int
    completed: int
    failed: int
    skipped: int
    cancelled: int
    running: int
    pending: int
    percent_complete: float


class RunStatusResponse(BaseModel):
    id: int
    status: str
    provider: str
    model: str
    progress: RunProgressResponse


@router.post(
    "",
    response_model=StartRunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a new run of the extraction pipeline over every ingested call",
)
async def start_run(
    body: StartRunRequest, use_case: RunExtractionOverCorpusDep
) -> StartRunResponse:
    run_id = await use_case.start(provider_name=body.provider, model=body.model)
    return StartRunResponse(id=run_id)


@router.get(
    "/{run_id}",
    response_model=RunStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="A run's status and how far it has got",
)
async def get_run(run_id: int, use_case: RunExtractionOverCorpusDep) -> RunStatusResponse:
    view = await use_case.status(run_id)
    if view is None:
        raise NotFoundError(f"There is no run {run_id}.")
    return RunStatusResponse(
        id=view.record.id,
        status=view.record.status.value,
        provider=view.record.provider,
        model=view.record.model,
        progress=RunProgressResponse(
            total=view.progress.total,
            completed=view.progress.completed,
            failed=view.progress.failed,
            skipped=view.progress.skipped,
            cancelled=view.progress.cancelled,
            running=view.progress.running,
            pending=view.progress.pending,
            percent_complete=view.progress.percent_complete,
        ),
    )


@router.post(
    "/{run_id}/resume",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Re-enter a run that stopped before every call finished",
)
async def resume_run(run_id: int, use_case: RunExtractionOverCorpusDep) -> None:
    await use_case.resume(run_id)


@router.post(
    "/{run_id}/cancel",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ask a run to stop after its current call",
)
async def cancel_run(run_id: int, use_case: RunExtractionOverCorpusDep) -> None:
    await use_case.cancel(run_id)
