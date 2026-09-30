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
    async def list(self, employer_ref: str | None = None) -> tuple[Action, ...]:
        """Every action, newest first. Scoped to one employer when given.

        **Scoped here rather than by the caller**, because "this account's
        actions" is a definition and not a filter. An action belongs to an
        account either by naming it or by citing one of its calls, and the
        second half is a join the client cannot do without being sent every
        action's whole call list -- one seeded action cites 179 calls. A
        client that did it anyway would own a second definition of account
        membership, and the two would disagree the first time either moved.
        """

    @abstractmethod
    async def calls_on_account(self, employer_ref: str) -> dict[int, int]:
        """Per action, how many of its cited calls are this employer's.

        A separate method rather than a field on `Action`, because it is a
        property of the question and not of the action: the same card has a
        different answer on every account page and none at all on the board.
        Hanging it off the entity would make `Action` mean something
        different depending on which query produced it.

        Actions with none of this employer's calls are absent rather than
        present at nought -- a caller that has scoped the board to this
        account will not ask about them, and a nought would have to mean
        "no share" where the honest reading is "not in this scope".
        """

    @abstractmethod
    async def save(self, action: Action) -> None:
        """Write back an edited action: its fields, its checklist and any
        log entries not stored yet."""

    @abstractmethod
    async def seed_keys(self) -> frozenset[str]:
        """The seed keys already present."""
