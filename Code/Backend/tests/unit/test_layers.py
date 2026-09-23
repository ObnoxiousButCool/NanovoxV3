"""A layer is essential iff some metric needs it (plan §2A.3) — this is the
test that catches drift between the two if either is edited alone.
"""

from __future__ import annotations

import pytest

from domain.layers import ESSENTIAL_LAYERS, REQUIRED_LAYERS_BY_METRIC, Layer


@pytest.mark.parametrize("metric", sorted(REQUIRED_LAYERS_BY_METRIC))
def test_every_metrics_required_layer_is_essential(metric: str) -> None:
    required = REQUIRED_LAYERS_BY_METRIC[metric]

    missing = required - ESSENTIAL_LAYERS
    assert not missing, f"metric {metric} needs {missing}, which isn't marked essential"


def test_every_layer_is_required_by_at_least_one_metric() -> None:
    """The converse check: nothing is essential by fiat, only by metric demand."""
    required_anywhere = frozenset().union(*REQUIRED_LAYERS_BY_METRIC.values())

    assert required_anywhere == ESSENTIAL_LAYERS


def test_no_metric_is_required_layers_empty() -> None:
    """Every metric reads at least L1 — caller_ref underlies every join."""
    for metric, required in REQUIRED_LAYERS_BY_METRIC.items():
        assert Layer.L1 in required, f"metric {metric} has no caller_ref join"
