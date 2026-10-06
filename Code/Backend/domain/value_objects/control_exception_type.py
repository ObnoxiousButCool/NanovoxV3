"""The three control exceptions the Call Tag Schema allows (field 7).

"Deterministic checks on the opening turns. The strongest case for real-
time assist — a greeting check needs no model" (Call Tag Schema sheet).
Two of the three are genuinely pattern-matchable against the opening
turns alone. The third needs to know what benefit was under discussion,
which takes a model's judgement, and metric 7 is deterministic — so nothing
produces it (see ``domain/extraction/l1_deterministic.py``).
"""

from __future__ import annotations

from enum import StrEnum


class ControlExceptionType(StrEnum):
    NO_RECORDING_DISCLOSURE = "no_recording_disclosure"
    DISCLOSURE_BEFORE_VERIFICATION = "disclosure_before_verification"
    MISSING_BENEFIT_DISCLOSURE = "missing_benefit_disclosure"
