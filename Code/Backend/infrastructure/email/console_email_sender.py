"""The development `EmailSender`: logs the code instead of mailing it.

Lets the whole OTP flow be built, run and demonstrated before a real mail
account is chosen — `EMAIL_BACKEND=console` (the default) prints the code
where whoever is testing the login page is already looking, so no inbox is
needed to exercise the feature end to end.
"""

from __future__ import annotations

import logging

from application.ports.email_sender import EmailSender

logger = logging.getLogger(__name__)


class ConsoleEmailSender(EmailSender):
    async def send_otp(self, *, to: str, code: str, expires_in_minutes: int) -> None:
        logger.info(
            "OTP for %s is %s (expires in %d minutes). "
            "EMAIL_BACKEND=console: this was logged, not emailed.",
            to,
            code,
            expires_in_minutes,
        )
