"""One verbatim statement behind Call Tag Schema field 9.

"Verbatim statements only, with the turn reference. Inferred intent is an
opinion and will be treated as one" — so every statement carries the
quote and turn it came from, validated the same way a rubric marker or a
signal is (plan §7, "Evidence validation, every LLM layer").
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.value_objects.intent_type import IntentType


@dataclass(frozen=True)
class IntentStatement:
    type: IntentType
    quote: str
    turn_seq: int
