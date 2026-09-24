"""Port for persisting the imported answer key.

Answer-key material — see `ground_truth_source` for the import-linter
contract that keeps extraction out of it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from domain.entities.ground_truth import GroundTruth


@dataclass(frozen=True)
class GroundTruthCounts:
    """What one answer-key import wrote, and what it could not place.

    `unmatched` counts tracker rows naming a call that has not been
    ingested. They are reported rather than written: `ground_truth` hangs
    off `calls.id`, so a row with no call has nowhere to go, and inventing
    a placeholder call to hold an answer would put fabricated rows in the
    fact table. A non-zero count here means the corpus and the tracker are
    out of step — usually the mismatched-revision trap of plan §11 — and
    the import says so instead of quietly writing 97 of 100.
    """

    written: int
    unmatched: tuple[str, ...]


class GroundTruthRepository(ABC):
    """Persists the answer key, idempotently, keyed by call reference."""

    @abstractmethod
    async def upsert(self, rows: tuple[GroundTruth, ...]) -> GroundTruthCounts:
        """Insert or update one row per call, matched by call reference.

        Idempotent like `ReferenceRepository.upsert`: re-running against the
        same or a revised workbook updates in place. A tracker row whose
        call is not ingested is returned in `unmatched`, never written.
        """

    @abstractmethod
    async def all(self) -> tuple[GroundTruth, ...]:
        """Every stored answer, ordered by call reference.

        Phase 5 scores the pipeline against all of them at once, so this
        reads the lot rather than offering a per-call lookup: an evaluation
        that fetched one row at a time would make "the pipeline produced
        nothing for this call" indistinguishable from "this call has no
        answer", and those are different findings.
        """
