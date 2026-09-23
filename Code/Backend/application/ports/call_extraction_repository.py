"""Persistence port for the pipeline's per-call output (plan §7).

One row per call, filled in as each layer runs — see
`domain/entities/call_extraction.py`. Later layers (L3, L4) read a call's
L2 result back through here too: `category` and `product_lines` are what
scope which rules they're shown (plan §7, "never all 122").
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from domain.entities.call_extraction import CallExtraction
from domain.value_objects.broker_named_aloud import BrokerNamedAloud
from domain.value_objects.category import Category
from domain.value_objects.complaint import Complaint
from domain.value_objects.intent_statement import IntentStatement
from domain.value_objects.outcome import Outcome
from domain.value_objects.product_line import ProductLine


@dataclass(frozen=True)
class L2Provenance:
    """Which call, model and prompt produced an L2 result, and when."""

    provider: str
    model: str
    prompt_version: str
    completed_at: datetime


@dataclass(frozen=True)
class L2Save:
    """Everything one L2 classification writes."""

    outcome: Outcome
    category: Category
    product_lines: tuple[ProductLine, ...]
    complaint: Complaint
    intent: tuple[IntentStatement, ...]
    escalation_triggered: bool
    escalation_requested_by_caller: bool
    broker_named_aloud: BrokerNamedAloud
    touchpoint: str | None
    summary: str
    provenance: L2Provenance


class CallExtractionRepository(ABC):
    """Stores and reads back each call's pipeline output."""

    @abstractmethod
    async def get(self, call_reference: str) -> CallExtraction | None:
        """The call's extraction so far, or `None` if nothing has run yet."""

    @abstractmethod
    async def save_l2(self, call_reference: str, result: L2Save) -> None:
        """Record L2's output. Upserts: a re-run replaces, never duplicates."""
