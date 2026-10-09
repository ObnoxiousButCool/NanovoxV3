"""The Brokers table's risk column (leadership, 2026-10-09).

Deliberately a value of its own, not a reuse of the employer risk flag's
`StatusTone` (`frameworks_drivers`' `StatusPill`) — the two are built from
different signals and answer different questions, and reusing one state
vocabulary for both is the exact failure D12 named for the employer screen:
"two scoring systems on one page, one of which quietly feeds the other."

See `domain.aggregation.isolation.broker_risk_tier` for the rule this
tiers, and `Documents/notes/Decisions-and-Questions.md` for why the
threshold is what it is and what it is not validated against.
"""

from __future__ import annotations

from enum import StrEnum


class BrokerRiskTier(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
