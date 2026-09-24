"""The pipeline's own output for one call, read back.

Mirrors `CallExtractionRow`: every field arrives with the layer that
produces it, so most are `None` until that layer has run. A `None` field
means "not analysed yet", never "empty" — an L3/L4 failure is recorded as
unavailable with a reason (plan §7), not as this shape with blanks.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.entities.score_marker import ScoreMarker
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
from domain.value_objects.score import Score, ScoreStatus
from domain.value_objects.signal import Signal
from domain.value_objects.tier import Tier


@dataclass(frozen=True)
class CallExtraction:
    call_reference: str

    # --- L1 (run inside L2, saved with it) ---
    #: The two control exceptions a greeting check can prove (schema
    #: field 7). An empty set means L1 ran and found none; `None` means
    #: it has not run. Never carries `missing_benefit_disclosure` — see
    #: `domain/extraction/l1_deterministic.py`.
    control_exceptions: frozenset[ControlExceptionType] | None = None

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

    # --- L3 ---
    quality_score: Score | None = None
    quality_status: ScoreStatus | None = None
    quality_tier: Tier | None = None
    #: Only markers accepted by evidence checking — see
    #: `application.ports.call_extraction_repository.RaisedMarker` for the
    #: full raised-and-refused record this is read back from.
    markers: tuple[ScoreMarker, ...] = ()
    knowledge_failure: KnowledgeFailure | None = None

    # --- L4 ---
    signals: tuple[Signal, ...] = ()
    escalation_handled: bool | None = None
    escalation_trigger_type: EscalationTriggerType | None = None
    process_gap: ProcessGap | None = None
