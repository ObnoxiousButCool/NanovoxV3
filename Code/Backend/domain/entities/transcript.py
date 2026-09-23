"""A call's clean transcript — extraction's only view of a call.

Deliberately carries nothing an extraction stage shouldn't see: no
category, no outcome, no score, no archetype, no rule references. Those
live in `AnswerKey`, a separate entity reached through a separate port that
extraction code cannot import (plan's Phase 2 rules; enforced by an
import-linter contract, not just this docstring).

Source-agnostic (plan §6.4): `source` says where this came from, but
nothing else on this entity is PDF-specific. A `PastedSource` or
`AudioSource` adapter produces the exact same shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from domain.entities.turn import Turn
from domain.value_objects.call_source import CallSource
from domain.value_objects.caller_type import CallerType


@dataclass(frozen=True)
class Transcript:
    """`reference` is the call's business key, e.g. ``C-0001``."""

    reference: str
    source: CallSource
    occurred_at: datetime | None
    aht_seconds: int | None
    caller_type: CallerType
    caller_ref: str
    agent_ref: str
    agent_name: str
    turns: tuple[Turn, ...]
