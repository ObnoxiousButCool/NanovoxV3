"""`ImportReferenceData` orchestrates source → repository; both faked."""

from __future__ import annotations

from application.ports.reference_repository import ImportCounts, ReferenceRepository
from application.ports.reference_source import ReferenceDataset, ReferenceSource
from application.use_cases.import_reference_data import ImportReferenceData

_COUNTS = ImportCounts(
    brokers=1, employers=1, members=1, employer_contacts=1, agents=1, rules=1, touchpoints=1
)


class _FakeSource(ReferenceSource):
    def __init__(self, dataset: ReferenceDataset) -> None:
        self._dataset = dataset

    def read(self) -> ReferenceDataset:
        return self._dataset


class _FakeRepository(ReferenceRepository):
    def __init__(self) -> None:
        self.received: ReferenceDataset | None = None

    async def upsert(self, dataset: ReferenceDataset) -> ImportCounts:
        self.received = dataset
        return _COUNTS


async def test_passes_the_source_dataset_straight_to_the_repository() -> None:
    dataset = ReferenceDataset(warnings=("something to know about",))
    repository = _FakeRepository()
    use_case = ImportReferenceData(source=_FakeSource(dataset), repository=repository)

    result = await use_case.execute()

    assert repository.received is dataset
    assert result.counts == _COUNTS
    assert result.warnings == ("something to know about",)
