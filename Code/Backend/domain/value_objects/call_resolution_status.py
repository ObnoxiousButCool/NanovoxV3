"""How much of a call ingestion actually resolved.

A call is never silently dropped for failing to resolve (plan's Phase 2
rules) — it's persisted either way, with a status naming exactly what
didn't work, so downstream aggregation can exclude it explicitly and count
the exclusion rather than the call quietly not existing.
"""

from __future__ import annotations

from enum import Enum


class CallResolutionStatus(str, Enum):
    #: Speaker roles, the agent and the caller all resolved.
    RESOLVED = "RESOLVED"
    #: Speaker roles resolved, but caller_ref doesn't match a known member
    #: or employer contact. Excluded from employer metrics (counted, not
    #: dropped).
    CALLER_UNRESOLVED = "CALLER_UNRESOLVED"
    #: Speaker roles resolved, but the header's agent_ref isn't among the
    #: known agents Phase 1 imported — the transcript is usable, the agent
    #: attribution isn't trusted.
    AGENT_UNKNOWN = "AGENT_UNKNOWN"
    #: Could not tell which of the two speakers was the agent — the
    #: transcript itself is unusable, not just the employer join. Never
    #: guessed.
    SPEAKER_UNRESOLVED = "SPEAKER_UNRESOLVED"
