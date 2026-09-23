---
id: l4_signals
version: 1.0.0
description: L4 — signals, the agent-action half of escalation, a confirmed process gap, and a confirmed touchpoint.
---
You are looking for structural and account-level findings on one call for a health-benefits call centre (ChoiceBuilder). Read the transcript below and answer strictly according to the schema. Every claim must be something a reader could check against the transcript.

TRANSCRIPT (turn 0 first):
{transcript}

RULES that may apply to this call (for context only):
{rules}

L2 already found: escalation_triggered={escalation_triggered}, escalation_requested_by_caller={escalation_requested_by_caller}, first-pass touchpoint={l2_touchpoint}.

Answer these fields:

**signals** — every distinct signal type this call raises, zero or more, each with the exact quote and turn number (0-indexed) it came from. A signal is counted once per call even if it recurs. Choose only from:
- member_communication_gap: something the member should have been told at enrollment and was not (surprise cost, exclusion, waiting period).
- process_breakdown: an internal process accepted an input and failed to act on it (portal submission not applied, ID never issued, termination still billing).
- compliance_disclosure_missing: a required disclosure was not made (no recording notice, benefit limit not stated where required).
- verification_failure: member detail disclosed before identity verification completed.
- broker_conduct_adverse: a broker action or omission caused the member's problem (misstated rule at sale, unsubmitted election, unresponsive for weeks).
- broker_conduct_positive: the broker prepared the client well and shortened the call.
- escalation_missed: an explicit escalation request went nowhere and no alternative was offered.
- retention_risk: explicit exit or market-test language (going out to bid, moving at renewal, cancelling).
- revenue_opportunity: interest in a line the group does not hold.
- knowledge_error: an agent stated a published rule incorrectly (waiting period type confused, out-of-state availability misstated). This is the on-call agent-conduct event — separate from any knowledge_failure L3 may have found; judge it independently.
- network_adequacy: a covered benefit is unusable where the member lives or works.
- billing_defect: an invoice does not match the enrolled roster (terminated employee still billing, new hire missing).
- process_gap_proposed: an improvement to a document, system or process proposed or clearly implied inside the call.

**escalation_handled** — was ownership of the issue actually transferred to a named party with a reference, by the agent? True only when the agent's own actions did this, regardless of whether escalation_triggered was true.

**escalation_trigger_type** — if escalation_triggered is true (see above), which single condition fired: caller_request, compliance_exception, contested_document, retention_risk, clinical_or_safety_risk, scheduled_care_at_risk, authority_limit, or broker_conduct_adverse. If escalation_triggered is false, answer NONE.

**process_gap** — {{present, gap_type, touchpoint, proposed_change, raised_by, status}}. Present is true only when the call proposes or clearly implies a structural improvement to a document, system or process — distinct from a plain complaint that something failed. gap_type is a short label for the kind of gap (e.g. "denial letter missing detail"). touchpoint is where in the member/employer journey the gap originates, if you can tell, else empty string. proposed_change is what should change, in one sentence. raised_by is AGENT or CALLER depending on who proposed or implied it — NONE if present is false. status is always UNVALIDATED for a gap raised for the first time on this call (this pipeline does not yet check calls against previously logged gaps) — NONE if present is false.

**touchpoint** — confirm or revise L2's first-pass touchpoint (shown above) with the fuller picture of the call now available: a short lowercase snake_case reference to where in the member/employer journey the call's issue originated, or empty string if you cannot tell.
