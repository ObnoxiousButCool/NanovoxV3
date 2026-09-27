"""`root_cause_owner`/`preventable_of` — computed, not extracted."""

from __future__ import annotations

import pytest

from domain.derivations.root_cause import preventable_of, root_cause_owner
from domain.value_objects.complaint import Complaint
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.preventable import Preventable
from domain.value_objects.root_cause_owner import RootCauseOwner
from domain.value_objects.signal import Signal
from domain.value_objects.signal_type import SignalType

_NO_COMPLAINT = Complaint(present=False)


def _signal(signal_type: SignalType) -> Signal:
    return Signal(type=signal_type, quote="quote", turn_seq=0)


@pytest.mark.parametrize(
    ("attribution", "expected"),
    [
        (ComplaintAttribution.CHOICE, RootCauseOwner.CHOICE),
        (ComplaintAttribution.BROKER, RootCauseOwner.BROKER),
        (ComplaintAttribution.CARRIER, RootCauseOwner.CARRIER),
        (ComplaintAttribution.PROVIDER, RootCauseOwner.PROVIDER),
    ],
)
def test_a_complaints_own_attribution_is_the_root_cause(
    attribution: ComplaintAttribution, expected: RootCauseOwner
) -> None:
    """A complaint's attribution, when one exists, wins over any signal —
    even one that would otherwise point elsewhere."""
    complaint = Complaint(present=True, attributed_to=attribution)
    signals = (_signal(SignalType.BROKER_CONDUCT_ADVERSE),)

    assert root_cause_owner(complaint, signals) is expected


def test_with_no_complaint_the_most_severe_owned_signal_wins() -> None:
    """verification_failure is CRITICAL (Compliance), billing_defect is
    HIGH (CHOICE) — the critical one must win regardless of order."""
    signals = (_signal(SignalType.BILLING_DEFECT), _signal(SignalType.VERIFICATION_FAILURE))

    assert root_cause_owner(_NO_COMPLAINT, signals) is RootCauseOwner.CHOICE


def test_broker_conduct_adverse_points_to_the_broker() -> None:
    assert (
        root_cause_owner(_NO_COMPLAINT, (_signal(SignalType.BROKER_CONDUCT_ADVERSE),))
        is RootCauseOwner.BROKER
    )


def test_network_adequacy_points_to_the_carrier() -> None:
    assert (
        root_cause_owner(_NO_COMPLAINT, (_signal(SignalType.NETWORK_ADEQUACY),))
        is RootCauseOwner.CARRIER
    )


@pytest.mark.parametrize(
    "signal_type",
    [SignalType.BROKER_CONDUCT_POSITIVE, SignalType.RETENTION_RISK, SignalType.REVENUE_OPPORTUNITY],
)
def test_signals_that_are_not_failures_do_not_attribute_a_fault(signal_type: SignalType) -> None:
    """A positive mention, exit language and an upsell opportunity are not
    failures — none of them should force an owner onto a call that has
    none."""
    assert (
        root_cause_owner(_NO_COMPLAINT, (_signal(signal_type),))
        is RootCauseOwner.MEMBER_MISUNDERSTANDING
    )


def test_a_call_with_no_complaint_and_no_owned_signal_is_member_misunderstanding() -> None:
    """The fallback the schema's own gap statement describes: 'a third of
    calls carried no owner at all.' A blameless, resolved call still gets
    one (Corpus-v10-Decisions.md item A)."""
    assert root_cause_owner(_NO_COMPLAINT, ()) is RootCauseOwner.MEMBER_MISUNDERSTANDING


@pytest.mark.parametrize(
    ("owner", "expected"),
    [
        (RootCauseOwner.CHOICE, Preventable.YES),
        (RootCauseOwner.SYSTEM, Preventable.YES),
        (RootCauseOwner.PROVIDER, Preventable.NO),
        (RootCauseOwner.BROKER, Preventable.PARTLY),
        (RootCauseOwner.CARRIER, Preventable.PARTLY),
        (RootCauseOwner.EMPLOYER, Preventable.PARTLY),
        (RootCauseOwner.MEMBER_MISUNDERSTANDING, Preventable.PARTLY),
    ],
)
def test_preventable_is_a_pure_function_of_the_owner(
    owner: RootCauseOwner, expected: Preventable
) -> None:
    assert preventable_of(owner) is expected
