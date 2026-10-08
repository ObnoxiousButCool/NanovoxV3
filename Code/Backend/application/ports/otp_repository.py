"""Persistence port for OTP requests.

One row per code issued, not one row per email. A new request for the same
address does not overwrite the last one — it is recorded separately and the
use case consults only the most recent, so a code already sent stays valid
for its own lifetime even if the reader asks for another before it expires
(decision: the resend button issues a new code rather than re-sending the
old one, since a reader who lost the first email cannot tell this one apart
from it, and sending the same secret twice doubles its exposure for no gain).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class OtpRequestRecord:
    id: int
    email: str
    code_hash: str
    created_at: datetime
    expires_at: datetime
    attempts: int
    consumed_at: datetime | None


class OtpRepository(ABC):
    """Stores and retrieves OTP requests."""

    @abstractmethod
    async def create(
        self, *, email: str, code_hash: str, created_at: datetime, expires_at: datetime
    ) -> OtpRequestRecord:
        """Record a newly issued code."""

    @abstractmethod
    async def latest_for(self, email: str) -> OtpRequestRecord | None:
        """The most recently issued request for this address, if any.

        Used both to verify a submitted code against and to throttle how
        often a new one may be requested — the one existing row answers
        both questions, rather than two separate queries that could
        disagree about which request is "current".
        """

    @abstractmethod
    async def record_attempt(self, request_id: int) -> int:
        """Count one more guess against this request. Returns the new total."""

    @abstractmethod
    async def consume(self, request_id: int, *, at: datetime) -> None:
        """Mark a request used, so its code cannot be replayed."""
