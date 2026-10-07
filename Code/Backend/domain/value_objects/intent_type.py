"""Call Tag Schema field 9. Verbatim statements only, with a turn
reference — "inferred intent is an opinion and will be treated as one"
(the schema's own note).
"""

from __future__ import annotations

from enum import StrEnum


class IntentType(StrEnum):
    EXPANSION = "expansion"
    MARKET_TEST = "market_test"
    CANCELLATION = "cancellation"
    NONE = "none"
