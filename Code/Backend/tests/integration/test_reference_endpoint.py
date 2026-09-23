"""`POST /api/v1/reference/import`, with the use case faked out.

An exercise of the real workbook is a manual step, not an automated test —
the workbook itself is git-ignored client material (plan §3.2, decision
D8), so CI has nothing to read.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.ports.reference_repository import ImportCounts
from application.use_cases.import_reference_data import ImportReferenceData, ImportResult
from frameworks_drivers.api.dependencies import get_import_reference_data_use_case

IMPORT_URL = "/api/v1/reference/import"


class _StubUseCase(ImportReferenceData):
    def __init__(self, result: ImportResult) -> None:
        self._result = result

    async def execute(self) -> ImportResult:
        return self._result


def test_import_reports_counts_and_warnings(app: FastAPI) -> None:
    result = ImportResult(
        counts=ImportCounts(
            brokers=30,
            employers=95,
            members=285,
            employer_contacts=101,
            agents=20,
            rules=122,
            touchpoints=12,
        ),
        warnings=("no premium lever found",),
    )
    app.dependency_overrides[get_import_reference_data_use_case] = lambda: _StubUseCase(result)

    with TestClient(app) as client:
        response = client.post(IMPORT_URL)

    assert response.status_code == 200
    body = response.json()
    assert body["counts"]["employers"] == 95
    assert body["counts"]["brokers"] == 30
    assert body["warnings"] == ["no premium lever found"]


def test_import_with_no_warnings_returns_an_empty_list(app: FastAPI) -> None:
    result = ImportResult(
        counts=ImportCounts(
            brokers=1,
            employers=1,
            members=1,
            employer_contacts=1,
            agents=1,
            rules=1,
            touchpoints=1,
        ),
        warnings=(),
    )
    app.dependency_overrides[get_import_reference_data_use_case] = lambda: _StubUseCase(result)

    with TestClient(app) as client:
        response = client.post(IMPORT_URL)

    assert response.json()["warnings"] == []
