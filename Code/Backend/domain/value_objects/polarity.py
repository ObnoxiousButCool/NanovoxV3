"""Direction of a scoring observation."""

from __future__ import annotations

from enum import StrEnum


class Polarity(StrEnum):
    """Whether a rubric marker counts for or against the score."""

    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"

    @property
    def is_positive(self) -> bool:
        return self is Polarity.POSITIVE
