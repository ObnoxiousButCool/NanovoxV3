"""The real `EmailSender`: one account's SMTP credentials, stdlib only.

No email SDK is added for this — `smtplib` and `email.message` already do
the whole job, and the provider behind "an SMTP account" is deliberately
left open: a company mailbox, SendGrid's SMTP relay, Azure Communication
Services' SMTP endpoint, anything that takes a host, a port and a login all
speak the same protocol this adapter does. Choosing one is a credentials
decision (`SMTP_*` in `.env`), not a code change.

`smtplib` is synchronous; `asyncio.to_thread` keeps it off the event loop
the same way `infrastructure.persistence.backup` already does for a blocking
file copy.
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from application.ports.email_sender import EmailSender
from domain.errors import DependencyUnavailableError

logger = logging.getLogger(__name__)


class SmtpEmailSender(EmailSender):
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        from_address: str,
        use_tls: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from_address = from_address
        self._use_tls = use_tls

    async def send_otp(self, *, to: str, code: str, expires_in_minutes: int) -> None:
        message = EmailMessage()
        message["Subject"] = "Your NanoVox Insights sign-in code"
        message["From"] = self._from_address
        message["To"] = to
        message.set_content(
            f"Your sign-in code is {code}.\n\n"
            f"It expires in {expires_in_minutes} minutes. If you did not request "
            "this, you can ignore this email."
        )
        try:
            await asyncio.to_thread(self._send_sync, message)
        except (smtplib.SMTPException, OSError) as exc:
            raise DependencyUnavailableError(
                "Could not send the sign-in email.", detail=str(exc)
            ) from exc

    def _send_sync(self, message: EmailMessage) -> None:
        with smtplib.SMTP(self._host, self._port, timeout=10) as client:
            if self._use_tls:
                client.starttls()
            client.login(self._username, self._password)
            client.send_message(message)
