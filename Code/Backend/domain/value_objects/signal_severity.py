"""How urgently a signal should be routed (Signal Taxonomy sheet).

A property of the signal *type*, never something a model assigns per
instance — see `domain/value_objects/signal_type.py::SEVERITY_OF` for the
fixed mapping every signal is scored against.
"""

from __future__ import annotations

from enum import StrEnum


class SignalSeverity(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
