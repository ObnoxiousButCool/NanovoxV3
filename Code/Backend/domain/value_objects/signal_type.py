"""The Signal Taxonomy sheet's thirteen signal types.

"Signals are counted as distinct types per call, never as occurrences —
five instances of one problem is one problem, whereas three different
problems on one call is an account coming apart." Severity and owner are
fixed per type, not chosen by the model — `SEVERITY_OF` and `OWNER_OF` are
copied verbatim from the sheet, which calls both mandatory: severity drives
ranking and owner drives routing.

An enum rather than bare strings because the aggregations branch on three
specific types — `knowledge_error` is the real agent-conduct event (D7),
`broker_conduct_adverse` drives the isolation views, and
`process_gap_proposed` carries the improvement lifecycle. A typo in any of
those produces a count of zero, which reads as good news rather than as a
bug.

`tests/integration/test_signal_taxonomy_matches_workbook.py` checks every
type, severity and owner against the real sheet, and fails if a signal is
added there and not here — the case that otherwise just makes a number
quietly smaller.
"""

from __future__ import annotations

from enum import StrEnum

from domain.value_objects.signal_severity import SignalSeverity


class SignalType(StrEnum):
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
    #: and nothing may reconcile them in code.
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


# Signal Taxonomy sheet, "Owner" column — who the signal routes to. Mandatory
# per the sheet, and not the call centre for most of them: a compliance
# failure goes to Compliance and a knowledge error to Knowledge Management.
OWNER_OF: dict[SignalType, str] = {
    SignalType.MEMBER_COMMUNICATION_GAP: "Member Communications",
    SignalType.PROCESS_BREAKDOWN: "Operations",
    SignalType.COMPLIANCE_DISCLOSURE_MISSING: "Compliance",
    SignalType.VERIFICATION_FAILURE: "Compliance",
    SignalType.BROKER_CONDUCT_ADVERSE: "Broker Relations",
    SignalType.BROKER_CONDUCT_POSITIVE: "Broker Relations",
    SignalType.ESCALATION_MISSED: "Operations",
    SignalType.RETENTION_RISK: "Account Management",
    SignalType.REVENUE_OPPORTUNITY: "Account Management",
    SignalType.KNOWLEDGE_ERROR: "Knowledge Management",
    SignalType.NETWORK_ADEQUACY: "Product / Network",
    SignalType.BILLING_DEFECT: "Operations / Finance",
    SignalType.PROCESS_GAP_PROPOSED: "Process Owner (by touchpoint)",
}

#: Worst first. Ranking order for the views that sort by severity.
SEVERITY_ORDER: tuple[SignalSeverity, ...] = (
    SignalSeverity.CRITICAL,
    SignalSeverity.HIGH,
    SignalSeverity.MEDIUM,
    SignalSeverity.LOW,
)


def owner_team_of(signal_type: SignalType) -> str:
    """Who the signal routes to. The sheet calls this mandatory, not advisory."""
    return OWNER_OF[signal_type]
