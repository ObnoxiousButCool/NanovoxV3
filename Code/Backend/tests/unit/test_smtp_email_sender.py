"""`SmtpEmailSender` against a fake `smtplib.SMTP`, not a real mail server."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from types import TracebackType
from typing import ClassVar

import pytest

from domain.errors import DependencyUnavailableError
from infrastructure.email.smtp_email_sender import SmtpEmailSender


class _FakeSmtp:
    """Records what a real `smtplib.SMTP` would have been told to do."""

    instances: ClassVar[list[_FakeSmtp]] = []

    def __init__(self, host: str, port: int, timeout: float) -> None:
        self.host = host
        self.port = port
        self.started_tls = False
        self.logged_in: tuple[str, str] | None = None
        self.sent: EmailMessage | None = None
        _FakeSmtp.instances.append(self)

    def __enter__(self) -> _FakeSmtp:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.logged_in = (username, password)

    def send_message(self, message: EmailMessage) -> None:
        self.sent = message


class _RefusingSmtp(_FakeSmtp):
    def login(self, username: str, password: str) -> None:
        raise smtplib.SMTPAuthenticationError(535, b"bad credentials")


@pytest.fixture(autouse=True)
def _reset_instances() -> None:
    _FakeSmtp.instances.clear()


def _sender(
    monkeypatch: pytest.MonkeyPatch, *, smtp_cls: type[_FakeSmtp] = _FakeSmtp
) -> SmtpEmailSender:
    monkeypatch.setattr(smtplib, "SMTP", smtp_cls)
    return SmtpEmailSender(
        host="smtp.example.com",
        port=587,
        username="bot@example.com",
        password="secret",  # noqa: S106
        from_address="bot@example.com",
    )


async def test_the_code_and_recipient_reach_the_message(monkeypatch: pytest.MonkeyPatch) -> None:
    sender = _sender(monkeypatch)

    await sender.send_otp(to="reader@example.com", code="123456", expires_in_minutes=10)

    sent = _FakeSmtp.instances[0].sent
    assert sent is not None
    assert sent["To"] == "reader@example.com"
    assert "123456" in sent.get_content()
    assert "10 minutes" in sent.get_content()


async def test_it_authenticates_before_sending(monkeypatch: pytest.MonkeyPatch) -> None:
    sender = _sender(monkeypatch)

    await sender.send_otp(to="reader@example.com", code="123456", expires_in_minutes=10)

    smtp = _FakeSmtp.instances[0]
    assert smtp.started_tls
    assert smtp.logged_in == ("bot@example.com", "secret")


async def test_tls_can_be_turned_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(smtplib, "SMTP", _FakeSmtp)
    sender = SmtpEmailSender(
        host="smtp.example.com",
        port=25,
        username="bot@example.com",
        password="secret",  # noqa: S106
        from_address="bot@example.com",
        use_tls=False,
    )

    await sender.send_otp(to="reader@example.com", code="123456", expires_in_minutes=10)

    assert not _FakeSmtp.instances[0].started_tls


async def test_a_failure_to_send_is_a_dependency_unavailable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sender = _sender(monkeypatch, smtp_cls=_RefusingSmtp)

    with pytest.raises(DependencyUnavailableError):
        await sender.send_otp(to="reader@example.com", code="123456", expires_in_minutes=10)
