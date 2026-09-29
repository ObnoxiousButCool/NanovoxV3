"""One call, with the turns behind it — the evidence a figure opens onto.

**This is the only read path in the application that serves transcript
text.** `plan.md` §6.3 calls label stripping "the single most important
safety property", and until now that property was enforced at ingestion:
the corpus PDF carries a CALL TAGS block under each transcript, and
ingestion drops it so the extraction model cannot read the answer it is
being asked to produce.

Ingestion being correct is necessary and not sufficient. The stored turns
are what this endpoint returns, so the leak test runs against **this
response**, not only against the ingest step — a stripping bug, a
re-ingest from a different source, or a fixture loaded straight into the
database would all pass an ingestion-only check and still put the answer
key on screen.

## What is deliberately not here

**No filters.** Evidence is a single call by reference. A filtered
evidence view would mean a reader could open a call from one screen and
see different turns than from another, which is the opposite of evidence.

**No search over turn text.** `ListCalls.haystack` explains why the
workbench does not search transcripts; the same reasoning applies to
anything that would let a phrase be located across member conversations
without opening a call.

## The tags are a second, independent lookup

The identity and transcript above come from `CallRepository`, the only
read path this module's docstring already governs. The signals, knowledge
failure, process gap and control exceptions below come from a second,
unrelated source — `InsightsReader`, the same one every figure on the
dashboard reads — asked for the whole corpus with no filters, so a call's
evidence cannot disagree with itself depending on who is looking. Neither
lookup touches the other: this one never reaches the transcript, so it
carries none of the leak surface the module docstring is about.

A call can exist in `CallRepository` (it was ingested) without yet having
tags (extraction has not run, or has not reached this call). That is not
an error — the tags below are simply absent, the same "not run yet" this
application already represents elsewhere as `None` rather than a zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from application.use_cases.read_insights import InsightsRequest
from domain.aggregation.filters import InsightFilters
from domain.errors import NotFoundError
from domain.value_objects.signal_type import owner_team_of, severity_of

if TYPE_CHECKING:
    from application.ports.call_repository import CallRepository
    from application.use_cases.read_insights import InsightsReader
    from domain.aggregation.call_tags import CallTags
    from domain.value_objects.control_exception_type import ControlExceptionType
    from domain.value_objects.knowledge_failure import KnowledgeFailure
    from domain.value_objects.process_gap import ProcessGap
    from domain.value_objects.signal_severity import SignalSeverity
    from domain.value_objects.signal_type import SignalType


@dataclass(frozen=True)
class Turn:
    """One line of the conversation."""

    sequence: int
    role: str
    text: str


@dataclass(frozen=True)
class SignalRaised:
    """One signal, with the severity and owner the taxonomy fixes per type.

    Not per-call data: `severity_of` and `owner_team_of` read the Signal
    Taxonomy sheet's own mapping, the same one `labels.py`'s severity
    labels already carry. A call only decides *which* signals fired.
    """

    signal_type: SignalType
    severity: SignalSeverity
    owner_team: str


@dataclass(frozen=True)
class CallEvidence:
    """A call's own record, and its turns if it has any."""

    reference: str
    caller_type: str
    caller_ref: str
    agent_ref: str
    employer_ref: str | None
    resolution_status: str
    resolution_reason: str | None
    turns: tuple[Turn, ...]
    #: True when the call has no turns to show.
    #:
    #: Read off the turns rather than off `transcript`: the repository
    #: reconstructs a `Transcript` whenever the row carries a source, so a
    #: call stored without turns still has one — an object with nothing in
    #: it. What a reader needs to know is whether there is anything to
    #: read, and a drawer rendering nothing with no explanation reads as a
    #: loading failure rather than as a call stored without a transcript.
    transcript_missing: bool
    #: Empty when the call has no tags yet (extraction has not reached it),
    #: never a stand-in for "no signals fired".
    signals: tuple[SignalRaised, ...] = ()
    knowledge_failure: KnowledgeFailure | None = None
    process_gap: ProcessGap | None = None
    control_exceptions: tuple[ControlExceptionType, ...] = ()

    @property
    def text(self) -> str:
        """Every turn's text, for the leak assertion to run over."""
        return "\n".join(turn.text for turn in self.turns)


class ReadCallEvidence:
    """One call by reference, or a 404 that names it."""

    def __init__(self, calls: CallRepository, reader: InsightsReader) -> None:
        self._calls = calls
        self._reader = reader

    async def execute(self, reference: str) -> CallEvidence:
        call = await self._calls.get(reference)
        if call is None:
            # Named, because a reader who followed a `callIds` link to a
            # call that is not there needs to be able to say which one when
            # they report it.
            raise NotFoundError(
                "No such call in this corpus.",
                detail=f"reference={reference}",
            )
        transcript = call.transcript
        turns = (
            tuple(
                Turn(sequence=index, role=turn.role.value, text=turn.text)
                for index, turn in enumerate(transcript.turns)
            )
            if transcript is not None
            else ()
        )
        tags = await self._tags_for(reference)
        knowledge_failure = (
            tags.knowledge_failure
            if tags is not None
            and tags.knowledge_failure is not None
            and tags.knowledge_failure.present
            else None
        )
        process_gap = (
            tags.process_gap
            if tags is not None and tags.process_gap is not None and tags.process_gap.present
            else None
        )
        return CallEvidence(
            reference=call.reference,
            caller_type=call.caller_type.value,
            caller_ref=call.caller_ref,
            agent_ref=call.agent_ref,
            employer_ref=call.employer_ref,
            resolution_status=call.resolution_status.value,
            resolution_reason=call.resolution_reason,
            turns=turns,
            transcript_missing=not turns,
            signals=tuple(
                _signal_raised(signal) for signal in sorted(tags.signals, key=lambda s: s.value)
            )
            if tags is not None
            else (),
            knowledge_failure=knowledge_failure,
            process_gap=process_gap,
            control_exceptions=tuple(sorted(tags.control_exceptions, key=lambda item: item.value))
            if tags is not None
            else (),
        )

    async def _tags_for(self, reference: str) -> CallTags | None:
        """This call's tags, or `None` if extraction has not reached it.

        Unfiltered on purpose (`InsightFilters()` narrows nothing): evidence
        is a single call by reference, and a period or region filter has no
        business deciding whether this lookup can find it.
        """
        scope = await self._reader.scope(InsightsRequest(filters=InsightFilters()))
        call = next((item for item in scope.filtered.calls if item.reference == reference), None)
        return call.tags if call is not None else None


def _signal_raised(signal: SignalType) -> SignalRaised:
    return SignalRaised(
        signal_type=signal, severity=severity_of(signal), owner_team=owner_team_of(signal)
    )
