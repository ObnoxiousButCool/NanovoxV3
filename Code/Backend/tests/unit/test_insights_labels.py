"""Every coded value a screen shows has words for it.

The completeness test is the point of the file. A missing label renders as
a blank cell, which reads as "nothing here" rather than as "we forgot to
name this" — so it has to fail in CI instead.
"""

from __future__ import annotations

from enum import Enum

import pytest

from domain.aggregation.figure import Basis, WithheldReason
from domain.value_objects.rule_layer import RuleLayer
from domain.value_objects.signal_type import SignalType
from frameworks_drivers.api.v1.insights.labels import LABELLED_ENUMS, LABELS, coded


@pytest.mark.parametrize("enum", LABELLED_ENUMS, ids=lambda enum: enum.__name__)
def test_every_member_has_a_label(enum: type[Enum]) -> None:
    """Adding a signal type without wording fails here, not on a screen."""
    missing = [member.name for member in enum if member not in LABELS]

    assert not missing, f"{enum.__name__} members with no display label: {missing}"


def test_no_label_is_blank_or_still_a_code() -> None:
    """A label that is just the code back again is not a label."""
    for member, label in LABELS.items():
        assert label.strip(), f"{member} has an empty label"
        assert label != member.value, f"{member} was labelled with its own code"


def test_a_code_travels_with_its_label() -> None:
    """The code is the contract; filters take it, not the prose."""
    value = coded(SignalType.BILLING_DEFECT)

    assert value.code == "billing_defect"
    assert value.label == "Billing defect"


def test_the_rule_layer_codes_become_words() -> None:
    """'P' is the clearest case for the whole map."""
    assert coded(RuleLayer.PROGRAM).label == "Program"
    assert coded(RuleLayer.PROGRAM).code == "P"


def test_withheld_reasons_read_differently_from_each_other() -> None:
    """More calls fixes one; only a schema change fixes another."""
    below = coded(WithheldReason.BELOW_MIN_N).label
    no_field = coded(WithheldReason.NO_FIELD).label
    not_eligible = coded(WithheldReason.NOT_ELIGIBLE).label

    assert len({below, no_field, not_eligible}) == 3
    assert "schema" in no_field


def test_labels_are_not_naive_title_case() -> None:
    """The derivation this module refuses would produce 'Billing Defect'."""
    assert coded(SignalType.BILLING_DEFECT).label != "Billing Defect"
    assert coded(Basis.OBSERVED).label == "Observed"
