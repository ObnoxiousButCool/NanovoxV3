"""`/api/v1/runs`, with the use case stubbed out."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.ports.run_repository import RunRecord
from application.use_cases.run_extraction_over_corpus import RunExtractionOverCorpus, RunStatusView
from domain.errors import NotFoundError
from domain.run_progress import summarise
from domain.value_objects.run_status import RunItemStatus, RunStatus
from frameworks_drivers.api.dependencies import get_run_extraction_over_corpus_use_case

RUNS_URL = "/api/v1/runs"

_CREATED_AT = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)


class _StubUseCase(RunExtractionOverCorpus):
    def __init__(self, *, started_id: int = 1, view: RunStatusView | None = None) -> None:
        self._started_id = started_id
        self._view = view
        self.resumed: list[int] = []
        self.cancelled: list[int] = []

    async def start(self, *, provider_name: str | None = None, model: str | None = None) -> int:
        return self._started_id

    async def status(self, run_id: int) -> RunStatusView | None:
        return self._view

    async def resume(self, run_id: int) -> None:
        self.resumed.append(run_id)

    async def cancel(self, run_id: int) -> None:
        self.cancelled.append(run_id)


def _view(*, status: RunStatus = RunStatus.RUNNING) -> RunStatusView:
    record = RunRecord(
        id=7,
        status=status,
        provider="ollama",
        model="qwen2.5:7b-instruct",
        created_at=_CREATED_AT,
        started_at=_CREATED_AT,
        finished_at=None,
    )
    progress = summarise([RunItemStatus.COMPLETED, RunItemStatus.PENDING])
    return RunStatusView(record=record, progress=progress)


def test_starting_a_run_returns_its_id(app: FastAPI) -> None:
    app.dependency_overrides[get_run_extraction_over_corpus_use_case] = lambda: _StubUseCase(
        started_id=42
    )

    with TestClient(app) as client:
        response = client.post(RUNS_URL, json={})

    assert response.status_code == 201
    assert response.json() == {"id": 42}


def test_getting_a_runs_status_reports_its_progress(app: FastAPI) -> None:
    app.dependency_overrides[get_run_extraction_over_corpus_use_case] = lambda: _StubUseCase(
        view=_view()
    )

    with TestClient(app) as client:
        response = client.get(f"{RUNS_URL}/7")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == 7
    assert body["status"] == "RUNNING"
    assert body["progress"]["total"] == 2
    assert body["progress"]["completed"] == 1


def test_getting_an_unknown_runs_status_is_404(app: FastAPI) -> None:
    app.dependency_overrides[get_run_extraction_over_corpus_use_case] = lambda: _StubUseCase(
        view=None
    )

    with TestClient(app) as client:
        response = client.get(f"{RUNS_URL}/999")

    assert response.status_code == 404


def test_resuming_a_run_delegates_to_the_use_case(app: FastAPI) -> None:
    stub = _StubUseCase()
    app.dependency_overrides[get_run_extraction_over_corpus_use_case] = lambda: stub

    with TestClient(app) as client:
        response = client.post(f"{RUNS_URL}/7/resume")

    assert response.status_code == 202
    assert stub.resumed == [7]


def test_cancelling_a_run_delegates_to_the_use_case(app: FastAPI) -> None:
    stub = _StubUseCase()
    app.dependency_overrides[get_run_extraction_over_corpus_use_case] = lambda: stub

    with TestClient(app) as client:
        response = client.post(f"{RUNS_URL}/7/cancel")

    assert response.status_code == 202
    assert stub.cancelled == [7]


class _NotFoundUseCase(RunExtractionOverCorpus):
    def __init__(self) -> None:
        pass

    async def resume(self, run_id: int) -> None:
        raise NotFoundError(f"There is no run {run_id}.")


def test_resuming_an_unknown_run_is_404(app: FastAPI) -> None:
    app.dependency_overrides[get_run_extraction_over_corpus_use_case] = _NotFoundUseCase

    with TestClient(app) as client:
        response = client.post(f"{RUNS_URL}/999/resume")

    assert response.status_code == 404
