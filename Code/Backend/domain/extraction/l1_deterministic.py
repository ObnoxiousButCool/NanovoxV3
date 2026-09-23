"""L1 — deterministic extraction (plan §7: "no model judgement needed").

Produces `caller_ref` (already resolved by Phase 2's ingestion — carried
over, not re-derived), the detectable half of `control_exceptions`
(field 7), and candidate `broker_named_aloud` mentions (field 14) before
L2 validates a candidate against the employer's actual broker of record.

**What is genuinely deterministic here, and what isn't.** The Call Tag
Schema calls this "a greeting check" — a pattern match on the opening
turns, not a semantic read of the call. That is true of two of the three
control exceptions:

* `no_recording_disclosure` — did the agent's greeting say the call may be
  recorded?
* `disclosure_before_verification` — did the agent's greeting ask for the
  caller's identity at all? A greeting with no verification request means
  nothing that follows was gated behind one.

`missing_benefit_disclosure` needs to know which benefit was under
discussion and whether the relevant disclosure was owed — a judgement,
not a pattern — so L1 does not attempt it; it is L3's alone.

**How well this heuristic actually matches the workbook's own CALL TAGS
is exactly what Phase 5's evaluation harness measures** (plan §8 Phase 5,
per-field agreement against `ground_truth`). The scope of this module is
a principled, testable, deterministic pass — not a claim of accuracy
Phase 5 hasn't checked yet.

Broker mentions: a known broker's surname spoken by the caller is a
candidate. `sentiment` (ADVERSE / POSITIVE) and validation against the
employer's own broker of record are both judgement calls the schema
assigns to L2 (Emitted by: L1/L2) — L1 only spots the name.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from domain.entities.broker import Broker
from domain.entities.transcript import Transcript
from domain.value_objects.control_exception_type import ControlExceptionType
from domain.value_objects.speaker_role import SpeakerRole

# Every recording-disclosure sentence in the corpus reads "...may be
# recorded for quality and training..."; matched loosely enough to survive
# minor phrasing drift without turning into a semantic classifier.
_RECORDING_DISCLOSURE = re.compile(
    r"record(?:ed|ing)?\b[^.]{0,60}(?:quality|training)", re.IGNORECASE
)

# The identity check that precedes disclosure in every compliant greeting
# observed: some variant of "name and member ID" / "name and group number".
_VERIFICATION_REQUEST = re.compile(
    r"(?:name\s+and\s+(?:member\s*id|group\s*(?:number|#))"
    r"|can\s+i\s+(?:take|get|have)\s+your\s+name)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class BrokerMention:
    """A known broker's name spotted in the caller's own words.

    Not yet validated against the employer's broker of record, and
    carries no sentiment — both are L2's job (§7).
    """

    broker_ref: str
    quote: str
    turn_seq: int


@dataclass(frozen=True)
class L1Result:
    """What L1 can establish without a model."""

    caller_ref: str
    control_exceptions: frozenset[ControlExceptionType]
    broker_mentions: tuple[BrokerMention, ...]


def _greeting(transcript: Transcript) -> str | None:
    """The agent's first turn, where the workbook says these checks belong."""
    for turn in transcript.turns:
        if turn.role is SpeakerRole.AGENT:
            return turn.text
    return None


def detect_control_exceptions(transcript: Transcript) -> frozenset[ControlExceptionType]:
    """The two control exceptions a greeting alone can prove."""
    greeting = _greeting(transcript)
    if greeting is None:
        # No agent turn at all is not this function's problem to solve —
        # Phase 2 already marks such a call SPEAKER_UNRESOLVED and withholds
        # its transcript entirely, so this branch is unreachable in practice
        # but must not raise if it somehow is.
        return frozenset()

    exceptions: set[ControlExceptionType] = set()
    if not _RECORDING_DISCLOSURE.search(greeting):
        exceptions.add(ControlExceptionType.NO_RECORDING_DISCLOSURE)
    if not _VERIFICATION_REQUEST.search(greeting):
        exceptions.add(ControlExceptionType.DISCLOSURE_BEFORE_VERIFICATION)
    return frozenset(exceptions)


def detect_broker_mentions(
    transcript: Transcript, known_brokers: tuple[Broker, ...]
) -> tuple[BrokerMention, ...]:
    """Every known broker whose surname the caller spoke, in turn order.

    Matched on the surname alone: callers use a broker's first name rarely
    and their agency name almost never, but the surname survives — "Anthony
    Salerno" becomes "Salerno told us...".

    The caller's own first turn is excluded: in this corpus it is almost
    always self-identification ("Leon Castellano. CB-7700205."), and a
    caller sharing a surname with a broker in the reference data — real in
    this corpus, C-0045's caller Denise Lindqvist against broker BRK-05
    Karen Lindqvist — would otherwise read as the caller naming their
    broker.
    """
    mentions: list[BrokerMention] = []
    caller_turns = tuple(turn for turn in transcript.turns if turn.role is SpeakerRole.CALLER)
    for turn in caller_turns[1:]:
        for broker in known_brokers:
            surname = broker.name.rsplit(" ", 1)[-1]
            if not surname:
                continue
            if re.search(rf"\b{re.escape(surname)}\b", turn.text, re.IGNORECASE):
                mentions.append(
                    BrokerMention(
                        broker_ref=broker.reference,
                        quote=turn.text,
                        turn_seq=_seq_of(transcript, turn),
                    )
                )
    return tuple(mentions)


def _seq_of(transcript: Transcript, target: object) -> int:
    for index, turn in enumerate(transcript.turns):
        if turn is target:
            return index
    raise ValueError("turn is not part of this transcript")  # pragma: no cover - defensive


def run_l1(transcript: Transcript, known_brokers: tuple[Broker, ...]) -> L1Result:
    """L1's whole output for one call."""
    return L1Result(
        caller_ref=transcript.caller_ref,
        control_exceptions=detect_control_exceptions(transcript),
        broker_mentions=detect_broker_mentions(transcript, known_brokers),
    )
