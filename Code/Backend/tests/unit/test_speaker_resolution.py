"""Speaker role resolution — never an "unqualified name is the agent" guess."""

from __future__ import annotations

from domain.speaker_resolution import RawTurn, resolve_speaker_roles
from domain.value_objects.speaker_role import SpeakerRole


def test_resolves_c0001_by_matching_the_agent_name_against_the_labels() -> None:
    """C-0001's header names the agent "Sarah Whitlock"; the dialogue is
    labelled "Sarah" and "Leon". Sarah is the agent because her name
    matches, not because she spoke first.
    """
    raw_turns = (
        RawTurn(label="Sarah", text="Choice Administrators, Sarah speaking."),
        RawTurn(label="Leon", text="Leon Castellano. CB-7700205."),
        RawTurn(label="Sarah", text="Thanks Leon, I have you."),
    )

    resolution = resolve_speaker_roles("Sarah", raw_turns)

    assert resolution.is_resolved
    turns = resolution.turns
    assert turns is not None
    assert turns[0].role is SpeakerRole.AGENT
    assert turns[0].text == "Choice Administrators, Sarah speaking."
    assert turns[1].role is SpeakerRole.CALLER
    assert turns[1].text == "Leon Castellano. CB-7700205."
    assert turns[2].role is SpeakerRole.AGENT


def test_does_not_assume_whoever_speaks_first_or_is_unqualified_is_the_agent() -> None:
    """The trap this function exists to avoid: NanoVox's own rule would
    make the caller the agent here, since "Leon" speaks first and neither
    label is qualified with a title.
    """
    raw_turns = (
        RawTurn(label="Leon", text="Hi, I have a question."),
        RawTurn(label="Sarah", text="Sure, go ahead."),
    )

    resolution = resolve_speaker_roles("Sarah", raw_turns)

    assert resolution.turns is not None
    assert resolution.turns[0].role is SpeakerRole.CALLER
    assert resolution.turns[1].role is SpeakerRole.AGENT


def test_unresolved_when_there_are_not_exactly_two_speakers() -> None:
    raw_turns = (RawTurn(label="Sarah", text="Hello?"),)

    resolution = resolve_speaker_roles("Sarah", raw_turns)

    assert not resolution.is_resolved
    assert resolution.turns is None
    assert resolution.unresolved_reason is not None
    assert "found 1" in resolution.unresolved_reason


def test_unresolved_when_three_speakers_appear() -> None:
    raw_turns = (
        RawTurn(label="Sarah", text="Hello?"),
        RawTurn(label="Leon", text="Hi."),
        RawTurn(label="Priya", text="Also here."),
    )

    resolution = resolve_speaker_roles("Sarah", raw_turns)

    assert not resolution.is_resolved
    assert "found 3" in (resolution.unresolved_reason or "")


def test_unresolved_when_the_agent_name_matches_neither_label() -> None:
    """Never guessed: if the header's agent name isn't one of the two
    labels, nothing is assigned — not even a fallback to "whoever spoke
    first".
    """
    raw_turns = (
        RawTurn(label="Tony", text="Go ahead."),
        RawTurn(label="Ewan", text="Question about my glasses."),
    )

    resolution = resolve_speaker_roles("Sarah", raw_turns)

    assert not resolution.is_resolved
    assert "Sarah" in (resolution.unresolved_reason or "")
    assert "matches none" in (resolution.unresolved_reason or "")


def test_preserves_turn_order() -> None:
    raw_turns = (
        RawTurn(label="Sarah", text="one"),
        RawTurn(label="Leon", text="two"),
        RawTurn(label="Sarah", text="three"),
        RawTurn(label="Leon", text="four"),
    )

    resolution = resolve_speaker_roles("Sarah", raw_turns)

    assert resolution.turns is not None
    assert [t.text for t in resolution.turns] == ["one", "two", "three", "four"]
