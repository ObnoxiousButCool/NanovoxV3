"""Sign-in: one shared username and password, checked against the configured pair.

Replaces the email-OTP flow (leadership, 2026-10-08 — see
Documents/notes/Decisions-and-Questions.md): a single credential for the
whole application rather than a per-person allowlist, so there is no
repository here — `Login` is handed the configured username and password
hash directly and has nothing to look up.
"""

from __future__ import annotations

from application.ports.session_issuer import SessionIssuer
from domain.errors import AuthenticationError
from domain.value_objects.password_hash import password_matches

INCORRECT_CREDENTIALS_MESSAGE = "Incorrect username or password."


class Login:
    """Checks a submitted username and password against the configured pair."""

    def __init__(
        self,
        *,
        username: str,
        password_hash: str,
        session_issuer: SessionIssuer,
    ) -> None:
        self._username = username
        self._password_hash = password_hash
        self._session_issuer = session_issuer

    async def execute(self, username: str, password: str) -> str:
        """Returns a bearer session token. Raises `AuthenticationError` otherwise.

        Checks both before raising, rather than short-circuiting on the
        username, so a wrong username and a wrong password answer identically
        — one does not out the other.
        """
        username_correct = username == self._username
        password_correct = password_matches(password, hashed=self._password_hash)
        if not (username_correct and password_correct):
            raise AuthenticationError(INCORRECT_CREDENTIALS_MESSAGE)

        return self._session_issuer.issue(username=self._username)
