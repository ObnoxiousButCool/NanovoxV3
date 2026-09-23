"""Call Tag Schema field 5, whose allowed values are the Signal Taxonomy sheet.

Thirteen signals, each with a fixed severity and a fixed owner team. Severity
drives ranking and owner drives routing, and the sheet calls both mandatory,
so they live here beside the code rather than being looked up from reference
data — they are properties of the signal type, not rows someone maintains.

An enum rather than the bare strings `GroundTruth` stores, because the
aggregations branch on three specific codes: `knowledge_error` is the real
agent-conduct event (D7), `broker_conduct_adverse` drives the isolation
views, and `process_gap_proposed` carries the improvement lifecycle. A typo
in any of those produces a count of zero, which reads as good news rather
than as a bug.

Counted as distinct types per call, never as occurrences — the sheet is
explicit: "five instances of one problem is one problem, whereas three
different problems on one call is an account coming apart."
"""

from __future__ import annotations

from enum import Enum


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SignalCode(str, Enum):
    MEMBER_COMMUNICATION_GAP = "member_communication_gap"
    PROCESS_BREAKDOWN = "process_breakdown"
    COMPLIANCE_DISCLOSURE_MISSING = "compliance_disclosure_missing"
    VERIFICATION_FAILURE = "verification_failure"
    BROKER_CONDUCT_ADVERSE = "broker_conduct_adverse"
    BROKER_CONDUCT_POSITIVE = "broker_conduct_positive"
    ESCALATION_MISSED = "escalation_missed"
    RETENTION_RISK = "retention_risk"
    REVENUE_OPPORTUNITY = "revenue_opportunity"
    #: "An agent stated a published rule incorrectly." The genuine
    #: agent-conduct event, and NOT the same thing as the `knowledge_failure`
    #: tag (schema field 8). The two are independent and can fire with or
    #: without each other; D7 is open with Karim on exactly that distinction,
    #: and nothing here may reconcile them.
    KNOWLEDGE_ERROR = "knowledge_error"
    NETWORK_ADEQUACY = "network_adequacy"
    BILLING_DEFECT = "billing_defect"
    PROCESS_GAP_PROPOSED = "process_gap_proposed"


#: Severity and owner exactly as the Signal Taxonomy sheet publishes them.
_TAXONOMY: dict[SignalCode, tuple[Severity, str]] = {
    SignalCode.MEMBER_COMMUNICATION_GAP: (Severity.MEDIUM, "Member Communications"),
    SignalCode.PROCESS_BREAKDOWN: (Severity.HIGH, "Operations"),
    SignalCode.COMPLIANCE_DISCLOSURE_MISSING: (Severity.HIGH, "Compliance"),
    SignalCode.VERIFICATION_FAILURE: (Severity.CRITICAL, "Compliance"),
    SignalCode.BROKER_CONDUCT_ADVERSE: (Severity.HIGH, "Broker Relations"),
    SignalCode.BROKER_CONDUCT_POSITIVE: (Severity.LOW, "Broker Relations"),
    SignalCode.ESCALATION_MISSED: (Severity.HIGH, "Operations"),
    SignalCode.RETENTION_RISK: (Severity.CRITICAL, "Account Management"),
    SignalCode.REVENUE_OPPORTUNITY: (Severity.LOW, "Account Management"),
    SignalCode.KNOWLEDGE_ERROR: (Severity.MEDIUM, "Knowledge Management"),
    SignalCode.NETWORK_ADEQUACY: (Severity.MEDIUM, "Product / Network"),
    SignalCode.BILLING_DEFECT: (Severity.HIGH, "Operations / Finance"),
    SignalCode.PROCESS_GAP_PROPOSED: (Severity.MEDIUM, "Process Owner (by touchpoint)"),
}

#: Worst first. Ranking order for the views that sort by severity.
SEVERITY_ORDER: tuple[Severity, ...] = (
    Severity.CRITICAL,
    Severity.HIGH,
    Severity.MEDIUM,
    Severity.LOW,
)


def severity_of(code: SignalCode) -> Severity:
    return _TAXONOMY[code][0]


def owner_team_of(code: SignalCode) -> str:
    """Who the signal routes to. The sheet calls this mandatory, not advisory."""
    return _TAXONOMY[code][1]
