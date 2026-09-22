"""The result of ingesting one call: its transcript, if usable, plus what resolved.

Persisted whatever the outcome — a call is never silently dropped for
failing to resolve (plan's Phase 2 rules). `transcript` is `None` exactly
when `resolution_status` is `SPEAKER_UNRESOLVED`: the header always parses
(caller type/ref and agent ref are legitimate inputs, independent of
dialogue), but there is no usable transcript without resolved speaker
roles. `member_ref`/`employer_contact_ref`/`employer_ref` are `None` when
caller resolution didn't happen, not guessed at.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.entities.transcript import Transcript
from domain.value_objects.call_resolution_status import CallResolutionStatus
from domain.value_objects.caller_type import CallerType


@dataclass(frozen=True)
class IngestedCall:
    reference: str
    caller_type: CallerType
    caller_ref: str
    agent_ref: str
    transcript: Transcript | None
    resolution_status: CallResolutionStatus
    resolution_reason: str | None
    member_ref: str | None
    employer_contact_ref: str | None
    employer_ref: str | None
