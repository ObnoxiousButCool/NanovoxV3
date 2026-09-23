"""Resolving which speaker label is the agent and which is the caller.

Both speakers in the v9 transcripts are labelled by first name — "Sarah:"
and " Leon:" — so an unqualified-name-is-the-agent rule (NanoVox's own)
would make every turn the agent's. Resolved instead by matching the
transcript header's own agent name (a legitimate input, §6.3) against the
dialogue's speaker labels: whichever label equals the agent's first name is
the agent, the other is the caller.

Never guessed: exactly one match is required. Anything else — no speakers,
one speaker, three or more, an agent name that matches none of them —
returns a stated reason instead of a resolution. Verified against all 100
calls in batch 1: every one has exactly two distinct labels and exactly one
matches the header's agent name (see
`tests/unit/test_speaker_resolution.py`), but the corpus growing to 600
calls is exactly the kind of change this function has to survive without
being rewritten.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.entities.turn import Turn
from domain.value_objects.speaker_role import SpeakerRole


@dataclass(frozen=True)
class RawTurn:
    """One line of dialogue as parsed from the source, before role resolution."""

    label: str
    text: str


@dataclass(frozen=True)
class SpeakerResolution:
    """Either resolved turns, or a reason nothing was guessed."""

    turns: tuple[Turn, ...] | None
    unresolved_reason: str | None

    @property
    def is_resolved(self) -> bool:
        return self.turns is not None


def resolve_speaker_roles(
    agent_first_name: str, raw_turns: tuple[RawTurn, ...]
) -> SpeakerResolution:
    """Assign `SpeakerRole` to every turn, or explain why none was assigned."""
    labels = sorted({turn.label for turn in raw_turns})

    if len(labels) != 2:
        return SpeakerResolution(
            turns=None,
            unresolved_reason=f"expected exactly two speakers, found {len(labels)}: {labels}",
        )

    matches = [label for label in labels if label == agent_first_name]
    if not matches:
        return SpeakerResolution(
            turns=None,
            unresolved_reason=(
                f"agent name {agent_first_name!r} matches none of the speaker labels {labels}"
            ),
        )
    agent_label = matches[0]

    turns = tuple(
        Turn(
            role=SpeakerRole.AGENT if raw.label == agent_label else SpeakerRole.CALLER,
            text=raw.text,
        )
        for raw in raw_turns
    )
    return SpeakerResolution(turns=turns, unresolved_reason=None)
