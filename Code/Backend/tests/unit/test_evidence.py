"""Quote-must-be-in-transcript validation, shared by every LLM layer."""

from __future__ import annotations

from dataclasses import dataclass

from domain.entities.transcript import Transcript
from domain.entities.turn import Turn
from domain.extraction.evidence import EvidenceRejection, validate_evidence
from domain.value_objects.call_source import CallSource
from domain.value_objects.caller_type import CallerType
from domain.value_objects.speaker_role import SpeakerRole


@dataclass(frozen=True)
class _Cited:
    """A minimal stand-in for any evidence-citing item (marker, signal, intent)."""

    label: str
    quote: str
    turn_seq: int


def _transcript(*texts: str) -> Transcript:
    return Transcript(
        reference="C-TEST",
        source=CallSource.CORPUS_PDF,
        occurred_at=None,
        aht_seconds=None,
        caller_type=CallerType.MEMBER,
        caller_ref="CB-7700205",
        agent_ref="AGT-01",
        agent_name="Sarah Whitlock",
        turns=tuple(Turn(role=SpeakerRole.CALLER, text=text) for text in texts),
    )


def test_a_quote_genuinely_in_its_cited_turn_is_accepted() -> None:
    transcript = _transcript("I had a crown done three weeks ago.")
    item = _Cited("a", quote="crown done three weeks ago", turn_seq=0)

    result = validate_evidence([item], transcript)

    assert result.accepted == (item,)
    assert not result.has_rejections


def test_a_quote_not_in_the_cited_turn_is_rejected() -> None:
    transcript = _transcript("I had a crown done three weeks ago.")
    item = _Cited("a", quote="something never said", turn_seq=0)

    result = validate_evidence([item], transcript)

    assert result.accepted == ()
    assert result.rejected[0].reason is EvidenceRejection.QUOTE_NOT_IN_TURN


def test_a_turn_index_out_of_range_is_rejected_as_missing() -> None:
    transcript = _transcript("Only one turn.")
    item = _Cited("a", quote="Only one turn.", turn_seq=5)

    result = validate_evidence([item], transcript)

    assert result.rejected[0].reason is EvidenceRejection.MISSING_TURN


def test_a_negative_turn_index_is_rejected_as_missing() -> None:
    transcript = _transcript("Only one turn.")
    item = _Cited("a", quote="Only one turn.", turn_seq=-1)

    result = validate_evidence([item], transcript)

    assert result.rejected[0].reason is EvidenceRejection.MISSING_TURN


def test_an_empty_quote_is_rejected_without_touching_the_transcript() -> None:
    transcript = _transcript("Some text.")
    item = _Cited("a", quote="   ", turn_seq=0)

    result = validate_evidence([item], transcript)

    assert result.rejected[0].reason is EvidenceRejection.EMPTY_QUOTE


def test_matching_is_case_and_whitespace_insensitive() -> None:
    transcript = _transcript("I had a  CROWN   done.")
    item = _Cited("a", quote="crown done", turn_seq=0)

    result = validate_evidence([item], transcript)

    assert result.accepted == (item,)


def test_accepted_and_rejected_items_are_both_reported() -> None:
    transcript = _transcript("The claim was denied.", "I paid since March.")
    good = _Cited("good", quote="claim was denied", turn_seq=0)
    bad = _Cited("bad", quote="never happened", turn_seq=1)

    result = validate_evidence([good, bad], transcript)

    assert result.accepted == (good,)
    assert [r.item for r in result.rejected] == [bad]


def test_all_rejected_is_true_only_when_something_was_cited_and_none_survived() -> None:
    transcript = _transcript("Some text.")
    item = _Cited("a", quote="not present", turn_seq=0)

    result = validate_evidence([item], transcript)

    assert result.all_rejected


def test_all_rejected_is_false_when_nothing_was_cited_at_all() -> None:
    # A quiet call — nothing to report — is not the same event as a call
    # where every citation failed checking.
    no_items: list[_Cited] = []
    result = validate_evidence(no_items, _transcript("Some text."))

    assert not result.all_rejected
    assert not result.has_rejections


def test_the_explanation_names_the_quote_and_turn() -> None:
    transcript = _transcript("Some text.")
    item = _Cited("a", quote="not present", turn_seq=0)

    result = validate_evidence([item], transcript)

    assert "turn 0" in result.rejected[0].explanation
    assert "not present" in result.rejected[0].explanation
