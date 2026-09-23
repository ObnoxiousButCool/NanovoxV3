"""Call Tag Schema field 4's `attributed_to`.

Mandatory whenever `complaint.present` is true — an unattributed complaint
overstates CHOICE's own failure rate (the schema's own note). No EMPLOYER
value: that's the v10 proposal in plan §7A, not built.
"""

from __future__ import annotations

from enum import Enum


class ComplaintAttribution(str, Enum):
    CHOICE = "CHOICE"
    BROKER = "BROKER"
    CARRIER = "CARRIER"
    PROVIDER = "PROVIDER"
