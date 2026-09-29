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

## The analysis beside the transcript

The call's own pipeline output travels with it, grouped the way plan §7
groups it: L1, L2, L3, L4, and then the values computed in code after the
layers have run. **Five panels, four layers.** The Call Tag Schema's
"Emitted by" column names four and nothing beyond L4 exists in the
workbook (`domain/layers.py` is the source of truth and deliberately has
four members). The fifth panel is not a fifth layer and is not labelled as
one: it holds what §7 lists under "Deterministic, not LLM" — values no
model ever saw, derived from the layers' output.

Every panel carries whether its layer **ran**, separately from what it
found. L3 and L4 are not pipeline-critical: either can fail on a single
call and be recorded unavailable while the rest of the analysis stands. A
panel that rendered "no signals" for a layer that never ran would be
reporting a clean call, which is the same "withheld is not zero" mistake
the figures make impossible everywhere else on the product.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from domain.errors import NotFoundError

if TYPE_CHECKING:
    from application.ports.call_extraction_repository import CallExtractionRepository
    from application.ports.call_repository import CallRepository
    from domain.entities.call_extraction import CallExtraction


@dataclass(frozen=True)
class Turn:
    """One line of the conversation."""

    sequence: int
    role: str
    text: str


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
    #: The pipeline's output for this call, or `None` when nothing has run
    #: on it at all. Not flattened into this dataclass: the grouping by
    #: layer is the point, and `CallExtraction` already carries it.
    analysis: CallExtraction | None = None

    @property
    def text(self) -> str:
        """Every turn's text, for the leak assertion to run over."""
        return "\n".join(turn.text for turn in self.turns)


class ReadCallEvidence:
    """One call by reference, or a 404 that names it."""

    def __init__(self, calls: CallRepository, extractions: CallExtractionRepository) -> None:
        self._calls = calls
        self._extractions = extractions

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
        extraction = await self._extractions.get(reference)
        transcript = call.transcript
        turns = (
            tuple(
                Turn(sequence=index, role=turn.role.value, text=turn.text)
                for index, turn in enumerate(transcript.turns)
            )
            if transcript is not None
            else ()
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
            analysis=extraction,
        )
