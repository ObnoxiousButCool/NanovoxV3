"""One turn of dialogue.

Source-agnostic (plan §6.4): a turn carries a role and text, plus optional
timing and channel that only a richer source (audio) would ever populate.
No PDF-specific field survives ingestion into this shape.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.value_objects.speaker_role import SpeakerRole


@dataclass(frozen=True)
class Turn:
    role: SpeakerRole
    text: str
    start_seconds: float | None = None
    end_seconds: float | None = None
    channel: str | None = None
