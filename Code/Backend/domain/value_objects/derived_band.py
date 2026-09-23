"""The High/Medium/Low banding shared by the derived composites (member
effort, complexity) — plan §7: "0-100, High >=60, Medium >=35".

Deliberately not `Tier` (GOOD/AVERAGE/POOR): that vocabulary belongs to
the quality score, a real Call Tag Schema field. Effort and complexity are
not — "our composites, not v9 fields" (Prototype/tools/03_join_corpus.py)
— and use their own words so nothing suggests they came from the
workbook.
"""

from __future__ import annotations

from enum import Enum

HIGH_THRESHOLD = 60
MEDIUM_THRESHOLD = 35


class DerivedBand(str, Enum):
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


def band_for(score: int) -> DerivedBand:
    if score >= HIGH_THRESHOLD:
        return DerivedBand.HIGH
    if score >= MEDIUM_THRESHOLD:
        return DerivedBand.MEDIUM
    return DerivedBand.LOW
