"""Call Tag Schema field 3. Multi-valued — shares exceed 100%.

Contact rate (Metrics sheet metric 1) uses a single primary line to avoid
double counting; this enum only names what a call can touch, not which
line owns the call.
"""

from __future__ import annotations

from enum import Enum


class ProductLine(str, Enum):
    DENTAL = "dental"
    VISION = "vision"
    LIFE = "life"
    CHIRO = "chiro"
    PROGRAM = "program"
