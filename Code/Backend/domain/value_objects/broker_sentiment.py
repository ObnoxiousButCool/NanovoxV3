"""Call Tag Schema field 14's `sentiment` — set only once `present` is true."""

from __future__ import annotations

from enum import Enum


class BrokerSentiment(str, Enum):
    ADVERSE = "ADVERSE"
    POSITIVE = "POSITIVE"
