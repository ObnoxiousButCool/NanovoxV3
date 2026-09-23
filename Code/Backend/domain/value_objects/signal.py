"""One raised signal, evidence-anchored (Call Tag Schema field 5).

"Zero or more. Distinct types, deduplicated per call." Severity is never
stored on the instance — it's derived from `type` via
`domain.value_objects.signal_type.severity_of`, so it can't drift from
the taxonomy.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.value_objects.signal_type import SignalType


@dataclass(frozen=True)
class Signal:
    type: SignalType
    quote: str
    turn_seq: int
