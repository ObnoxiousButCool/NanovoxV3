"""The one `SessionIssuer` adapter: a signed JWT, HS256, email as the subject.

No refresh tokens, no claims beyond `sub`/`iat`/`exp`. A session that expires
asks the reader to sign in again — through the same OTP flow, which is cheap
enough at this traffic that a refresh path would be complexity with nothing
bought for it yet.
"""

from __future__ import annotations

from datetime import timedelta

import jwt

from application.ports.clock import Clock
from application.ports.session_issuer import Session, SessionIssuer
from domain.errors import AuthenticationError

_ALGORITHM = "HS256"


class JwtSessionIssuer(SessionIssuer):
    def __init__(self, *, secret: str, expiry_minutes: int, clock: Clock) -> None:
        self._secret = secret
        self._expiry_minutes = expiry_minutes
        self._clock = clock

    def issue(self, *, email: str) -> str:
        now = self._clock.now()
        payload = {
            "sub": email,
            "iat": now,
            "exp": now + timedelta(minutes=self._expiry_minutes),
        }
        return jwt.encode(payload, self._secret, algorithm=_ALGORITHM)

    def verify(self, token: str) -> Session:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[_ALGORITHM])
        except jwt.PyJWTError as exc:
            raise AuthenticationError("Your session has expired. Sign in again.") from exc
        subject = payload.get("sub")
        if not isinstance(subject, str) or not subject:
            raise AuthenticationError("Your session has expired. Sign in again.")
        return Session(email=subject)
