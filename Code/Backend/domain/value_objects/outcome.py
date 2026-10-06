"""Call Tag Schema field 1 — the single field the most metrics key off.

Four values, and a decision order for applying the Outcomes sheet's own
tests: ESCALATED's three-part test (named owner outside the agent's
authority, a reference, a committed timeframe) is checked first, because
it is the strictest and most easily masked by a partial match; then
PARTIALLY RESOLVED's two-part test; then RESOLVED's "no open action
remains"; UNRESOLVED is the default when none of the above hold.
"""

from __future__ import annotations

from enum import StrEnum


class Outcome(StrEnum):
    RESOLVED = "RESOLVED"
    PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED"
    ESCALATED = "ESCALATED"
    UNRESOLVED = "UNRESOLVED"
