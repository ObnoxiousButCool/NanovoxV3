"""`POST /api/v1/ingest/transcripts`, with the use case stubbed out."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.ports.call_repository import IngestCounts
from application.use_cases.ingest_transcripts import IngestTranscripts
from frameworks_drivers.api.dependencies import get_ingest_transcripts_use_case

INGEST_URL = "/api/v1/ingest/transcripts"


class _StubUseCase(IngestTranscripts):
    def __init__(self, counts: IngestCounts) -> None:
        self._counts = counts

    async def execute(self) -> IngestCounts:
        return self._counts


def test_ingest_reports_counts(app: FastAPI) -> None:
    counts = IngestCounts(
        total=100, resolved=97, caller_unresolved=3, agent_unknown=0, speaker_unresolved=0
    )
    app.dependency_overrides[get_ingest_transcripts_use_case] = lambda: _StubUseCase(counts)

    with TestClient(app) as client:
        response = client.post(INGEST_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 100
    assert body["resolved"] == 97
    assert body["caller_unresolved"] == 3
