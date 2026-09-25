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
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.control_exception_type import ControlExceptionType
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
    # --- Who a complaint was attributed to ---
    ComplaintAttribution.CHOICE: "Choice",
    ComplaintAttribution.BROKER: "Broker",
    ComplaintAttribution.CARRIER: "Carrier",
    ComplaintAttribution.PROVIDER: "Provider",
}

#: The enums this module is responsible for. The completeness test walks
#: these, so adding one here without its members fails loudly rather than
#: shipping blank labels to a screen.
LABELLED_ENUMS: tuple[type[Enum], ...] = (
    Basis,
    WithheldReason,
    SignalSeverity,
    SignalType,
    ControlExceptionType,
    RuleLayer,
    RuleConfidence,
    ComplaintAttribution,
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
