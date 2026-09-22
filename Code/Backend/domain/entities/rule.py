"""A published rule an agent, a broker or a document can be measured against.

Rules — Program / Administration / Carrier sheets (122 rules total). Layer
decides who owns the rule and who is accountable for it being right — see
`RuleLayer`. `call_scenarios` exists only on Administration-layer rules
(that sheet's own extra column); absent elsewhere.

Referenced directly by `knowledge_failure.rule_id` (Call Tag Schema field
8) — "must cite a rule ID... naming the rule points at one article; naming
the agent fixes nothing" — and by every `rules` reference a call's category
and product line scope L3/L4 to (§7). A rule marked `UNVERIFIED` may only
shape a question, never assert that an agent or a document was wrong (Rules
— Program sheet's own instruction) — insight 24 exists to keep that
distinction visible.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.value_objects.rule_confidence import RuleConfidence
from domain.value_objects.rule_layer import RuleLayer


@dataclass(frozen=True)
class Rule:
    """Reference is the business key, e.g. ``P-14``, ``A-09``, ``C-12``."""

    reference: str
    layer: RuleLayer
    area: str
    text: str
    commonly_confused_with: str
    source: str
    confidence: RuleConfidence
    call_scenarios: str | None = None
