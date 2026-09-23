"""The Signal Taxonomy sheet's thirteen signal types.

"Signals are counted as distinct types per call, never as occurrences —
five instances of one problem is one problem, whereas three different
problems on one call is an account coming apart." Severity and owner are
fixed per type, not chosen by the model — `SEVERITY_OF` is copied
verbatim from the sheet.
"""

from __future__ import annotations

from enum import Enum

from domain.value_objects.signal_severity import SignalSeverity


class SignalType(str, Enum):
    MEMBER_COMMUNICATION_GAP = "member_communication_gap"
    PROCESS_BREAKDOWN = "process_breakdown"
    COMPLIANCE_DISCLOSURE_MISSING = "compliance_disclosure_missing"
    VERIFICATION_FAILURE = "verification_failure"
    BROKER_CONDUCT_ADVERSE = "broker_conduct_adverse"
    BROKER_CONDUCT_POSITIVE = "broker_conduct_positive"
    ESCALATION_MISSED = "escalation_missed"
    RETENTION_RISK = "retention_risk"
    REVENUE_OPPORTUNITY = "revenue_opportunity"
    KNOWLEDGE_ERROR = "knowledge_error"
    NETWORK_ADEQUACY = "network_adequacy"
    BILLING_DEFECT = "billing_defect"
    PROCESS_GAP_PROPOSED = "process_gap_proposed"


# Signal Taxonomy sheet, "Severity" column — fixed per type.
SEVERITY_OF: dict[SignalType, SignalSeverity] = {
    SignalType.MEMBER_COMMUNICATION_GAP: SignalSeverity.MEDIUM,
    SignalType.PROCESS_BREAKDOWN: SignalSeverity.HIGH,
    SignalType.COMPLIANCE_DISCLOSURE_MISSING: SignalSeverity.HIGH,
    SignalType.VERIFICATION_FAILURE: SignalSeverity.CRITICAL,
    SignalType.BROKER_CONDUCT_ADVERSE: SignalSeverity.HIGH,
    SignalType.BROKER_CONDUCT_POSITIVE: SignalSeverity.LOW,
    SignalType.ESCALATION_MISSED: SignalSeverity.HIGH,
    SignalType.RETENTION_RISK: SignalSeverity.CRITICAL,
    SignalType.REVENUE_OPPORTUNITY: SignalSeverity.LOW,
    SignalType.KNOWLEDGE_ERROR: SignalSeverity.MEDIUM,
    SignalType.NETWORK_ADEQUACY: SignalSeverity.MEDIUM,
    SignalType.BILLING_DEFECT: SignalSeverity.HIGH,
    SignalType.PROCESS_GAP_PROPOSED: SignalSeverity.MEDIUM,
}


def severity_of(signal_type: SignalType) -> SignalSeverity:
    return SEVERITY_OF[signal_type]
