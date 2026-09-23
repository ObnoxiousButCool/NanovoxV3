"""L1's deterministic pass: the two pattern-matchable control exceptions,
and candidate broker mentions.

Built against real snippets from the corpus (quoted in each test), not
invented text: the greeting-pattern heuristic is only worth as much as
what it actually finds in the 100 real calls.
"""

from __future__ import annotations

from domain.entities.broker import Broker
from domain.entities.transcript import Transcript
from domain.entities.turn import Turn
from domain.extraction.l1_deterministic import (
    detect_broker_mentions,
    detect_control_exceptions,
    run_l1,
)
from domain.value_objects.call_source import CallSource
from domain.value_objects.caller_type import CallerType
from domain.value_objects.control_exception_type import ControlExceptionType
from domain.value_objects.speaker_role import SpeakerRole

NO_RECORDING = ControlExceptionType.NO_RECORDING_DISCLOSURE
NO_VERIFICATION = ControlExceptionType.DISCLOSURE_BEFORE_VERIFICATION

_KAREN_LINDQVIST = Broker(
    reference="BRK-05",
    name="Karen Lindqvist",
    agency="Lindqvist Group",
    region="Bay Area",
    groups_in_book=9,
    signal_profile="Watch",
)
_MARCUS_TRENT = Broker(
    reference="BRK-02",
    name="Marcus Trent",
    agency="Trent Benefits",
    region="Orange County",
    groups_in_book=6,
    signal_profile="Stable",
)


def _transcript(*turns: Turn, caller_ref: str = "CB-7700205") -> Transcript:
    return Transcript(
        reference="C-TEST",
        source=CallSource.CORPUS_PDF,
        occurred_at=None,
        aht_seconds=None,
        caller_type=CallerType.MEMBER,
        caller_ref=caller_ref,
        agent_ref="AGT-01",
        agent_name="Sarah Whitlock",
        turns=turns,
    )


class TestRecordingDisclosure:
    def test_c0001s_greeting_discloses_recording_and_asks_for_identity(self) -> None:
        # "Choice Administrators, Sarah speaking. This call may be recorded
        # for quality and training. Can I take your name and member ID?"
        transcript = _transcript(
            Turn(
                role=SpeakerRole.AGENT,
                text=(
                    "Choice Administrators, Sarah speaking. This call may be "
                    "recorded for quality and training. Can I take your name "
                    "and member ID?"
                ),
            ),
            Turn(role=SpeakerRole.CALLER, text="Leon Castellano. CB-7700205."),
        )

        assert detect_control_exceptions(transcript) == frozenset()

    def test_c0002s_greeting_has_neither_disclosure_nor_verification(self) -> None:
        # "Choice Administrators, Brad." — the whole greeting.
        transcript = _transcript(
            Turn(role=SpeakerRole.AGENT, text="Choice Administrators, Brad."),
            Turn(
                role=SpeakerRole.CALLER,
                text="Vidal Castellano, member ID CB-7700170. I'm after my dental card.",
            ),
        )

        assert detect_control_exceptions(transcript) == frozenset({NO_RECORDING, NO_VERIFICATION})

    def test_c0007s_greeting_discloses_recording_but_never_asks_for_identity(self) -> None:
        # "Choice Administrators, Tiffany speaking, this call may be
        # recorded for quality and training. How can I help?" — no name or
        # member ID request anywhere in the greeting.
        transcript = _transcript(
            Turn(
                role=SpeakerRole.AGENT,
                text=(
                    "Choice Administrators, Tiffany speaking, this call may be "
                    "recorded for quality and training. How can I help?"
                ),
            ),
            Turn(role=SpeakerRole.CALLER, text="Hi, I'm ringing about a claim for Jonah Nkemdi."),
        )

        assert detect_control_exceptions(transcript) == frozenset({NO_VERIFICATION})

    def test_a_group_number_request_also_counts_as_verification(self) -> None:
        transcript = _transcript(
            Turn(
                role=SpeakerRole.AGENT,
                text=(
                    "Thank you for calling Choice Administrators, this is Adaeze. "
                    "This call may be recorded for quality and training. Can I "
                    "take your name and group number?"
                ),
            ),
            Turn(role=SpeakerRole.CALLER, text="Sandra Villalobos, CON-137."),
        )

        assert detect_control_exceptions(transcript) == frozenset()

    def test_no_agent_turn_at_all_raises_no_exception_and_flags_nothing(self) -> None:
        # Defensive: Phase 2 already withholds a transcript with no
        # resolved agent turns (SPEAKER_UNRESOLVED), so this should be
        # unreachable — but must degrade safely rather than raise.
        transcript = _transcript(Turn(role=SpeakerRole.CALLER, text="Hello?"))

        assert detect_control_exceptions(transcript) == frozenset()


class TestBrokerMentions:
    def test_a_broker_named_by_surname_is_spotted(self) -> None:
        # C-0008: "By email to Marcus Trent, our broker. He told us at
        # renewal that was fine."
        transcript = _transcript(
            Turn(role=SpeakerRole.CALLER, text="Quentin Thibault, CON-101."),
            Turn(
                role=SpeakerRole.CALLER,
                text="By email to Marcus Trent, our broker. He told us at renewal that was fine.",
            ),
        )

        mentions = detect_broker_mentions(transcript, (_MARCUS_TRENT,))

        assert len(mentions) == 1
        assert mentions[0].broker_ref == "BRK-02"
        assert mentions[0].turn_seq == 1

    def test_the_callers_own_self_identification_is_never_read_as_a_mention(self) -> None:
        # C-0045: the caller Denise Lindqvist shares a surname with broker
        # BRK-05 Karen Lindqvist — a real coincidence in this corpus. The
        # caller's opening self-ID line must not be scanned.
        transcript = _transcript(
            Turn(role=SpeakerRole.CALLER, text="Denise Lindqvist, CB-7700249."),
            Turn(role=SpeakerRole.CALLER, text="I have a question about my crown."),
        )

        assert detect_broker_mentions(transcript, (_KAREN_LINDQVIST,)) == ()

    def test_a_surname_mentioned_only_in_the_self_id_turn_is_still_excluded(self) -> None:
        transcript = _transcript(
            Turn(role=SpeakerRole.CALLER, text="Denise Lindqvist, CB-7700249."),
        )

        assert detect_broker_mentions(transcript, (_KAREN_LINDQVIST,)) == ()

    def test_an_unmentioned_broker_produces_no_mention(self) -> None:
        transcript = _transcript(
            Turn(role=SpeakerRole.CALLER, text="Self ID line."),
            Turn(role=SpeakerRole.CALLER, text="Nothing about a broker here."),
        )

        assert detect_broker_mentions(transcript, (_MARCUS_TRENT, _KAREN_LINDQVIST)) == ()

    def test_agent_turns_are_never_scanned_for_broker_mentions(self) -> None:
        transcript = _transcript(
            Turn(role=SpeakerRole.CALLER, text="Self ID line."),
            Turn(role=SpeakerRole.AGENT, text="I see Marcus Trent is your broker of record."),
        )

        assert detect_broker_mentions(transcript, (_MARCUS_TRENT,)) == ()


class TestRunL1:
    def test_caller_ref_is_carried_over_unchanged(self) -> None:
        transcript = _transcript(
            Turn(role=SpeakerRole.AGENT, text="Choice Administrators, Sarah speaking."),
            caller_ref="CB-7700205",
        )

        result = run_l1(transcript, known_brokers=())

        assert result.caller_ref == "CB-7700205"

    def test_the_whole_result_combines_both_checks(self) -> None:
        transcript = _transcript(
            Turn(role=SpeakerRole.AGENT, text="Choice Administrators, Brad."),
            Turn(role=SpeakerRole.CALLER, text="Self ID."),
            Turn(role=SpeakerRole.CALLER, text="Marcus Trent handles our account."),
        )

        result = run_l1(transcript, known_brokers=(_MARCUS_TRENT,))

        assert result.control_exceptions == frozenset({NO_RECORDING, NO_VERIFICATION})
        assert len(result.broker_mentions) == 1
