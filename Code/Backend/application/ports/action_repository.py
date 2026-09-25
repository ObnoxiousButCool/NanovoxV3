"""Persistence port for actions (Revised plan Phase 4, D6).

An action is created once, read back whole — calls, checklist and log with
it — and saved whole after an edit. The log is append-only: saving writes
the entries the stored action does not have yet and never rewrites one.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime

from domain.actions import Action, ChecklistStep, LogEntry, Priority
from domain.value_objects.action_source_kind import ActionSourceKind


@dataclass(frozen=True)
class NewAction:
    """Everything an action is created with. No id yet."""

    title: str
    source_kind: ActionSourceKind
    source_detail: str | None
    issue_key: str | None
    evidence: str
    recommendation: str | None
    owner_team: str
    owner: str | None
    priority: Priority
    status: str
    employer_ref: str | None
    broker_ref: str | None
    call_references: tuple[str, ...]
    steps: tuple[ChecklistStep, ...]
    log: tuple[LogEntry, ...]
    created_at: datetime
    assigned_on: date | None = None
    due: date | None = None
    #: Set only when seeding, so a second seed finds it rather than
    #: creating it again.
    seed_key: str | None = None


class ActionRepository(ABC):
    @abstractmethod
    async def create(self, action: NewAction) -> Action:
        """Store `action`. Every call reference must name an ingested call."""

    @abstractmethod
    async def get(self, action_id: int) -> Action | None: ...

    @abstractmethod
    async def list(self) -> tuple[Action, ...]:
        """Every action, newest first."""

    @abstractmethod
    async def save(self, action: Action) -> None:
        """Write back an edited action: its fields, its checklist and any
        log entries not stored yet."""

    @abstractmethod
    async def seed_keys(self) -> frozenset[str]:
        """The seed keys already present."""
