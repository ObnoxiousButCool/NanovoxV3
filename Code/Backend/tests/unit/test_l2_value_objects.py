"""Invariants on the Call Tag Schema's compound fields: a present flag and
its dependent fields must agree with each other, not just have the right
types.
"""

from __future__ import annotations

import pytest

from domain.value_objects.broker_named_aloud import BrokerNamedAloud
from domain.value_objects.broker_sentiment import BrokerSentiment
from domain.value_objects.complaint import Complaint
from domain.value_objects.complaint_attribution import ComplaintAttribution


class TestComplaint:
    def test_present_without_an_attribution_is_rejected(self) -> None:
        # "Attribution is mandatory when present" — Call Tag Schema field 4.
        with pytest.raises(ValueError, match="must carry an attribution"):
            Complaint(present=True, attributed_to=None)

    def test_absent_with_an_attribution_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="must not carry an attribution"):
            Complaint(present=False, attributed_to=ComplaintAttribution.BROKER)

    def test_present_with_an_attribution_is_valid(self) -> None:
        complaint = Complaint(present=True, attributed_to=ComplaintAttribution.CARRIER)

        assert complaint.attributed_to is ComplaintAttribution.CARRIER

    def test_absent_with_no_attribution_is_valid(self) -> None:
        complaint = Complaint(present=False)

        assert complaint.attributed_to is None


class TestBrokerNamedAloud:
    def test_present_without_a_broker_ref_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="must carry a broker_ref and sentiment"):
            BrokerNamedAloud(present=True, broker_ref=None, sentiment=BrokerSentiment.ADVERSE)

    def test_present_without_a_sentiment_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="must carry a broker_ref and sentiment"):
            BrokerNamedAloud(present=True, broker_ref="BRK-02", sentiment=None)

    def test_absent_with_a_broker_ref_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="must not carry"):
            BrokerNamedAloud(present=False, broker_ref="BRK-02")

    def test_present_with_everything_set_is_valid(self) -> None:
        mention = BrokerNamedAloud(
            present=True,
            broker_ref="BRK-02",
            sentiment=BrokerSentiment.ADVERSE,
            matches_employer_of_record=False,
        )

        assert mention.matches_employer_of_record is False

    def test_absent_with_nothing_set_is_valid(self) -> None:
        mention = BrokerNamedAloud(present=False)

        assert mention.broker_ref is None
        assert mention.matches_employer_of_record is None
