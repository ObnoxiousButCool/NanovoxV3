"""L4 — signals & gaps (plan §7): `signals`, the agent-action half of
`escalation`, `control_exceptions` confirmed, `process_gap`, and a
confirmed `touchpoint`.

Runs concurrently with L3, after L2 — both read L2's classification but
never each other's output (plan §7: "L3 and L4 run concurrently after
L2").
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.value_objects.escalation_trigger_type import EscalationTriggerType
from domain.value_objects.process_gap import ProcessGap
from domain.value_objects.signal import Signal


@dataclass(frozen=True)
class L4SignalsAndGaps:
    signals: tuple[Signal, ...]
    escalation_handled: bool
    #: None when L2 found no escalation trigger at all — L4 classifies
    #: *which* condition fired, but only when L2 already established that
    #: one did.
    escalation_trigger_type: EscalationTriggerType | None
    process_gap: ProcessGap
    #: L4's confirmed touchpoint, which may revise L2's first pass
    #: (Call Tag Schema field 16, "Emitted by: L2/L4").
    touchpoint: str | None
