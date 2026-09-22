"""A call-centre agent.

Agent Roster sheet. Score is a property of the agent and the call — it never
rolls up to an account (Data Model sheet). `expected_score`/`score_variance`
are the roster's designed population, carried through so insight 28 (agent
conduct against expected band) can say how far the written corpus is from
the volume the roster itself requires, and `planned_calls` is that same
"thirty calls each" minimum for an agent-level rate.

Referenced by the transcript header's agent id/name — a legitimate input
(§6.3), not one of the sixteen Call Tag Schema fields itself, but the entity
every `quality_score` (field 10) and `markers` (field 11) attaches to.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Agent:
    """Reference is the business key, e.g. ``AGT-01``."""

    reference: str
    name: str
    band: str
    planned_calls: int
    expected_score: float | None
    score_variance: float | None
    dominant_pattern: str
