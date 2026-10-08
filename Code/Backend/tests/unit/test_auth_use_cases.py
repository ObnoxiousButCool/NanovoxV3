"""`RequestOtp` and `VerifyOtp` against fakes for every port.

The fakes are small, honest implementations of each port's contract — an
in-memory list standing in for the table, a dict standing in for an inbox —
rather than mocks that only assert *what was called*. That is what lets a
test like "a resend within the cooldown sends nothing" check the actual
outcome (no second email) instead of a call count that could be satisfied by
the wrong code path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from application.ports.clock import Clock
from application.ports.email_sender import EmailSender
from application.ports.otp_repository import OtpRepository, OtpRequestRecord
from application.ports.session_issuer import Session, SessionIssuer
from application.use_cases.auth import INVALID_CODE_MESSAGE, RequestOtp, VerifyOtp
from domain.errors import AuthenticationError
from domain.value_objects.approved_emails import approved_emails_from
from domain.value_objects.otp_code import hash_otp_code

_NOW = datetime(2026, 10, 8, 9, 0, tzinfo=UTC)
_APPROVED = "reader@example.com"


class _MutableClock(Clock):
    def __init__(self, now: datetime) -> None:
        self.current = now

    def now(self) -> datetime:
        return self.current


@dataclass
class _SentEmail:
    to: str
    code: str
    expires_in_minutes: int


class _FakeEmailSender(EmailSender):
    def __init__(self) -> None:
        self.sent: list[_SentEmail] = []

    async def send_otp(self, *, to: str, code: str, expires_in_minutes: int) -> None:
        self.sent.append(_SentEmail(to, code, expires_in_minutes))


@dataclass
class _Row:
    id: int
    email: str
    code_hash: str
    created_at: datetime
    expires_at: datetime
    attempts: int = 0
    consumed_at: datetime | None = None


class _FakeOtpRepository(OtpRepository):
    """An in-memory stand-in with the same "never overwrite" shape as the
    real table — `create` always appends, `latest_for` reads the newest."""

    def __init__(self) -> None:
        self._rows: list[_Row] = []
        self._next_id = 1

    async def create(
        self, *, email: str, code_hash: str, created_at: datetime, expires_at: datetime
    ) -> OtpRequestRecord:
        row = _Row(
            id=self._next_id,
            email=email,
            code_hash=code_hash,
            created_at=created_at,
            expires_at=expires_at,
        )
        self._next_id += 1
        self._rows.append(row)
        return _to_record(row)

    async def latest_for(self, email: str) -> OtpRequestRecord | None:
        matching = [row for row in self._rows if row.email == email]
        if not matching:
            return None
        newest = max(matching, key=lambda row: (row.created_at, row.id))
        return _to_record(newest)

    async def record_attempt(self, request_id: int) -> int:
        row = self._row(request_id)
        row.attempts += 1
        return row.attempts

    async def consume(self, request_id: int, *, at: datetime) -> None:
        self._row(request_id).consumed_at = at

    def _row(self, request_id: int) -> _Row:
        return next(row for row in self._rows if row.id == request_id)


def _to_record(row: _Row) -> OtpRequestRecord:
    return OtpRequestRecord(
        id=row.id,
        email=row.email,
        code_hash=row.code_hash,
        created_at=row.created_at,
        expires_at=row.expires_at,
        attempts=row.attempts,
        consumed_at=row.consumed_at,
    )


class _FakeSessionIssuer(SessionIssuer):
    def issue(self, *, email: str) -> str:
        return f"token-for-{email}"

    def verify(self, token: str) -> Session:  # pragma: no cover - unused here
        raise NotImplementedError


@pytest.fixture
def clock() -> _MutableClock:
    return _MutableClock(_NOW)


@pytest.fixture
def otp_repository() -> _FakeOtpRepository:
    return _FakeOtpRepository()


@pytest.fixture
def email_sender() -> _FakeEmailSender:
    return _FakeEmailSender()


def _request_otp(
    otp_repository: _FakeOtpRepository,
    email_sender: _FakeEmailSender,
    clock: _MutableClock,
    *,
    expiry_minutes: int = 10,
    resend_cooldown_seconds: int = 30,
) -> RequestOtp:
    return RequestOtp(
        approved_emails=approved_emails_from([_APPROVED]),
        otp_repository=otp_repository,
        email_sender=email_sender,
        clock=clock,
        expiry_minutes=expiry_minutes,
        resend_cooldown_seconds=resend_cooldown_seconds,
    )


class TestRequestOtp:
    async def test_an_approved_address_is_sent_a_code(
        self,
        otp_repository: _FakeOtpRepository,
        email_sender: _FakeEmailSender,
        clock: _MutableClock,
    ) -> None:
        use_case = _request_otp(otp_repository, email_sender, clock)

        await use_case.execute(_APPROVED)

        assert len(email_sender.sent) == 1
        assert email_sender.sent[0].to == _APPROVED
        assert len(email_sender.sent[0].code) == 6

    async def test_the_sent_code_is_the_one_stored_hashed(
        self,
        otp_repository: _FakeOtpRepository,
        email_sender: _FakeEmailSender,
        clock: _MutableClock,
    ) -> None:
        use_case = _request_otp(otp_repository, email_sender, clock)

        await use_case.execute(_APPROVED)

        stored = await otp_repository.latest_for(_APPROVED)
        assert stored is not None
        assert stored.code_hash == hash_otp_code(email_sender.sent[0].code)

    async def test_matching_is_case_and_whitespace_insensitive(
        self,
        otp_repository: _FakeOtpRepository,
        email_sender: _FakeEmailSender,
        clock: _MutableClock,
    ) -> None:
        use_case = _request_otp(otp_repository, email_sender, clock)

        await use_case.execute("  Reader@Example.COM  ")

        assert email_sender.sent[0].to == _APPROVED

    async def test_an_unapproved_address_is_sent_nothing(
        self,
        otp_repository: _FakeOtpRepository,
        email_sender: _FakeEmailSender,
        clock: _MutableClock,
    ) -> None:
        use_case = _request_otp(otp_repository, email_sender, clock)

        await use_case.execute("stranger@example.com")

        assert email_sender.sent == []
        assert await otp_repository.latest_for("stranger@example.com") is None

    async def test_an_unapproved_address_does_not_raise(
        self,
        otp_repository: _FakeOtpRepository,
        email_sender: _FakeEmailSender,
        clock: _MutableClock,
    ) -> None:
        # The whole point: a prober cannot tell "not approved" from "approved,
        # code sent" by whether this call raises.
        use_case = _request_otp(otp_repository, email_sender, clock)

        await use_case.execute("stranger@example.com")  # must not raise

    async def test_a_resend_within_the_cooldown_sends_nothing(
        self,
        otp_repository: _FakeOtpRepository,
        email_sender: _FakeEmailSender,
        clock: _MutableClock,
    ) -> None:
        use_case = _request_otp(otp_repository, email_sender, clock, resend_cooldown_seconds=30)

        await use_case.execute(_APPROVED)
        clock.current += timedelta(seconds=10)
        await use_case.execute(_APPROVED)

        assert len(email_sender.sent) == 1

    async def test_a_resend_after_the_cooldown_sends_a_new_code(
        self,
        otp_repository: _FakeOtpRepository,
        email_sender: _FakeEmailSender,
        clock: _MutableClock,
    ) -> None:
        use_case = _request_otp(otp_repository, email_sender, clock, resend_cooldown_seconds=30)

        await use_case.execute(_APPROVED)
        clock.current += timedelta(seconds=31)
        await use_case.execute(_APPROVED)

        assert len(email_sender.sent) == 2
        assert email_sender.sent[0].code != email_sender.sent[1].code


def _verify_otp(
    otp_repository: _FakeOtpRepository, clock: _MutableClock, *, max_attempts: int = 5
) -> VerifyOtp:
    return VerifyOtp(
        otp_repository=otp_repository,
        session_issuer=_FakeSessionIssuer(),
        clock=clock,
        max_attempts=max_attempts,
    )


class TestVerifyOtp:
    async def test_the_right_code_issues_a_session(
        self,
        otp_repository: _FakeOtpRepository,
        email_sender: _FakeEmailSender,
        clock: _MutableClock,
    ) -> None:
        await _request_otp(otp_repository, email_sender, clock).execute(_APPROVED)
        code = email_sender.sent[0].code

        token = await _verify_otp(otp_repository, clock).execute(_APPROVED, code)

        assert token == f"token-for-{_APPROVED}"

    async def test_the_right_code_consumes_the_request(
        self,
        otp_repository: _FakeOtpRepository,
        email_sender: _FakeEmailSender,
        clock: _MutableClock,
    ) -> None:
        await _request_otp(otp_repository, email_sender, clock).execute(_APPROVED)
        code = email_sender.sent[0].code

        await _verify_otp(otp_repository, clock).execute(_APPROVED, code)

        stored = await otp_repository.latest_for(_APPROVED)
        assert stored is not None
        assert stored.consumed_at == clock.current

    async def test_a_consumed_code_cannot_be_replayed(
        self,
        otp_repository: _FakeOtpRepository,
        email_sender: _FakeEmailSender,
        clock: _MutableClock,
    ) -> None:
        await _request_otp(otp_repository, email_sender, clock).execute(_APPROVED)
        code = email_sender.sent[0].code
        verify = _verify_otp(otp_repository, clock)
        await verify.execute(_APPROVED, code)

        with pytest.raises(AuthenticationError, match=INVALID_CODE_MESSAGE):
            await verify.execute(_APPROVED, code)

    async def test_a_wrong_code_is_rejected(
        self,
        otp_repository: _FakeOtpRepository,
        email_sender: _FakeEmailSender,
        clock: _MutableClock,
    ) -> None:
        await _request_otp(otp_repository, email_sender, clock).execute(_APPROVED)

        with pytest.raises(AuthenticationError, match=INVALID_CODE_MESSAGE):
            await _verify_otp(otp_repository, clock).execute(_APPROVED, "000000")

    async def test_a_wrong_code_counts_as_an_attempt(
        self,
        otp_repository: _FakeOtpRepository,
        email_sender: _FakeEmailSender,
        clock: _MutableClock,
    ) -> None:
        await _request_otp(otp_repository, email_sender, clock).execute(_APPROVED)
        verify = _verify_otp(otp_repository, clock)

        with pytest.raises(AuthenticationError):
            await verify.execute(_APPROVED, "000000")

        stored = await otp_repository.latest_for(_APPROVED)
        assert stored is not None
        assert stored.attempts == 1

    async def test_too_many_attempts_rejects_even_the_right_code(
        self,
        otp_repository: _FakeOtpRepository,
        email_sender: _FakeEmailSender,
        clock: _MutableClock,
    ) -> None:
        await _request_otp(otp_repository, email_sender, clock).execute(_APPROVED)
        code = email_sender.sent[0].code
        verify = _verify_otp(otp_repository, clock, max_attempts=2)
        for _ in range(2):
            with pytest.raises(AuthenticationError):
                await verify.execute(_APPROVED, "000000")

        with pytest.raises(AuthenticationError, match=INVALID_CODE_MESSAGE):
            await verify.execute(_APPROVED, code)

    async def test_an_expired_code_is_rejected(
        self,
        otp_repository: _FakeOtpRepository,
        email_sender: _FakeEmailSender,
        clock: _MutableClock,
    ) -> None:
        await _request_otp(otp_repository, email_sender, clock, expiry_minutes=10).execute(
            _APPROVED
        )
        code = email_sender.sent[0].code
        clock.current += timedelta(minutes=10)

        with pytest.raises(AuthenticationError, match=INVALID_CODE_MESSAGE):
            await _verify_otp(otp_repository, clock).execute(_APPROVED, code)

    async def test_no_code_ever_requested_is_rejected_the_same_way(
        self, otp_repository: _FakeOtpRepository, clock: _MutableClock
    ) -> None:
        # Same message as a wrong or expired code — see the module docstring
        # on `application.use_cases.auth` on why this must not be distinguishable.
        with pytest.raises(AuthenticationError, match=INVALID_CODE_MESSAGE):
            await _verify_otp(otp_repository, clock).execute("nobody@example.com", "123456")
