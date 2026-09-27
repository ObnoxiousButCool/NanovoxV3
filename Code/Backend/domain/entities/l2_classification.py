"""L2 — classification (plan §7): outcome, category, product lines,
complaint, intent, the caller/detection half of escalation,
`broker_named_aloud`, a first-pass touchpoint, and a short summary.

Runs after L1 — its `category` and `product_lines` are what later scope
which of the 122 rules L3 and L4 are shown (plan §7, "never all 122").
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.value_objects.broker_named_aloud import BrokerNamedAloud
from domain.value_objects.category import Category
from domain.value_objects.complaint import Complaint
from domain.value_objects.impact_scope import ImpactScope
from domain.value_objects.intent_statement import IntentStatement
from domain.value_objects.outcome import Outcome
from domain.value_objects.product_line import ProductLine


@dataclass(frozen=True)
class L2Classification:
    outcome: Outcome
    category: Category
    product_lines: tuple[ProductLine, ...]
    complaint: Complaint
    intent: tuple[IntentStatement, ...]
    escalation_triggered: bool
    escalation_requested_by_caller: bool
    broker_named_aloud: BrokerNamedAloud
    #: A Touchpoint reference (Touchpoints sheet), or None if L2 found
    #: nothing to attribute a touchpoint to yet. L4 confirms or revises
    #: this first pass (Call Tag Schema field 16, "Emitted by: L2/L4").
    touchpoint: str | None
    summary: str
    #: Call Tag Schema field 19 (v10). `None` when the model gave no usable
    #: answer — free text, so nothing to validate past "non-empty".
    primary_issue: str | None
    secondary_issues: tuple[str, ...]
    #: Call Tag Schema field 20 (v10). `None` when the model's bucket+count
    #: combination would violate `ImpactScope.__post_init__` — an
    #: inconsistent answer is dropped, never guessed past.
    impact_scope: ImpactScope | None
