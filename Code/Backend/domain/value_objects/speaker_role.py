"""Which side of the call a turn belongs to.

Resolved, never assumed: both speakers in the v9 transcripts are labelled by
first name, so an "unqualified name is the agent" rule (NanoVox's own) would
make every turn the agent's. See `domain/speaker_resolution.py`.
"""

from __future__ import annotations

from enum import Enum


class SpeakerRole(str, Enum):
    AGENT = "AGENT"
    CALLER = "CALLER"
