"""Port for reading the answer key — evaluation's only way to reach it.

Used **only** to score the extraction pipeline (Phase 5's evaluation
harness). No extraction use case may import this — enforced by the
import-linter contract "Extraction cannot read the answer key" in
`pyproject.toml`, not left to convention.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from domain.entities.answer_key import AnswerKey


class AnswerKeySource(ABC):
    """Reads every call's answer key from the corpus."""

    @abstractmethod
    def read(self) -> tuple[AnswerKey, ...]:
        """Parse every call's answer key. Synchronous, same reasoning as
        `ReferenceSource.read`.
        """
