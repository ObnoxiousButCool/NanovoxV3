"""`root_cause_owner` and `preventable` (Call Tag Schema fields 17-18, v10) —
computed, not extracted.

`Documents/notes/Corpus-v10-Decisions.md` items A/B and the schema's own note: "Derived
from complaint attribution first, then the dominant signal's owner."
Read as an algorithm over fields the pipeline already extracts, not a
new model judgement — the same shape as metric 4's repeat-contact and
member-effort-complexity, "computed, not extracted." A model asked to
produce this directly could disagree with the complaint and signals it is
supposed to summarise; a pure function cannot.

## The rule, in order

1. **A complaint's own attribution, when one exists, is the root cause.**
   `complaint.attributed_to` already names CHOICE/BROKER/CARRIER/PROVIDER —
   `RootCauseOwner` uses the same four names for exactly this reason.
2. **Otherwise, the most severe signal with a known root-cause owner.**
   Not every signal implies a party at fault — `broker_conduct_positive`,
   `retention_risk` and `revenue_opportunity` are symptoms or opportunities,
   not failures, and are left out of `_SIGNAL_ROOT_CAUSE` rather than forced
   onto one.
3. **Otherwise, `MEMBER_MISUNDERSTANDING`.** Not a residual bucket added to
   make the function total: the schema's own gap statement — "a third of
   calls carried no owner at all" — is closed by this exact case, and it is
   the single largest bucket in the real corpus (45%). A resolved,
   blameless call still gets an owner (`Documents/notes/Corpus-v10-Decisions.md` item A):
   otherwise the field would still leave the calls it exists to cover
   unaccounted for.

## A known, documented gap

Nothing here can produce `EMPLOYER` or `SYSTEM`. Neither
`complaint.attributed_to` (four values, none of them these two) nor any of
the thirteen signal types names "the employer's own action or omission"
or "two systems disagreeing" specifically enough to attribute deterministically
— and the corpus shows why this is a small gap rather than a disqualifying
one: `EMPLOYER` and `SYSTEM` are 1% of calls each in the 200-call sample.
Under-attributing 2% of calls is a documented limitation, not a silent
wrong answer; raising a model-based path for just these two is future
work, not assumed here.
"""

from __future__ import annotations

from domain.value_objects.complaint import Complaint
from domain.value_objects.preventable import Preventable
from domain.value_objects.root_cause_owner import RootCauseOwner
from domain.value_objects.signal import Signal
from domain.value_objects.signal_type import SEVERITY_ORDER, SignalType, severity_of

#: Which signal types imply a party at fault, and which one. Signals with
#: no entry here (broker_conduct_positive, retention_risk,
#: revenue_opportunity) are symptoms or opportunities, not failures, and
#: are skipped rather than forced onto an owner.
_SIGNAL_ROOT_CAUSE: dict[SignalType, RootCauseOwner] = {
    SignalType.MEMBER_COMMUNICATION_GAP: RootCauseOwner.CHOICE,
    SignalType.PROCESS_BREAKDOWN: RootCauseOwner.CHOICE,
    SignalType.COMPLIANCE_DISCLOSURE_MISSING: RootCauseOwner.CHOICE,
    SignalType.VERIFICATION_FAILURE: RootCauseOwner.CHOICE,
    SignalType.ESCALATION_MISSED: RootCauseOwner.CHOICE,
    SignalType.KNOWLEDGE_ERROR: RootCauseOwner.CHOICE,
    SignalType.BILLING_DEFECT: RootCauseOwner.CHOICE,
    SignalType.PROCESS_GAP_PROPOSED: RootCauseOwner.CHOICE,
    SignalType.BROKER_CONDUCT_ADVERSE: RootCauseOwner.BROKER,
    SignalType.NETWORK_ADEQUACY: RootCauseOwner.CARRIER,
}

#: CHOICE and SYSTEM: ours, directly fixable. PROVIDER: not ours to fix.
#: Everything else: partly, through someone else's lever (Root Cause sheet).
_PREVENTABLE_OF: dict[RootCauseOwner, Preventable] = {
    RootCauseOwner.CHOICE: Preventable.YES,
    RootCauseOwner.SYSTEM: Preventable.YES,
    RootCauseOwner.PROVIDER: Preventable.NO,
    RootCauseOwner.BROKER: Preventable.PARTLY,
    RootCauseOwner.CARRIER: Preventable.PARTLY,
    RootCauseOwner.EMPLOYER: Preventable.PARTLY,
    RootCauseOwner.MEMBER_MISUNDERSTANDING: Preventable.PARTLY,
}

#: A complaint's attribution shares these four names exactly. Written out
#: rather than relying on the string values matching by coincidence, so a
#: rename of either enum breaks loudly here instead of silently drifting.
_FROM_COMPLAINT: dict[str, RootCauseOwner] = {
    "CHOICE": RootCauseOwner.CHOICE,
    "BROKER": RootCauseOwner.BROKER,
    "CARRIER": RootCauseOwner.CARRIER,
    "PROVIDER": RootCauseOwner.PROVIDER,
}


def root_cause_owner(complaint: Complaint, signals: tuple[Signal, ...]) -> RootCauseOwner:
    """Complaint attribution first, then the most severe signal with a
    known owner, else `MEMBER_MISUNDERSTANDING`."""
    if complaint.present and complaint.attributed_to is not None:
        return _FROM_COMPLAINT[complaint.attributed_to.value]

    by_severity = sorted(signals, key=lambda signal: SEVERITY_ORDER.index(severity_of(signal.type)))
    for signal in by_severity:
        owner = _SIGNAL_ROOT_CAUSE.get(signal.type)
        if owner is not None:
            return owner

    return RootCauseOwner.MEMBER_MISUNDERSTANDING


def preventable_of(owner: RootCauseOwner) -> Preventable:
    return _PREVENTABLE_OF[owner]
