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
from domain.entities.score_marker import ScoreMarker
from domain.scoring.rubric_engine import ScoreResult
from domain.value_objects.broker_named_aloud import BrokerNamedAloud
from domain.value_objects.category import Category
from domain.value_objects.complaint import Complaint
from domain.value_objects.control_exception_type import ControlExceptionType
from domain.value_objects.escalation_trigger_type import EscalationTriggerType
from domain.value_objects.intent_statement import IntentStatement
from domain.value_objects.knowledge_failure import KnowledgeFailure
from domain.value_objects.outcome import Outcome
from domain.value_objects.process_gap import ProcessGap
from domain.value_objects.product_line import ProductLine
from domain.value_objects.signal import Signal


@dataclass(frozen=True)
class L2Provenance:
    """Which call, model and prompt produced an L2 result, and when."""

    provider: str
    model: str
    prompt_version: str
    completed_at: datetime


@dataclass(frozen=True)
class L2Save:
    """Everything one L2 classification writes, including the L1 result it
    ran on — L1 has no save of its own (see `run_extraction_pipeline`)."""

    control_exceptions: frozenset[ControlExceptionType]
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


@dataclass(frozen=True)
class L3Provenance:
    """Which call, model, prompt and rubric version produced an L3 result."""

    provider: str
    model: str
    prompt_version: str
    rubric_version: str
    completed_at: datetime


@dataclass(frozen=True)
class RaisedMarker:
    """One marker as the model raised it, with whether it survived
    evidence checking — the Data Model sheet's "Rubric marker" entity is
    kept at this level, refused markers included, "so a refused marker is
    visible."""

    marker: ScoreMarker
    verification_status: str


@dataclass(frozen=True)
class L3Save:
    """Everything one L3 quality pass writes."""

    score_result: ScoreResult
    markers: tuple[RaisedMarker, ...]
    knowledge_failure: KnowledgeFailure
    provenance: L3Provenance


@dataclass(frozen=True)
class L4Provenance:
    """Which call, model and prompt produced an L4 result, and when."""

    provider: str
    model: str
    prompt_version: str
    completed_at: datetime


@dataclass(frozen=True)
class L4Save:
    """Everything one L4 signals-and-gaps pass writes."""

    signals: tuple[Signal, ...]
    escalation_handled: bool
    escalation_trigger_type: EscalationTriggerType | None
    process_gap: ProcessGap
    #: Empty when L4 has nothing to add to or revise from L2's first pass
    #: (leaves the existing `touchpoint` column untouched).
    touchpoint: str | None
    provenance: L4Provenance


class CallExtractionRepository(ABC):
    """Stores and reads back each call's pipeline output."""

    @abstractmethod
    async def get(self, call_reference: str) -> CallExtraction | None:
        """The call's extraction so far, or `None` if nothing has run yet."""

    @abstractmethod
    async def save_l2(self, call_reference: str, result: L2Save) -> None:
        """Record L2's output. Upserts: a re-run replaces, never duplicates."""

    @abstractmethod
    async def save_l3(self, call_reference: str, result: L3Save) -> None:
        """Record L3's output. Upserts: a re-run replaces, never duplicates."""

    @abstractmethod
    async def save_l4(self, call_reference: str, result: L4Save) -> None:
        """Record L4's output. Upserts: a re-run replaces, never duplicates."""

    @abstractmethod
    async def mark_l3_provisional(self, call_reference: str) -> None:
        """Move an already-saved L3 result's status to PROVISIONAL.

        The score, tier and markers are left exactly as L3 computed them —
        only the confidence status changes. Used once L4 has run and found
        a clinical-or-safety-risk trigger, which L3 could not see at
        scoring time (the two layers run concurrently)."""
