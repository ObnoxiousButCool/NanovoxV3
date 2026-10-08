"""End-to-end checks on sign-in and the session gate.

Deliberately does not use the shared `app`/`client` fixtures from
`tests/conftest.py`: those pre-authenticate every request (see
`TEST_SESSION_USERNAME`) so the hundreds of tests written before sign-in
existed do not all need a token. This file is the one place that removes
the override and exercises the real `require_session` dependency.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from domain.value_objects.password_hash import hash_password
from frameworks_drivers.main import create_app
from infrastructure.config.settings import Settings
from tests.support.settings import make_settings

LOGIN_URL = "/api/v1/auth/login"
PROVIDERS_URL = "/api/v1/providers"
HEALTH_URL = "/api/v1/health"

USERNAME = "Technossus"
PASSWORD = "Tech@2026"  # noqa: S105


@pytest.fixture
def auth_settings(tmp_path: Path, schema_template: Path) -> Settings:
    database = tmp_path / "test.db"
    shutil.copyfile(schema_template, database)
    return make_settings(
        app_env="local",
        database_url=f"sqlite+aiosqlite:///{database.as_posix()}",
        log_enabled=False,
        log_to_console=False,
        log_dir=tmp_path / "logs",
        auth_username=USERNAME,
        auth_password_hash=hash_password(PASSWORD),
    )


@pytest.fixture
def auth_client(auth_settings: Settings) -> Iterator[TestClient]:
    """The real app, with no `require_session` override — unlike `tests/conftest.py`'s."""
    with TestClient(create_app(auth_settings)) as client:
        yield client


def test_health_needs_no_session(auth_client: TestClient) -> None:
    assert auth_client.get(HEALTH_URL).status_code == 200


def test_an_unauthenticated_request_is_rejected(auth_client: TestClient) -> None:
    response = auth_client.get(PROVIDERS_URL)

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_error"


def test_the_full_sign_in_round_trip(auth_client: TestClient) -> None:
    logged_in = auth_client.post(LOGIN_URL, json={"username": USERNAME, "password": PASSWORD})
    assert logged_in.status_code == 200
    token = logged_in.json()["token"]

    authed = auth_client.get(PROVIDERS_URL, headers={"Authorization": f"Bearer {token}"})
    assert authed.status_code == 200


def test_a_malformed_authorization_header_is_rejected(auth_client: TestClient) -> None:
    response = auth_client.get(PROVIDERS_URL, headers={"Authorization": "not-a-bearer-token"})

    assert response.status_code == 401


def test_the_wrong_password_is_rejected(auth_client: TestClient) -> None:
    response = auth_client.post(LOGIN_URL, json={"username": USERNAME, "password": "wrong"})

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_error"


def test_the_wrong_username_is_rejected(auth_client: TestClient) -> None:
    response = auth_client.post(LOGIN_URL, json={"username": "someone-else", "password": PASSWORD})

    assert response.status_code == 401


def test_a_token_from_a_failed_login_does_not_authenticate_anything(
    auth_client: TestClient,
) -> None:
    failed = auth_client.post(LOGIN_URL, json={"username": USERNAME, "password": "wrong"})
    assert failed.status_code == 401

    # There is no token to carry forward — confirm the gate still rejects
    # a request with none, rather than this test passing by accident.
    response = auth_client.get(PROVIDERS_URL)
    assert response.status_code == 401
