"""Persistence port for the email-OTP allowlist.

A database table rather than a config file (Ranjit, 2026-10-08 — see
Documents/notes/Decisions-and-Questions.md): the first cut shipped as
`config/approved_emails.yaml`, edited by a developer and redeployed. That
reads fine for a handful of internal testers; it does not for a client's own
list of who may sign in, which changes on a schedule this application's own
deploys do not follow.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class ApprovedEmailsRepository(ABC):
    """Stores and checks the set of addresses allowed to sign in.

    Matching is case- and whitespace-insensitive throughout — an adapter
    normalises before it writes and before it reads, so the same address
    typed two different ways is always the same row.
    """

    @abstractmethod
    async def is_approved(self, email: str) -> bool: ...

    @abstractmethod
    async def add(self, email: str, *, at: datetime) -> None:
        """Approve an address. Adding one already approved is a no-op."""

    @abstractmethod
    async def remove(self, email: str) -> bool:
        """Revoke an address. Returns whether it was on the list at all."""

    @abstractmethod
    async def list_all(self) -> tuple[str, ...]:
        """Every approved address, oldest first."""
