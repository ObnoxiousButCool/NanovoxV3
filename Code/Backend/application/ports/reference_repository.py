"""Port for persisting an imported `ReferenceDataset`."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from application.ports.reference_source import ReferenceDataset


@dataclass(frozen=True)
class ImportCounts:
    """How many rows of each kind were written by one import."""

    brokers: int
    employers: int
    members: int
    employer_contacts: int
    agents: int
    rules: int
    touchpoints: int


class ReferenceRepository(ABC):
    """Persists reference data, idempotently, by business reference."""

    @abstractmethod
    async def upsert(self, dataset: ReferenceDataset) -> ImportCounts:
        """Insert or update every entity in `dataset`, matched by reference.

        Re-running an import with the same or a revised workbook is safe:
        an existing row with the same reference is updated in place, never
        duplicated.
        """
