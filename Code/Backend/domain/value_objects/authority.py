"""Whether an employer contact can bind the group.

Employer Contacts sheet, column "Authority": ``can bind`` / ``cannot bind``.
Decides what an agent may action on a call without a second approval, and
gates insight 3 (authority-weighted exit language) — exit language only
counts toward the exit family from a `CAN_BIND` contact.
"""

from __future__ import annotations

from enum import StrEnum


class Authority(StrEnum):
    CAN_BIND = "can bind"
    CANNOT_BIND = "cannot bind"
