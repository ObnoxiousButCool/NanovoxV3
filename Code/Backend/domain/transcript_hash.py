"""A stable content hash for a transcript.

The stage-output cache (plan §7, "Cache layer outputs keyed by (transcript
hash, layer, prompt version, model)") keys on this rather than on the call
reference: a call reference is stable across a correction, but the content
behind it isn't, and a cache keyed on the reference alone would keep
serving a stale layer output after the transcript it was computed from had
changed underneath it (a caller-resolution fix, a re-ingest of a corrected
PDF). Hashing the content means a changed transcript is simply a cache
miss, not a correctness bug to remember to invalidate by hand.

Pure and deterministic: no I/O, no clock, no randomness (plan §2A.1) — the
same ``Transcript`` always hashes to the same string, on any machine.
"""

from __future__ import annotations

import hashlib

from domain.entities.transcript import Transcript

_FIELD_SEPARATOR = "\x1f"  # unlikely to occur in transcript text
_TURN_SEPARATOR = "\x1e"


def content_hash(transcript: Transcript) -> str:
    """A hex digest over every field that could change what a layer produces.

    Everything on the entity is included, not just ``turns``: a corrected
    ``caller_ref`` or ``agent_name`` changes what a layer sees just as much
    as different dialogue would, and both must miss the cache rather than
    silently reuse an answer computed against the old value.
    """
    parts = [
        transcript.reference,
        transcript.source.value,
        transcript.occurred_at.isoformat() if transcript.occurred_at is not None else "",
        str(transcript.aht_seconds) if transcript.aht_seconds is not None else "",
        transcript.caller_type.value,
        transcript.caller_ref,
        transcript.agent_ref,
        transcript.agent_name,
    ]
    turns = _TURN_SEPARATOR.join(f"{turn.role.value}:{turn.text}" for turn in transcript.turns)
    parts.append(turns)

    digest_input = _FIELD_SEPARATOR.join(parts).encode("utf-8")
    return hashlib.sha256(digest_input).hexdigest()
