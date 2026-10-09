"""The Brokers table's risk column (leadership, 2026-10-09).

High when the pattern test has already fired or two-plus accounts are
independently flagged; medium on any single flagged account or any adverse
mention short of the pattern threshold; low otherwise. See
`domain.aggregation.isolation.broker_risk_tier`'s own docstring for why
this is not sourced from the Metrics sheet.
"""

from __future__ import annotations

from domain.aggregation.isolation import broker_risk_tier
from domain.value_objects.broker_risk_tier import BrokerRiskTier


def test_nothing_against_the_broker_is_low() -> None:
    tier = broker_risk_tier(flagged_accounts=0, adverse_mentions=0, pattern_fires=False)

    assert tier is BrokerRiskTier.LOW


def test_one_flagged_account_alone_is_medium() -> None:
    tier = broker_risk_tier(flagged_accounts=1, adverse_mentions=0, pattern_fires=False)

    assert tier is BrokerRiskTier.MEDIUM


def test_an_adverse_mention_alone_is_medium_even_with_no_flagged_account() -> None:
    tier = broker_risk_tier(flagged_accounts=0, adverse_mentions=1, pattern_fires=False)

    assert tier is BrokerRiskTier.MEDIUM


def test_two_flagged_accounts_is_high_even_with_no_adverse_mentions() -> None:
    tier = broker_risk_tier(flagged_accounts=2, adverse_mentions=0, pattern_fires=False)

    assert tier is BrokerRiskTier.HIGH


def test_the_pattern_test_firing_is_high_even_with_no_flagged_accounts() -> None:
    # The pattern test's own threshold (3+ adverse mentions from 2+
    # employers) is reached independently of the flagged-accounts count.
    tier = broker_risk_tier(flagged_accounts=0, adverse_mentions=3, pattern_fires=True)

    assert tier is BrokerRiskTier.HIGH


def test_many_adverse_mentions_short_of_the_pattern_threshold_is_still_medium() -> None:
    # Mentions alone, however many, do not reach High without the pattern
    # test actually firing — that threshold (2+ distinct employers) is not
    # reproduced here.
    tier = broker_risk_tier(flagged_accounts=0, adverse_mentions=10, pattern_fires=False)

    assert tier is BrokerRiskTier.MEDIUM
