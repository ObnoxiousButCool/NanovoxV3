"""One scored observation about a call, anchored to transcript evidence
(Call Tag Schema field 11: ``markers``).

Evidence is mandatory by construction — a marker cannot exist without
naming the turn it came from and quoting it, which is what makes every
point of deduction traceable to a sentence somebody actually said
(Call Quality Framework sheet: "the same transcript produces the same
score... every point lost can be traced to a quoted turn"). Whether the
quote is *truthful* is checked separately, against the transcript, by
``domain/extraction/evidence.py::validate_evidence`` — the same function
every other evidence-citing layer uses, which is why this carries `quote`
and `turn_seq` rather than NanoVox's `evidence_turn_seq`.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.errors import ValidationError
from domain.value_objects.polarity import Polarity


@dataclass(frozen=True)
class ScoreMarker:
    """One positive or negative observation about how the agent handled the call."""

    polarity: Polarity
    dimension: str
    description: str
    quote: str
    turn_seq: int

    def __post_init__(self) -> None:
        if not self.dimension.strip():
            raise ValidationError("Score marker must name a rubric dimension.")
        if not self.description.strip():
            raise ValidationError(
                f"Score marker for {self.dimension!r} must describe what was observed."
            )
        if isinstance(self.turn_seq, bool) or not isinstance(self.turn_seq, int):
            raise ValidationError(
                f"Score marker evidence turn must be an integer, got {self.turn_seq!r}."
            )
        if self.turn_seq < 0:
            raise ValidationError("Score marker evidence turn must be non-negative.")
        if not self.quote.strip():
            raise ValidationError(
                f"Score marker for {self.dimension!r} must quote the evidence it relies on."
            )

    @property
    def is_positive(self) -> bool:
        return self.polarity.is_positive
