"""What produced an action (plan §8 Phase 9, Revised plan Phase 4).

One per grouping the prototype's `add_action` seeds from
(`Prototype/tools/04_build_app_data.py`), plus `manual` for a card someone
raised on the board. A playbook names the kind it produces, so the focused
action view can show "already in progress" for the issue in front of it.
"""

from __future__ import annotations

from enum import Enum


class ActionSourceKind(str, Enum):
    PROCESS_GAP = "process_gap"
    KNOWLEDGE_FAILURE = "knowledge_failure"
    ESCALATION_MISSED = "escalation_missed"
    RETENTION_RISK = "retention_risk"
    CONTROL_EXCEPTION = "control_exception"
    #: Questions Worth Asking trigger 2 — a broker with adverse mentions
    #: across several employers.
    BROKER_PATTERN = "broker_pattern"
    MANUAL = "manual"
