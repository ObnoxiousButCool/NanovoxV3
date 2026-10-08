"""End-to-end checks on the email-OTP sign-in flow and the session gate.

Deliberately does not use the shared `app`/`client` fixtures from
`tests/conftest.py`: those pre-authenticate every request (see
`TEST_SESSION_EMAIL`) so the hundreds of tests written before sign-in existed
do not all need a token. This file is the one place that removes the
override and exercises the real `require_session` dependency.
"""

from __future__ import annotations

import logging
import re
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from frameworks_drivers.main import create_app
from infrastructure.config.settings import Settings
from tests.support.settings import make_settings

REQUEST_URL = "/api/v1/auth/otp/request"
VERIFY_URL = "/api/v1/auth/otp/verify"
PROVIDERS_URL = "/api/v1/providers"
HEALTH_URL = "/api/v1/health"

APPROVED_EMAIL = "reader@example.com"
_CODE_IN_LOG = re.compile(r"OTP for \S+ is (\d{6})")


@pytest.fixture
def approved_emails_file(tmp_path: Path) -> Path:
    path = tmp_path / "approved_emails.yaml"
    path.write_text(f"emails:\n  - {APPROVED_EMAIL}\n", encoding="utf-8")
    return path


@pytest.fixture
def auth_settings(tmp_path: Path, approved_emails_file: Path, schema_template: Path) -> Settings:
    database = tmp_path / "test.db"
    shutil.copyfile(schema_template, database)
    return make_settings(
        app_env="local",
        database_url=f"sqlite+aiosqlite:///{database.as_posix()}",
        log_enabled=False,
        log_to_console=False,
        log_dir=tmp_path / "logs",
        approved_emails_path=approved_emails_file,
        # Zero, not the real default: several tests here request a code more
        # than once and must not trip the resend guard to see whether this
        # path works.
        otp_resend_cooldown_seconds=0,
    )


@pytest.fixture
def auth_client(auth_settings: Settings) -> Iterator[TestClient]:
    """The real app, with no `require_session` override — unlike `tests/conftest.py`'s."""
    with TestClient(create_app(auth_settings)) as client:
        yield client


def _requested_code(caplog: pytest.LogCaptureFixture, client: TestClient, email: str) -> str:
    caplog.set_level(logging.INFO, logger="infrastructure.email.console_email_sender")
    caplog.clear()
    response = client.post(REQUEST_URL, json={"email": email})
    assert response.status_code == 200
    match = _CODE_IN_LOG.search(caplog.text)
    assert match, f"no OTP logged for {email}; log was: {caplog.text!r}"
    return match.group(1)


def test_health_needs_no_session(auth_client: TestClient) -> None:
    assert auth_client.get(HEALTH_URL).status_code == 200


def test_an_unauthenticated_request_is_rejected(auth_client: TestClient) -> None:
    response = auth_client.get(PROVIDERS_URL)

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_error"


def test_requesting_a_code_answers_the_same_for_an_unapproved_address(
    auth_client: TestClient,
) -> None:
    approved = auth_client.post(REQUEST_URL, json={"email": APPROVED_EMAIL})
    unapproved = auth_client.post(REQUEST_URL, json={"email": "stranger@example.com"})

    assert approved.status_code == unapproved.status_code == 200
    assert approved.json() == unapproved.json()


def test_the_full_sign_in_round_trip(
    auth_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    code = _requested_code(caplog, auth_client, APPROVED_EMAIL)

    verified = auth_client.post(VERIFY_URL, json={"email": APPROVED_EMAIL, "code": code})
    assert verified.status_code == 200
    token = verified.json()["token"]

    authed = auth_client.get(PROVIDERS_URL, headers={"Authorization": f"Bearer {token}"})
    assert authed.status_code == 200


def test_a_malformed_authorization_header_is_rejected(auth_client: TestClient) -> None:
    response = auth_client.get(PROVIDERS_URL, headers={"Authorization": "not-a-bearer-token"})

    assert response.status_code == 401


def test_a_code_cannot_be_redeemed_twice(
    auth_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    code = _requested_code(caplog, auth_client, APPROVED_EMAIL)
    first = auth_client.post(VERIFY_URL, json={"email": APPROVED_EMAIL, "code": code})
    assert first.status_code == 200

    second = auth_client.post(VERIFY_URL, json={"email": APPROVED_EMAIL, "code": code})

    assert second.status_code == 401


def test_the_wrong_code_is_rejected(
    auth_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    _requested_code(caplog, auth_client, APPROVED_EMAIL)

    response = auth_client.post(VERIFY_URL, json={"email": APPROVED_EMAIL, "code": "000000"})

    assert response.status_code == 401


def test_a_malformed_email_is_rejected_before_any_code_is_sent(auth_client: TestClient) -> None:
    response = auth_client.post(REQUEST_URL, json={"email": "not-an-email"})

    assert response.status_code == 422


def test_a_non_six_digit_code_is_rejected_before_any_lookup(auth_client: TestClient) -> None:
    response = auth_client.post(VERIFY_URL, json={"email": APPROVED_EMAIL, "code": "abc"})

    assert response.status_code == 422
