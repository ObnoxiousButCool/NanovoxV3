"""Import the workbook's reference (master-data) sheets."""

from __future__ import annotations

from dataclasses import dataclass

from application.ports.reference_repository import ImportCounts, ReferenceRepository
from application.ports.reference_source import ReferenceSource


@dataclass(frozen=True)
class ImportResult:
    counts: ImportCounts
    warnings: tuple[str, ...]


class ImportReferenceData:
    """Reads the workbook, then upserts everything in one transaction."""

    def __init__(self, source: ReferenceSource, repository: ReferenceRepository) -> None:
        self._source = source
        self._repository = repository

    async def execute(self) -> ImportResult:
        dataset = self._source.read()
        counts = await self._repository.upsert(dataset)
        return ImportResult(counts=counts, warnings=dataset.warnings)
