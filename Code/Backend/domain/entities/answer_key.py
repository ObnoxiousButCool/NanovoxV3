"""What the corpus PDF says about a call, before anything strips it out.

The answer sheet (plan §6.3): category, archetype, cited rules, outcome,
score, and the raw `CALL TAGS` block. Used **only** to score the extraction
pipeline (Phase 5) — reached through `AnswerKeySource`, a port no
extraction code may import (enforced by an import-linter contract). No
screen ever renders this.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AnswerKey:
    """`reference` is the call's business key, e.g. ``C-0001``."""

    reference: str
    category: str
    archetype: str
    rule_refs: tuple[str, ...]
    outcome: str
    score: int | None
    call_tags_text: str
