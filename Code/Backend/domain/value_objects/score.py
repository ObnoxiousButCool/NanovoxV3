"""Agent score and its confidence status (Call Tag Schema field 10).

A score is a bounded integer, not a bare ``int``: it cannot be constructed
outside 0-100, so an arithmetic slip in the engine fails at the point of
the mistake rather than surfacing as a nonsensical figure on a dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain.errors import ValidationError

MIN_SCORE = 0
MAX_SCORE = 100


class ScoreStatus(str, Enum):
    """Whether a computed score can be presented as final.

    ``PROVISIONAL`` covers both cases the Call Quality Framework sheet's
    "Withholding" step names: every marker failing verification (handled
    entirely within L3 — see `RubricEngine.score`'s `evidence_all_rejected`
    parameter), and clinical risk present (which L4, not L3, detects —
    handled at the pipeline level once L3 and L4 have both run, not as a
    rubric-internal gate; see `domain/scoring/rubric.py`'s module
    docstring for why).
    """

    CONFIRMED = "confirmed"
    PROVISIONAL = "provisional"


@dataclass(frozen=True, order=True)
class Score:
    """An agent score in the closed range 0-100."""

    value: int

    def __post_init__(self) -> None:
        if isinstance(self.value, bool) or not isinstance(self.value, int):
            raise ValidationError(f"Score must be a whole number, got {self.value!r}.")
        if not MIN_SCORE <= self.value <= MAX_SCORE:
            raise ValidationError(
                f"Score must be between {MIN_SCORE} and {MAX_SCORE}, got {self.value}."
            )

    @classmethod
    def clamped(cls, raw: int) -> Score:
        """Build a score from a raw total, clamping into range.

        The rubric engine can produce a total outside 0-100 when many
        penalties accumulate; clamping is the intended behaviour there,
        so it is expressed explicitly rather than by silently
        constructing an invalid value.
        """
        return cls(max(MIN_SCORE, min(MAX_SCORE, raw)))

    def __str__(self) -> str:
        return str(self.value)
