"""Port for turning a verified sign-in into a bearer session, and back.

A port rather than a direct `PyJWT` call from the use case: the application
layer asks for a session over an identity and a session's identity back, not
for a JWT specifically — see `domain.errors` on the same principle for
errors. The only adapter today signs a JWT; nothing above this port would
need to change if that became an opaque token in a session table instead.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Session:
    username: str


class SessionIssuer(ABC):
    """Issues and verifies bearer sessions."""

    @abstractmethod
    def issue(self, *, username: str) -> str:
        """A bearer token asserting this user signed in, valid for the
        issuer's configured lifetime."""

    @abstractmethod
    def verify(self, token: str) -> Session:
        """The session a token asserts. Raises `AuthenticationError` if the
        token is missing, malformed, expired or signed by someone else."""
