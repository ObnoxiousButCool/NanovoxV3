"""Quote-must-be-in-transcript validation, shared by every LLM layer.

"Every quote must appear in the transcript after normalisation, or the
item is rejected with a recorded note" (plan §7). A model that keeps
inventing quotes is a finding about the model, not something to hide by
discarding the rejection silently — so this returns what survived *and*
what was refused and why, for every layer that cites evidence: L2's
intent statements, L3's rubric markers, L4's signals.

Normalisation is deliberately light: casefold and collapse whitespace.
Anything more — dropping punctuation, stemming — would let a quote "prove"
something adjacent to what was actually said.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from domain.entities.transcript import Transcript

_WHITESPACE = re.compile(r"\s+")


def _normalise(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip().casefold()


class CitesEvidence(Protocol):
    """What every evidence-citing item — an intent statement, a rubric
    marker, a signal — has in common: a quote and the turn it claims to
    come from.
    """

    @property
    def quote(self) -> str: ...

    @property
    def turn_seq(self) -> int: ...


class EvidenceRejection(StrEnum):
    """Why a piece of cited evidence was refused."""

    MISSING_TURN = "missing_turn"
    QUOTE_NOT_IN_TURN = "quote_not_in_turn"
    EMPTY_QUOTE = "empty_quote"
    #: The Call Quality Framework's third named refusal: "the dimension is
    #: not in the rubric". A marker-level refusal, not a failed call — the
    #: sheet's own example refuses one marker for zero points and scores the
    #: rest. Before this existed the rubric raised NotFoundError on an
    #: unknown code, so one hallucinated dimension name failed the whole L3
    #: pass for that call.
    UNKNOWN_DIMENSION = "unknown_dimension"


@dataclass(frozen=True)
class RejectedEvidence[T: CitesEvidence]:
    """A cited item that was refused, and why."""

    item: T
    reason: EvidenceRejection

    @property
    def explanation(self) -> str:
        if self.reason is EvidenceRejection.UNKNOWN_DIMENSION:
            return "Cites a dimension the rubric does not define."
        if self.reason is EvidenceRejection.EMPTY_QUOTE:
            return "Cited no quote."
        if self.reason is EvidenceRejection.MISSING_TURN:
            return f"Cites turn {self.item.turn_seq}, which does not exist."
        return f"Quoted text does not appear in turn {self.item.turn_seq}: {self.item.quote!r}"


@dataclass(frozen=True)
class EvidenceValidation[T: CitesEvidence]:
    """The outcome of validating a batch of cited items."""

    accepted: tuple[T, ...]
    rejected: tuple[RejectedEvidence[T], ...]

    @property
    def has_rejections(self) -> bool:
        return bool(self.rejected)

    @property
    def all_rejected(self) -> bool:
        """The model cited evidence and none of it survived checking.

        Distinct from citing nothing: a call with nothing to report on
        this dimension is a quiet call, while one where every citation
        failed checking is a call nobody has actually evidenced — usually
        the sign of a transcript that failed to parse into turns.
        """
        return bool(self.rejected) and not self.accepted


def _reject_reason(item: CitesEvidence, transcript: Transcript) -> EvidenceRejection | None:
    if not item.quote.strip():
        return EvidenceRejection.EMPTY_QUOTE

    if not 0 <= item.turn_seq < len(transcript.turns):
        return EvidenceRejection.MISSING_TURN

    turn_text = _normalise(transcript.turns[item.turn_seq].text)
    if _normalise(item.quote) not in turn_text:
        return EvidenceRejection.QUOTE_NOT_IN_TURN

    return None


def validate_evidence[T: CitesEvidence](
    items: Iterable[T], transcript: Transcript
) -> EvidenceValidation[T]:
    """Keep only the cited items whose quote genuinely appears in the transcript."""
    accepted: list[T] = []
    rejected: list[RejectedEvidence[T]] = []

    for item in items:
        reason = _reject_reason(item, transcript)
        if reason is None:
            accepted.append(item)
        else:
            rejected.append(RejectedEvidence(item=item, reason=reason))

    return EvidenceValidation(accepted=tuple(accepted), rejected=tuple(rejected))


def also_rejected[T: CitesEvidence](
    validation: EvidenceValidation[T],
    items: Sequence[T],
    reason: EvidenceRejection,
) -> EvidenceValidation[T]:
    """Fold in items refused before the transcript was ever consulted.

    L3 filters markers whose dimension is not in the rubric before checking
    quotes, because there is no point asking whether a quote supports a
    dimension that does not exist. Those refusals still belong in the same
    `EvidenceValidation` — `all_rejected` has to see them, or a call whose
    every marker named an invented dimension would look like a call that
    cited nothing, and the Call Quality Framework treats those two very
    differently.
    """
    if not items:
        return validation
    return EvidenceValidation(
        accepted=validation.accepted,
        rejected=validation.rejected
        + tuple(RejectedEvidence(item=item, reason=reason) for item in items),
    )
