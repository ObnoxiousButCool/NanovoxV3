"""The pipeline's own output for one call, read back.

Mirrors `CallExtractionRow`: every field arrives with the layer that
produces it, so most are `None` until that layer has run. A `None` field
means "not analysed yet", never "empty" — an L3/L4 failure is recorded as
unavailable with a reason (plan §7), not as this shape with blanks.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.value_objects.broker_named_aloud import BrokerNamedAloud
from domain.value_objects.category import Category
from domain.value_objects.complaint import Complaint
from domain.value_objects.intent_statement import IntentStatement
from domain.value_objects.outcome import Outcome
from domain.value_objects.product_line import ProductLine


@dataclass(frozen=True)
class CallExtraction:
    call_reference: str

    # --- L2 ---
    outcome: Outcome | None = None
    category: Category | None = None
    product_lines: tuple[ProductLine, ...] = ()
    complaint: Complaint | None = None
    intent: tuple[IntentStatement, ...] = ()
    escalation_triggered: bool | None = None
    escalation_requested_by_caller: bool | None = None
    broker_named_aloud: BrokerNamedAloud | None = None
    touchpoint: str | None = None
    summary: str | None = None
