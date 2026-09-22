"""Provenance grade of a rule.

Rules — Program/Administration/Carrier sheets, column "Confidence". A rule
marked `UNVERIFIED` may only shape a question, never assert that an agent or
a document was wrong (Rules — Program sheet's own instruction) — insight 24
(rule provenance and confidence) exists to make this distinction visible,
not just enforced silently in the extraction prompts.

`VERIFIED_SECONDARY` is a third value actually present in the workbook (Rules
— Program and Rules — Carrier), not documented in the plan's original
two-value description of this column — confirmed by reading every distinct
value across all three rule sheets rather than assuming VERIFIED/UNVERIFIED
was exhaustive.
"""

from __future__ import annotations

from enum import Enum


class RuleConfidence(str, Enum):
    VERIFIED = "VERIFIED"
    VERIFIED_SECONDARY = "VERIFIED (SECONDARY)"
    UNVERIFIED = "UNVERIFIED"
