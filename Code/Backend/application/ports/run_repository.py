"""Persistence port for a run of the extraction pipeline over a set of
calls (plan §8 Phase 3, "run orchestration... resumability").

A run's status and its items' statuses are two different questions
(`domain.value_objects.run_status`'s module docstring): a run stays
healthy while individual items fail, so the two are read and written
separately here rather than folded into one call.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from domain.value_objects.run_status import RunItemStatus, RunStatus


@dataclass(frozen=True)
class RunRecord:
    """A run's own fields — not its items, which are read separately so a
    caller that only needs the status isn't forced to load every item."""

    id: int
    status: RunStatus
    provider: str
    model: str
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(frozen=True)
class RunItemRecord:
    call_reference: str
    status: RunItemStatus
    error: str | None = None


class RunRepository(ABC):
    """Stores a run's own record and its per-call items."""

    @abstractmethod
    async def create(
        self, call_references: Sequence[str], *, provider: str, model: str, created_at: datetime
    ) -> int:
        """Start a new run, PENDING, with one PENDING item per reference.

        Returns the new run's id."""

    @abstractmethod
    async def get(self, run_id: int) -> RunRecord | None: ...

    @abstractmethod
    async def items(self, run_id: int) -> tuple[RunItemRecord, ...]:
        """Every item in this run, in the order they were created."""

    @abstractmethod
    async def set_status(
        self, run_id: int, status: RunStatus, *, at: datetime | None = None
    ) -> None:
        """Move the run itself to a new status.

        ``at`` records when the run started or finished — the caller
        passes it only on the transitions that mean one of those two
        things (into RUNNING for the first time, into a terminal status)."""

    @abstractmethod
    async def set_item_status(
        self, run_id: int, call_reference: str, status: RunItemStatus, *, error: str | None = None
    ) -> None: ...

    @abstractmethod
    async def active_run_ids(self) -> tuple[int, ...]:
        """Every run this repository believes is still active.

        Read once at process startup: a run found active here belonged to
        whatever process created this repository's data, which is never
        the process now asking — nothing could actually be working it yet
        (plan: a fresh `BackgroundRunner` starts with no tasks)."""
