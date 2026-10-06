"""Performance tier and the thresholds that define it (Call Quality
Framework sheet, "Banding").

Thresholds are data, not constants: they arrive from ``config/rubric.yaml``
so a reviewer can see and change where the boundaries sit without reading
code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from domain.errors import ValidationError
from domain.value_objects.score import MAX_SCORE, MIN_SCORE, Score


class Tier(StrEnum):
    """GOOD at 86 and above, AVERAGE at 60 and above, POOR below 60
    (Call Quality Framework sheet)."""

    GOOD = "GOOD"
    AVERAGE = "AVERAGE"
    POOR = "POOR"


@dataclass(frozen=True)
class TierThresholds:
    """Lower bounds, inclusive: ``score >= good`` is GOOD, ``>= average`` is AVERAGE."""

    good: int
    average: int

    def __post_init__(self) -> None:
        if not MIN_SCORE < self.average < self.good <= MAX_SCORE:
            raise ValidationError(
                "Tier thresholds must satisfy "
                f"{MIN_SCORE} < average < good <= {MAX_SCORE}, "
                f"got average={self.average}, good={self.good}."
            )

    def tier_for(self, score: Score) -> Tier:
        if score.value >= self.good:
            return Tier.GOOD
        if score.value >= self.average:
            return Tier.AVERAGE
        return Tier.POOR
