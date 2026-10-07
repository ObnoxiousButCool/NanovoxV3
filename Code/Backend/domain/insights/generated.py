"""What a generated insight is, and what it is when there isn't one.

## Two kinds, and they go on the wire

**C3a is decided** (D14, 2026-09-25, Minnie): a recommendation is labelled
*in the response*, not only on screen. So `InsightKind` is a field, not a
CSS class. The reason is quotable-out-of-context: a suggested action that
travels into a report without its screen must still say it was suggested,
or it reads as something the corpus measured.

`Documents/notes/Revised-Implementation-Plan.md` §9 Phase 5 says this phase "needs no enum
from the backend, unless C3a closes the other way". It closed the other
way.

Note what is *not* here: OBSERVED. D13 gives `basis` three values and they
describe where a **figure** came from. A generated sentence is never one of
them, and the honesty contract (checkpoint I4) is that generated text is
labelled INFERENCE or RECOMMENDATION and never OBSERVED. Keeping the two
enums apart in the code is what stops that being a matter of care.

## Severity orders sentences; it never grades an account

`Severity` ranks which generated sentence a reader should read first. It is
**not** a risk level, and D12 is the reason to say so out loud: "flagged"
means metric 10 and nothing else, and indicator families render as a count
precisely so that a second grading vocabulary does not grow beside the
first. A HIGH insight is a sentence worth reading first. It is not an
account in a band, and nothing downstream may treat it as one.

## Unavailable is a state, not an empty list

**U2 is decided** (D14, 2026-09-25, Minnie): when the provider is
unavailable the surface shows an explicit "unavailable" state, like the
withheld panels — *"not templated copy standing in for generated text, and
not a silently hidden panel."*

That overrides the Phase 5 text written the day before, which specified a
templated fallback. The decision is later, and it is the client's. So there
is no fallback copy in this module: a screen with no model gets a
`GeneratedInsights` whose `status` says why, which is the same shape as a
withheld figure and reads the same way — we could not say, and here is the
reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from domain.errors import ValidationError


class InsightKind(StrEnum):
    """What a sentence is doing. Never OBSERVED — see the module docstring."""

    #: Reads the figures and says what they appear to mean.
    INFERENCE = "INFERENCE"
    #: Proposes an action. Must not be readable as a measurement (C3a).
    RECOMMENDATION = "RECOMMENDATION"


class Severity(StrEnum):
    """Reading order for generated prose. Never a risk band — see D12.

    The values say reading order rather than HIGH/MEDIUM/LOW for two
    reasons, and both are load-bearing. A `HIGH` beside a figure invites
    exactly the second grading vocabulary D12 removed. And `SignalSeverity`
    already has a `HIGH`: both are `str` enums, so the two members compare
    and hash equal, and a shared label map would silently take one label for
    the other. That is a real defect in `labels.py` and is worth fixing on
    its own; these values are chosen so as not to depend on it.
    """

    READ_FIRST = "READ_FIRST"
    WORTH_READING = "WORTH_READING"
    BACKGROUND = "BACKGROUND"


class Lens(StrEnum):
    """The four readings the exec page groups insights under.

    **U1 (D14, 2026-09-25, Minnie): a client requirement.** Not a
    presentational choice, so these four and no others, in this order, with
    the prototype's own wording. Reorganising them is a conversation with
    the client, not a design decision.

    A lens is a property of a *sentence*, not of a figure. `exec.html` makes
    that plain — the grid carries an "AI insights" badge, three insights per
    lens, each written from the figures on the page and adding no number of
    its own — so the lens lives here beside the sentence rather than on the
    exec response.
    """

    EMPLOYERS = "EMPLOYERS"
    CHURN_AND_RETENTION = "CHURN_AND_RETENTION"
    PRODUCT_AND_SERVICE = "PRODUCT_AND_SERVICE"
    PAYER_AND_CARRIER = "PAYER_AND_CARRIER"


class InsightsStatus(StrEnum):
    GENERATED = "GENERATED"
    UNAVAILABLE = "UNAVAILABLE"


class UnavailableReason(StrEnum):
    """Why there is no generated text, in the reader's terms.

    Each value is a different thing to do about it, which is the test for
    whether a reason earns its place: a missing provider is configuration, a
    failed call is operations, and a rejected answer is a prompt problem
    that must never be quietly retried into acceptance.
    """

    #: No provider is configured for this deployment.
    NO_PROVIDER = "NO_PROVIDER"
    #: A provider is configured and the call did not succeed.
    PROVIDER_FAILED = "PROVIDER_FAILED"
    #: The model answered and the answer stated a number no fact supports.
    GUARDRAIL_REJECTED = "GUARDRAIL_REJECTED"
    #: Every figure on the screen is withheld, so there is nothing to read.
    NO_PUBLISHED_FACTS = "NO_PUBLISHED_FACTS"
    #: The account had too few calls to be assessed at all. Distinct from
    #: the above: its counts are published and perfectly true, but a
    #: handful of calls cannot support a reading, and asking anyway would
    #: bill for a sentence that restates a tile.
    NOT_ASSESSABLE = "NOT_ASSESSABLE"


@dataclass(frozen=True)
class Insight:
    """One generated sentence, with what it rests on."""

    key: str
    #: One sentence. Length is enforced where it is parsed, not here.
    sentence: str
    kind: InsightKind
    severity: Severity
    #: Which of the four readings this sentence belongs under (U1).
    lens: Lens
    #: The figures it read, by `Fact.key`. Never empty: a sentence about
    #: nothing on the screen is a sentence about something else.
    fact_keys: tuple[str, ...]
    #: The playbook key its "What to do" link points at, when one applies.
    #: Validated against the catalogue by the use case, not here.
    issue_key: str | None = None

    def __post_init__(self) -> None:
        if not self.sentence.strip():
            raise ValidationError(f"Insight {self.key!r} has no sentence.")
        if not self.fact_keys:
            raise ValidationError(
                f"Insight {self.key!r} cites no figure. An insight that reads nothing "
                "on the screen cannot be checked against it."
            )


@dataclass(frozen=True)
class GeneratedInsights:
    """The insight surface for one screen, generated or explicitly not.

    Constructed through the two classmethods rather than directly, so a
    populated UNAVAILABLE — the shape that would let a screen show
    sentences while claiming it had none — cannot be built at all.
    """

    status: InsightsStatus
    insights: tuple[Insight, ...] = ()
    reason: UnavailableReason | None = None
    #: The provider and model that wrote these, for provenance on screen.
    provider: str | None = None
    model: str | None = None

    def __post_init__(self) -> None:
        if self.status is InsightsStatus.GENERATED:
            if not self.insights:
                raise ValidationError(
                    "GENERATED with no insights is an unavailable surface wearing the "
                    "wrong status. Use `unavailable()`."
                )
            if self.reason is not None:
                raise ValidationError("A generated surface has no unavailable reason.")
        else:
            if self.insights:
                raise ValidationError("An unavailable surface carries no insights.")
            if self.reason is None:
                raise ValidationError("An unavailable surface must say why.")

    @classmethod
    def generated(
        cls, insights: tuple[Insight, ...], *, provider: str, model: str
    ) -> GeneratedInsights:
        return cls(
            status=InsightsStatus.GENERATED,
            insights=insights,
            provider=provider,
            model=model,
        )

    @classmethod
    def unavailable(cls, reason: UnavailableReason) -> GeneratedInsights:
        return cls(status=InsightsStatus.UNAVAILABLE, reason=reason)
