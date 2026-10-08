"""Port for delivering a one-time code to a reader's inbox.

Deliberately narrow: `send_otp` takes the address and the code, not a
template or a subject line, so every adapter (console log for development, an
SMTP account, a transactional provider later) sends the same words — the
choice of *how* the words get there is the only thing that changes behind
this port.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class EmailSender(ABC):
    """Delivers an OTP code to an email address."""

    @abstractmethod
    async def send_otp(self, *, to: str, code: str, expires_in_minutes: int) -> None:
        """Send the code. Raises `DependencyUnavailableError` if it could not be sent."""
