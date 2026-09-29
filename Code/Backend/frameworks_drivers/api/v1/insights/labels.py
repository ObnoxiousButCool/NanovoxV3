"""Display wording for the coded values the insights screens show.

A response carries `billing_defect` because that is the Signal Taxonomy
sheet's own identifier, and `P` because that is how the Rules sheets name
the Program layer. Neither is something to put in front of a reader. This
maps each code to the words a person should see.

## Codes stay, labels are added

Every coded value goes out as `{code, label}` rather than as a label
replacing a code. Three reasons, and the first is the load-bearing one:

- **The code is the contract.** The filter parameters take `signal=
  billing_defect`, and a client that only received "Billing defect" could
  not send a filter back without reversing the prose. Round-tripping
  display text is how a filter starts matching nothing.
- A label may be reworded for clarity without breaking any client, because
  nothing branches on it.
- A reader looking at an API response and a screen sees the same two
  things, so a bug report can name either.

## Every label is written out, never derived

No `code.replace("_", " ").title()`. That helper looks tempting and gets
the domain's own vocabulary wrong: "Claims & Eob", "Cobra Regime", "Aht".
The terms this business uses — EOB, COBRA, AHT, ID cards — are exactly the
ones a naive transformation mangles, and it mangles them in the one place
everybody reads.

So the maps below are explicit, and
`tests/unit/test_insights_labels.py` fails if an enum gains a member
without one. That matters more than it looks: a missing label would
otherwise surface as a blank cell on a screen, which reads as "nothing
here" rather than as "we forgot to name this".

## Categories are already words

`Category` and the touchpoint names arrive from the workbook as prose —
"Claims & EOB" is the sheet's own wording — so they are not mapped here.
Re-labelling them would put a second vocabulary beside the workbook's, and
the workbook wins.
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from domain.aggregation.figure import Basis, WithheldReason
from domain.insights.generated import (
    InsightKind,
    InsightsStatus,
    Lens,
    Severity,
    UnavailableReason,
)
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.control_exception_type import ControlExceptionType
from domain.value_objects.outcome import Outcome
from domain.value_objects.process_gap import ProcessGapStatus, RaisedBy
from domain.value_objects.product_line import ProductLine
from domain.value_objects.rule_confidence import RuleConfidence
from domain.value_objects.rule_layer import RuleLayer
from domain.value_objects.signal_severity import SignalSeverity
from domain.value_objects.signal_type import SignalType
from frameworks_drivers.api.camel import CamelModel


class CodedValue(CamelModel):
    """One coded value and the words for it.

    `code` is what a filter accepts and what a client branches on; `label`
    is what a person reads. They are never the same field.
    """

    code: str = Field(description="The stable identifier. Filters take this value.")
    label: str = Field(description="Display wording. Never branch on it — it may be reworded.")


#: Every label the insights screens show, by enum member.
#:
#: Written out rather than generated. See this module's docstring: a
#: derived label gets "Claims & Eob" and "Aht" wrong, in the one place
#: everybody reads.
LABELS: dict[Enum, str] = {
    # --- Basis: where a number came from (D13). Suppression is not a basis
    # and is not in this enum; it is `published` plus `withheldReason`.
    Basis.OBSERVED: "Observed",
    Basis.DERIVED: "Derived",
    Basis.REFERENCE: "Reference",
    # --- How a call ended (schema field 1). The prototype's own wording,
    # which is a reader's rather than the enum's: "Partly resolved" is what
    # the chart legend says, and a chart that disagreed with the rest of
    # the screen about a category name would be read as a different
    # category.
    Outcome.RESOLVED: "Resolved",
    Outcome.PARTIALLY_RESOLVED: "Partly resolved",
    Outcome.ESCALATED: "Escalated",
    Outcome.UNRESOLVED: "Unresolved",
    # --- Why a figure is withheld. Each means something different to a
    # reader: more calls fixes the first, only a schema change fixes the
    # second, and the third is not a finding of low risk.
    WithheldReason.BELOW_MIN_N: "Too few calls to publish",
    WithheldReason.NO_FIELD: "Not a field in the v9 schema",
    WithheldReason.NOT_ELIGIBLE: "Not enough calls to assess",
    WithheldReason.MONEY_UNKNOWN: "Cost per call not set",
    WithheldReason.NO_DENOMINATOR: "Nothing to divide by",
    # --- Signal severity (Signal Taxonomy sheet, fixed per type) ---
    SignalSeverity.CRITICAL: "Critical",
    SignalSeverity.HIGH: "High",
    SignalSeverity.MEDIUM: "Medium",
    SignalSeverity.LOW: "Low",
    # --- The thirteen signal types ---
    SignalType.MEMBER_COMMUNICATION_GAP: "Member communication gap",
    SignalType.PROCESS_BREAKDOWN: "Process breakdown",
    SignalType.COMPLIANCE_DISCLOSURE_MISSING: "Compliance disclosure missing",
    SignalType.VERIFICATION_FAILURE: "Verification failure",
    SignalType.BROKER_CONDUCT_ADVERSE: "Broker conduct — adverse",
    SignalType.BROKER_CONDUCT_POSITIVE: "Broker conduct — positive",
    SignalType.ESCALATION_MISSED: "Escalation missed",
    SignalType.RETENTION_RISK: "Retention risk",
    SignalType.REVENUE_OPPORTUNITY: "Revenue opportunity",
    SignalType.KNOWLEDGE_ERROR: "Knowledge error",
    SignalType.NETWORK_ADEQUACY: "Network adequacy",
    SignalType.BILLING_DEFECT: "Billing defect",
    SignalType.PROCESS_GAP_PROPOSED: "Process gap proposed",
    # --- Control exceptions (metric 7, reported per type) ---
    ControlExceptionType.NO_RECORDING_DISCLOSURE: "No recording disclosure",
    ControlExceptionType.DISCLOSURE_BEFORE_VERIFICATION: "Disclosure before verification",
    ControlExceptionType.MISSING_BENEFIT_DISCLOSURE: "Missing benefit disclosure",
    # --- Rule layer. The codes are "P", "A" and "C", which say nothing to
    # a reader on their own — this is the clearest case for the whole map.
    RuleLayer.PROGRAM: "Program",
    RuleLayer.ADMINISTRATION: "Administration",
    RuleLayer.CARRIER: "Carrier",
    # --- Rule provenance, from the Rules sheets' own grades ---
    RuleConfidence.VERIFIED: "Verified",
    RuleConfidence.VERIFIED_SECONDARY: "Verified (secondary source)",
    RuleConfidence.UNVERIFIED: "Unverified",
    # --- What a generated sentence is doing. Never OBSERVED: `Basis`
    # describes where a figure came from, and no generated text is one of
    # its three values (checkpoint I4, the honesty contract).
    InsightKind.INFERENCE: "What this suggests",
    InsightKind.RECOMMENDATION: "Suggested action",
    # --- Reading order for generated prose. Deliberately not "High risk":
    # D12 reserves the flag for metric 10 and there is no risk band to echo
    # here, so these are worded as attention rather than as a grade.
    Severity.READ_FIRST: "Read first",
    Severity.WORTH_READING: "Worth reading",
    Severity.BACKGROUND: "Background",
    # --- The four exec lenses. A client requirement (U1), so this is the
    # prototype's own wording and is not reworded to fit a column.
    Lens.EMPLOYERS: "Employers",
    Lens.CHURN_AND_RETENTION: "Churn & retention",
    Lens.PRODUCT_AND_SERVICE: "Product & service",
    Lens.PAYER_AND_CARRIER: "Payer & carrier",
    # --- Whether there is generated text at all (U2) ---
    InsightsStatus.GENERATED: "Generated",
    InsightsStatus.UNAVAILABLE: "Unavailable",
    # --- and why there is not. Each reason is a different thing to do.
    UnavailableReason.NO_PROVIDER: "No model is configured",
    UnavailableReason.PROVIDER_FAILED: "The model could not be reached",
    UnavailableReason.GUARDRAIL_REJECTED: "The model stated a figure we did not measure",
    UnavailableReason.NO_PUBLISHED_FACTS: "Nothing on this screen is published yet",
    UnavailableReason.NOT_ASSESSABLE: "Too few calls to read this account",
    # --- Who a complaint was attributed to ---
    ComplaintAttribution.CHOICE: "Choice",
    ComplaintAttribution.BROKER: "Broker",
    ComplaintAttribution.CARRIER: "Carrier",
    ComplaintAttribution.PROVIDER: "Provider",
    # --- Who raised a process gap (schema field 15) ---
    RaisedBy.AGENT: "Agent",
    RaisedBy.CALLER: "Caller",
    # --- A process gap's own lifecycle: "a tag without one is a note." ---
    ProcessGapStatus.UNVALIDATED: "Not yet validated",
    ProcessGapStatus.VALIDATED: "Validated",
    ProcessGapStatus.ACTIONED: "Actioned",
    ProcessGapStatus.REJECTED: "Rejected",
    # --- Call Tag Schema field 3. Multi-valued; a call can touch several. ---
    ProductLine.DENTAL: "Dental",
    ProductLine.VISION: "Vision",
    ProductLine.LIFE: "Life",
    ProductLine.CHIRO: "Chiro",
    ProductLine.PROGRAM: "Program",
}

#: The Touchpoints sheet's own reference column — a slug, not prose, unlike
#: `Category`. Written out rather than derived for the same reason as
#: everything else in this module: a naive `replace("_", " ").title()` would
#: turn "denial_letter_eob" into "Denial Letter Eob".
#:
#: Not an `Enum`, so it cannot join `LABELLED_ENUMS`'s completeness check —
#: `call.tags.touchpoint` is free text an extraction produces, not a closed
#: set this application defines, and a call can legitimately name a
#: touchpoint the workbook's twelve rows do not cover. `touchpoint_label`
#: below is the fallback for exactly that case.
TOUCHPOINT_LABELS: dict[str, str] = {
    "enrolment_meeting": "Enrolment meeting",
    "enrolment_material": "Enrolment material",
    "enrolment_form": "Enrolment form",
    "welcome_pack": "Welcome pack",
    "id_card_mailer": "ID card mailer",
    "denial_letter_eob": "Denial letter / EOB",
    "invoice_statement": "Invoice / statement",
    "employer_portal": "Employer portal",
    "renewal_pack": "Renewal pack",
    "broker_material": "Broker material",
    "agent_conversation": "Agent conversation",
    "cobra_notice": "COBRA notice",
}


def touchpoint_label(reference: str) -> str:
    """A touchpoint's words, from the sheet where this application knows
    them and a plain reformatting where it does not.

    The fallback lower-cases then capitalises rather than title-casing —
    still a guess, but a smaller one than the naive derivation this
    module's docstring warns against, and only reached for a value nobody
    has written out yet.
    """
    known = TOUCHPOINT_LABELS.get(reference)
    if known is not None:
        return known
    return reference.replace("_", " ").capitalize()


#: The enums this module is responsible for. The completeness test walks
#: these, so adding one here without its members fails loudly rather than
#: shipping blank labels to a screen.
LABELLED_ENUMS: tuple[type[Enum], ...] = (
    Basis,
    Outcome,
    WithheldReason,
    SignalSeverity,
    SignalType,
    ControlExceptionType,
    RuleLayer,
    RuleConfidence,
    ComplaintAttribution,
    InsightKind,
    Severity,
    InsightsStatus,
    Lens,
    ProcessGapStatus,
    ProductLine,
    RaisedBy,
    UnavailableReason,
)


def coded(value: Enum) -> CodedValue:
    """One coded value, ready for the wire.

    Raises on an unlabelled member rather than falling back to the code. A
    fallback would put `process_gap_proposed` on a screen and nobody would
    notice for a release; a failure is noticed immediately, and the
    completeness test means it happens in CI rather than in front of a
    reader.
    """
    label = LABELS.get(value)
    if label is None:  # pragma: no cover - the completeness test prevents it
        raise KeyError(
            f"No display label for {type(value).__name__}.{value.name}. Add one to "
            "LABELS rather than letting a code reach a screen."
        )
    return CodedValue(code=str(value.value), label=label)
