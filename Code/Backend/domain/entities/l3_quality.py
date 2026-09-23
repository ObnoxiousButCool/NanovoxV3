"""L3 — quality & knowledge (plan §7): `quality_score`, `markers`,
`knowledge_failure`.

The score, status and tier come from `RubricEngine.score()` — this entity
just carries that result alongside the field the rubric doesn't touch,
`knowledge_failure`.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.entities.score_marker import ScoreMarker
from domain.scoring.rubric_engine import ScoreResult
from domain.value_objects.knowledge_failure import KnowledgeFailure


@dataclass(frozen=True)
class L3Quality:
    score_result: ScoreResult
    markers: tuple[ScoreMarker, ...]
    knowledge_failure: KnowledgeFailure
