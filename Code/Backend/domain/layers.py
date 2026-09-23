"""Which extraction layers each workbook metric needs, and which layers this
pipeline currently treats as essential.

The workbook's Call Tag Schema sheet names four extraction layers in its
"Emitted by" column — L1 deterministic extraction, L2 classification, L3
quality & knowledge, L4 signals & gaps (see plan §7; checked every sheet,
nothing beyond L4 exists). This module answers a different, narrower
question than that column: not "which layer writes this *tag*" but "which
layers does a given *metric*, from the Metrics sheet, need before it can be
computed at all."

Essential is a consequence of that mapping, not a choice made independently
(plan §2A.3): a layer is essential exactly when some metric here can't be
computed without it. ``ESSENTIAL_LAYERS`` is still declared as its own,
independent constant — not derived by unioning the mapping — so that
:mod:`tests.unit.test_layers` has something real to check: if a metric is
ever added or re-scoped to need a layer nobody has marked essential, the
test fails instead of that metric silently under-serving withheld data.
"""

from __future__ import annotations

from enum import Enum


class Layer(str, Enum):
    """An extraction layer, named exactly as the Call Tag Schema names it."""

    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


# Metrics sheet row (the "#" column there) → the layers it reads from.
# Base measures B1 (call volume) and B2 (AHT) need only L1's telephony pass
# and aren't metrics in their own right, so they're absent here.
REQUIRED_LAYERS_BY_METRIC: dict[str, frozenset[Layer]] = {
    # 1 Contact rate — dimensioned by product line (L2); population join via
    # caller_ref (L1).
    "1": frozenset({Layer.L1, Layer.L2}),
    # 2 Complaint rate — complaint.present / .attributed_to (L2).
    "2": frozenset({Layer.L1, Layer.L2}),
    # 3 First-contact resolution — outcome (L2).
    "3": frozenset({Layer.L1, Layer.L2}),
    # 4 Failure-driven repeat rate — outcome (L2); the repeat match itself is
    # deterministic, not an extraction layer.
    "4": frozenset({Layer.L1, Layer.L2}),
    # 5 Self-inflicted demand — outcome (L2) for the failure-driven-repeat
    # component, process_gap (L4) for the logged-process-defect component.
    "5": frozenset({Layer.L1, Layer.L2, Layer.L4}),
    # 6 Escalation integrity — escalation.triggered (L2), .handled /
    # .trigger_type (L4).
    "6": frozenset({Layer.L1, Layer.L2, Layer.L4}),
    # 7 Control exception rate — control_exceptions (L1 detection, L3
    # scoring).
    "7": frozenset({Layer.L1, Layer.L3}),
    # 8 Knowledge failure rate — knowledge_failure (L3).
    "8": frozenset({Layer.L1, Layer.L3}),
    # 9 Cost to serve — aht_seconds (L1, telephony); dimensioned by product
    # line (L2).
    "9": frozenset({Layer.L1, Layer.L2}),
    # 10 Account risk flag — complaint rate, failure-driven repeat,
    # market_test intent and CHOICE-attributed UNRESOLVED all read L2; the
    # ten indicator families rendered alongside it on the account page
    # (insight 1) read signals (L4).
    "10": frozenset({Layer.L1, Layer.L2, Layer.L4}),
    # 11 Commercial intent capture — intent, with the routed flag (L2; the
    # routed facet itself is a join to the Action Centre, not an extraction
    # layer).
    "11": frozenset({Layer.L1, Layer.L2}),
    # 12 Agent quality score — markers / quality_score (L3).
    "12": frozenset({Layer.L1, Layer.L3}),
}

# The layers this pipeline currently treats as essential. Declared
# independently of the mapping above — see the module docstring for why.
ESSENTIAL_LAYERS: frozenset[Layer] = frozenset({Layer.L1, Layer.L2, Layer.L3, Layer.L4})
