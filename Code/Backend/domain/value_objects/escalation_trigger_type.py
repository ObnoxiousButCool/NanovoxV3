"""The Escalation Logic sheet's trigger list — eight conditions that
warrant escalation, each routing to a different owning team.

`escalation.triggered` (L2) asks whether any of these held;
`escalation.trigger_type` (L4) names which one. Both fields read this
same list — the schema splits *detecting* a trigger from *classifying*
it across the two layers.
"""

from __future__ import annotations

from enum import StrEnum


class EscalationTriggerType(StrEnum):
    #: The caller explicitly asks for a supervisor, a manager or someone
    #: senior. Deterministic — verbatim phrase with turn reference.
    CALLER_REQUEST = "caller_request"
    #: A control exception is detected on the call.
    COMPLIANCE_EXCEPTION = "compliance_exception"
    #: The caller disputes a document or signature on file.
    CONTESTED_DOCUMENT = "contested_document"
    #: Verbatim exit or market-test language.
    RETENTION_RISK = "retention_risk"
    #: A health or safety situation requiring urgent care or review.
    #: Model-detected, clinician-reviewed; the score is withheld pending
    #: review (Escalation Logic sheet — this is the clinical gate).
    CLINICAL_OR_SAFETY_RISK = "clinical_or_safety_risk"
    #: A benefit dispute the agent cannot resolve, with care already
    #: booked within days.
    SCHEDULED_CARE_AT_RISK = "scheduled_care_at_risk"
    #: A billing correction, reinstatement or retroactive adjustment
    #: beyond the agent's authority threshold.
    AUTHORITY_LIMIT = "authority_limit"
    #: A broker action or omission caused the caller's problem and the
    #: caller names the broker aloud.
    BROKER_CONDUCT_ADVERSE = "broker_conduct_adverse"
