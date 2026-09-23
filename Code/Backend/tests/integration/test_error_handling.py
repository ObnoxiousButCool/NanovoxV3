"""Every error the API can produce leaves in the same RFC 9457 shape."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from domain.errors import ConfigurationError, NotFoundError
from frameworks_drivers.api.errors import PROBLEM_MEDIA_TYPE
from infrastructure.logging.correlation import CORRELATION_ID_HEADER


def test_an_exposed_domain_error_carries_its_own_message(app: FastAPI) -> None:
    @app.get("/api/v1/_test/not-found")
    async def _raise_not_found() -> None:
        raise NotFoundError("no such call", detail="C-9999")

    with TestClient(app) as client:
        response = client.get("/api/v1/_test/not-found")

    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "not_found"
    assert body["title"] == "no such call"
    assert body["detail"] == "C-9999"
    assert body["correlation_id"] == response.headers[CORRELATION_ID_HEADER]


def test_an_unexposed_domain_error_hides_its_detail(app: FastAPI) -> None:
    @app.get("/api/v1/_test/config-error")
    async def _raise_configuration_error() -> None:
        raise ConfigurationError("DATABASE_URL is wrong", detail="connection string leaked here")

    with TestClient(app) as client:
        response = client.get("/api/v1/_test/config-error")

    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "configuration_error"
    assert "connection string" not in body["detail"]
    assert "correlation ID" in body["detail"]


def test_a_missing_required_query_parameter_returns_a_problem_document(app: FastAPI) -> None:
    @app.get("/api/v1/_test/requires-a-parameter")
    async def _requires_a_parameter(count: int) -> dict[str, int]:
        return {"count": count}

    with TestClient(app) as client:
        response = client.get("/api/v1/_test/requires-a-parameter")

    assert response.status_code == 422
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    body = response.json()
    assert body["code"] == "request_validation_error"
    assert "count" in (body["detail"] or "")
