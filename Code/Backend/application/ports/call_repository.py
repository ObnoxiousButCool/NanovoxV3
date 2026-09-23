"""Port for persisting ingested calls.

Idempotent by reference, like `ReferenceRepository` — re-ingesting is safe.
Every call is written, whatever its resolution status: nothing here decides
to drop one.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from domain.entities.ingested_call import IngestedCall


@dataclass(frozen=True)
class IngestCounts:
    total: int
    resolved: int
    caller_unresolved: int
    agent_unknown: int
    speaker_unresolved: int


class CallRepository(ABC):
    @abstractmethod
    async def upsert_all(self, calls: tuple[IngestedCall, ...]) -> IngestCounts: ...
