"""Email-OTP sign-in: request a code, then redeem it for a session.

Two use cases over one small state machine (unissued -> issued -> consumed,
or issued -> expired). Both are deliberately silent about *why* a request
failed in ways that would let a caller enumerate who is approved or how many
codes exist: `RequestOtp` answers the same way whether or not the address is
on the allowlist, and `VerifyOtp` gives one message ("that code is not
valid") whether no code was ever issued, the code was wrong, or it already
expired.
"""

from __future__ import annotations

from datetime import timedelta

from application.ports.approved_emails_repository import ApprovedEmailsRepository
from application.ports.clock import Clock
from application.ports.email_sender import EmailSender
from application.ports.otp_repository import OtpRepository
from application.ports.session_issuer import SessionIssuer
from domain.errors import AuthenticationError
from domain.value_objects.otp_code import generate_otp_code, hash_otp_code, otp_code_matches

INVALID_CODE_MESSAGE = "That code is not valid. Request a new one."


def _normalise(email: str) -> str:
    return email.strip().lower()


class RequestOtp:
    """Sends a fresh code to an approved address, if it is allowed one right now."""

    def __init__(
        self,
        approved_emails: ApprovedEmailsRepository,
        otp_repository: OtpRepository,
        email_sender: EmailSender,
        clock: Clock,
        *,
        expiry_minutes: int,
        resend_cooldown_seconds: int,
    ) -> None:
        self._approved_emails = approved_emails
        self._otp_repository = otp_repository
        self._email_sender = email_sender
        self._clock = clock
        self._expiry_minutes = expiry_minutes
        self._resend_cooldown_seconds = resend_cooldown_seconds

    async def execute(self, email: str) -> None:
        """Always returns, never raises for a bad or unapproved address.

        The caller (the router) answers every call with the same generic
        "if that address is approved, a code is on its way" — a 404 or a
        422 here would be the difference a probing caller is looking for.
        """
        normalised = _normalise(email)
        if not await self._approved_emails.is_approved(normalised):
            return

        now = self._clock.now()
        latest = await self._otp_repository.latest_for(normalised)
        if latest is not None:
            age = (now - latest.created_at).total_seconds()
            if age < self._resend_cooldown_seconds:
                return

        code = generate_otp_code()
        await self._otp_repository.create(
            email=normalised,
            code_hash=hash_otp_code(code),
            created_at=now,
            expires_at=now + timedelta(minutes=self._expiry_minutes),
        )
        await self._email_sender.send_otp(
            to=normalised, code=code, expires_in_minutes=self._expiry_minutes
        )


class VerifyOtp:
    """Redeems a code for a session, if it is the current, unused, unexpired one."""

    def __init__(
        self,
        otp_repository: OtpRepository,
        session_issuer: SessionIssuer,
        clock: Clock,
        *,
        max_attempts: int,
    ) -> None:
        self._otp_repository = otp_repository
        self._session_issuer = session_issuer
        self._clock = clock
        self._max_attempts = max_attempts

    async def execute(self, email: str, code: str) -> str:
        """Returns a bearer session token. Raises `AuthenticationError` otherwise."""
        normalised = _normalise(email)
        latest = await self._otp_repository.latest_for(normalised)
        if latest is None or latest.consumed_at is not None:
            raise AuthenticationError(INVALID_CODE_MESSAGE)

        now = self._clock.now()
        if now >= latest.expires_at:
            raise AuthenticationError(INVALID_CODE_MESSAGE)
        if latest.attempts >= self._max_attempts:
            raise AuthenticationError(INVALID_CODE_MESSAGE)

        if not otp_code_matches(code, hashed=latest.code_hash):
            await self._otp_repository.record_attempt(latest.id)
            raise AuthenticationError(INVALID_CODE_MESSAGE)

        await self._otp_repository.consume(latest.id, at=now)
        return self._session_issuer.issue(email=normalised)
