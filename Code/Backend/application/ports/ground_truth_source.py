"""Port for reading the workbook's Transcript Tracker — the answer key.

Answer-key material: no extraction code may import this, enforced by the
import-linter contract "Extraction cannot read the answer key" in
`pyproject.toml` rather than left to convention. The same rule already
covers `application.ports.answer_key_source`, which is the PDF-side
equivalent of this port.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from domain.entities.ground_truth import GroundTruth


@dataclass(frozen=True)
class GroundTruthDataset:
    """Every tracker row read from one workbook, plus non-fatal warnings.

    Warnings follow `ReferenceDataset`'s reasoning: a cell in a form this
    parser does not recognise is collected, not raised, so one unfamiliar
    value does not abort an otherwise-good import. That matters more here
    than it does for reference data — an answer key that refuses to load
    leaves Phase 5 with nothing to score against at all, which is a worse
    failure than an answer key that loads with three fields flagged.
    """

    rows: tuple[GroundTruth, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)


class GroundTruthSource(ABC):
    """Reads the build-bible workbook's Transcript Tracker sheet."""

    @abstractmethod
    def read(self) -> GroundTruthDataset:
        """Parse the tracker into a `GroundTruthDataset`.

        Synchronous for the same reason as `ReferenceSource.read`: a local
        file and in-memory XML parsing, run as a rare admin operation
        rather than on a request path.
        """
