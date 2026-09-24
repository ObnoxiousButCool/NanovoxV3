"""Call Tag Schema field 8.

"Must cite a rule ID from the Product Rules sheet. Naming the rule points at
one article; naming the agent fixes nothing." The rule id is therefore
required when present, and enforced here rather than trusted — metric 8's
build note says the output is a list of knowledge base articles to rewrite,
ranked by call count, and a failure with no rule id cannot appear on it.

**D7 is open with Karim and must not be resolved in code.** The workbook
contradicts itself: C-0001 is RESOLVED, scores 91, is archetyped "Competent
and resolved", and still carries a knowledge failure. Store the field as the
schema defines it and roll it up by rule id and by touchpoint. Do not label
it an agent error, and do not add a correction or a heuristic.

The genuine agent-conduct event is a different thing entirely — the
`knowledge_error` signal, "an agent stated a published rule incorrectly",
MEDIUM, owner Knowledge Management. The two are independent and can fire
with or without each other.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.errors import ValidationError


@dataclass(frozen=True)
class KnowledgeFailure:
    present: bool
    rule_id: str | None = None
    correct_statement: str | None = None

    def __post_init__(self) -> None:
        # `correct_statement` is deliberately not required while D7 is open:
        # demanding a correction would read this field as an agent error.
        if self.present and not self.rule_id:
            raise ValidationError(
                "A knowledge failure must cite a rule id — naming the rule is the whole point."
            )
        if not self.present and (self.rule_id is not None or self.correct_statement is not None):
            raise ValidationError(
                "An absent knowledge failure must not carry a rule id or statement."
            )
