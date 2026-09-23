"""Which of the three rule sheets a rule comes from.

Program (P-nn): what a group may buy — ChoiceBuilder's own eligibility and
plan-design rules. Administration (A-nn): what happens after the sale —
enrolment, billing, COBRA, the renewal timeline. Carrier (C-nn): what a
member actually receives — waiting periods, network rules, benefit limits,
set by the carriers rather than by ChoiceBuilder.

Referenced by `knowledge_failure.rule_id` (Call Tag Schema field 8) and by
`rules` cited on a call (field 7's control exceptions layer, and every
knowledge-failure/process-gap touchpoint mapping in §7A).
"""

from __future__ import annotations

from enum import Enum


class RuleLayer(str, Enum):
    PROGRAM = "P"
    ADMINISTRATION = "A"
    CARRIER = "C"
