"""A transcript's content hash: the stage cache's key ingredient (plan §7).

A cache keyed on the call reference alone would keep serving a stale
answer after the transcript behind it changed (a caller-resolution fix, a
re-ingested PDF); hashing the content means that's simply a cache miss.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

from domain.entities.transcript import Transcript
from domain.entities.turn import Turn
from domain.transcript_hash import content_hash
from domain.value_objects.call_source import CallSource
from domain.value_objects.caller_type import CallerType
from domain.value_objects.speaker_role import SpeakerRole

_BASE = Transcript(
    reference="C-0001",
    source=CallSource.CORPUS_PDF,
    occurred_at=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
    aht_seconds=300,
    caller_type=CallerType.MEMBER,
    caller_ref="CB-7700205",
    agent_ref="AGT-01",
    agent_name="Sarah Whitlock",
    turns=(
        Turn(role=SpeakerRole.AGENT, text="How can I help?"),
        Turn(role=SpeakerRole.CALLER, text="I have a question about my claim."),
    ),
)


def _transcript(**overrides: Any) -> Transcript:
    return replace(_BASE, **overrides)


def test_the_same_transcript_hashes_the_same_way_every_time() -> None:
    assert content_hash(_transcript()) == content_hash(_transcript())


def test_different_dialogue_changes_the_hash() -> None:
    other = _transcript(
        turns=(
            Turn(role=SpeakerRole.AGENT, text="How can I help?"),
            Turn(role=SpeakerRole.CALLER, text="A completely different question."),
        )
    )

    assert content_hash(_transcript()) != content_hash(other)


def test_a_corrected_caller_ref_changes_the_hash() -> None:
    # A caller-resolution fix changes what L1 and every layer after it sees,
    # just as much as different words would.
    assert content_hash(_transcript()) != content_hash(_transcript(caller_ref="CB-7700001"))


def test_a_corrected_agent_name_changes_the_hash() -> None:
    assert content_hash(_transcript()) != content_hash(_transcript(agent_name="Someone Else"))


def test_turn_order_matters() -> None:
    reordered = _transcript(
        turns=(
            Turn(role=SpeakerRole.CALLER, text="I have a question about my claim."),
            Turn(role=SpeakerRole.AGENT, text="How can I help?"),
        )
    )

    assert content_hash(_transcript()) != content_hash(reordered)


def test_a_missing_occurred_at_does_not_crash() -> None:
    # occurred_at is optional on the entity; the hash must still be computable.
    assert content_hash(_transcript(occurred_at=None))


def test_a_missing_aht_seconds_does_not_crash() -> None:
    assert content_hash(_transcript(aht_seconds=None))


def test_the_digest_is_a_sha256_hex_string() -> None:
    digest = content_hash(_transcript())

    assert len(digest) == 64
    assert all(char in "0123456789abcdef" for char in digest)
