"""L4's structured-output schema — what the model must return.

Every field is required and non-nullable, for the same reason as L2's and
L3's (see ``application/dto/l2_response.py``'s module docstring): absence
is its own literal value, normalised into the domain shape by
``application.use_cases.classify_call_l4``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

SignalTypeLiteral = Literal[
    "member_communication_gap",
    "process_breakdown",
    "compliance_disclosure_missing",
    "verification_failure",
    "broker_conduct_adverse",
    "broker_conduct_positive",
    "escalation_missed",
    "retention_risk",
    "revenue_opportunity",
    "knowledge_error",
    "network_adequacy",
    "billing_defect",
    "process_gap_proposed",
]

EscalationTriggerTypeLiteral = Literal[
    "caller_request",
    "compliance_exception",
    "contested_document",
    "retention_risk",
    "clinical_or_safety_risk",
    "scheduled_care_at_risk",
    "authority_limit",
    "broker_conduct_adverse",
    "NONE",
]

ProcessGapRaisedByLiteral = Literal["AGENT", "CALLER", "NONE"]
ProcessGapStatusLiteral = Literal["UNVALIDATED", "VALIDATED", "ACTIONED", "REJECTED", "NONE"]


class SignalResponse(BaseModel):
    type: SignalTypeLiteral
    quote: str
    turn_seq: int = Field(ge=0)


class ProcessGapResponse(BaseModel):
    present: bool
    #: Empty string when `present` is false.
    gap_type: str
    #: Empty string when `present` is false or unknown.
    touchpoint: str
    #: Empty string when `present` is false.
    proposed_change: str
    raised_by: ProcessGapRaisedByLiteral
    status: ProcessGapStatusLiteral


class L4Response(BaseModel):
    signals: list[SignalResponse]
    escalation_handled: bool
    escalation_trigger_type: EscalationTriggerTypeLiteral
    process_gap: ProcessGapResponse
    #: Empty string when L4 has nothing to add to or revise from L2's
    #: first pass.
    touchpoint: str
