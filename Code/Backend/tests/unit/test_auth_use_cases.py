"""`Login` against a fake `SessionIssuer`."""

from __future__ import annotations

import pytest

from application.ports.session_issuer import Session, SessionIssuer
from application.use_cases.auth import INCORRECT_CREDENTIALS_MESSAGE, Login
from domain.errors import AuthenticationError
from domain.value_objects.password_hash import hash_password

_USERNAME = "Technossus"
_PASSWORD = "Tech@2026"  # noqa: S105


class _FakeSessionIssuer(SessionIssuer):
    def __init__(self) -> None:
        self.issued_for: list[str] = []

    def issue(self, *, username: str) -> str:
        self.issued_for.append(username)
        return f"token-for-{username}"

    def verify(self, token: str) -> Session:  # pragma: no cover - unused here
        raise NotImplementedError


def _login(session_issuer: _FakeSessionIssuer | None = None) -> Login:
    return Login(
        username=_USERNAME,
        password_hash=hash_password(_PASSWORD),
        session_issuer=session_issuer or _FakeSessionIssuer(),
    )


async def test_the_right_username_and_password_issue_a_session() -> None:
    issuer = _FakeSessionIssuer()

    token = await _login(issuer).execute(_USERNAME, _PASSWORD)

    assert token == f"token-for-{_USERNAME}"
    assert issuer.issued_for == [_USERNAME]


async def test_a_wrong_password_is_rejected() -> None:
    with pytest.raises(AuthenticationError, match=INCORRECT_CREDENTIALS_MESSAGE):
        await _login().execute(_USERNAME, "wrong-password")


async def test_a_wrong_username_is_rejected() -> None:
    with pytest.raises(AuthenticationError, match=INCORRECT_CREDENTIALS_MESSAGE):
        await _login().execute("someone-else", _PASSWORD)


async def test_both_wrong_gives_the_same_message_as_one_wrong() -> None:
    # Nothing in the error should let a caller tell "the username was right
    # but the password was not" from "neither was."
    with pytest.raises(AuthenticationError, match=INCORRECT_CREDENTIALS_MESSAGE):
        await _login().execute("someone-else", "wrong-password")


async def test_a_wrong_password_issues_no_session() -> None:
    issuer = _FakeSessionIssuer()

    with pytest.raises(AuthenticationError):
        await _login(issuer).execute(_USERNAME, "wrong-password")

    assert issuer.issued_for == []


async def test_matching_is_case_sensitive_on_the_password() -> None:
    # Leadership's password is a fixed string, not an email address — there
    # is no normalisation rule to apply here, unlike the allowlist this
    # replaces.
    with pytest.raises(AuthenticationError):
        await _login().execute(_USERNAME, _PASSWORD.lower())
