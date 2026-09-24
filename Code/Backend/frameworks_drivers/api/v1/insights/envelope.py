"""The shape every insights response shares.

`Backend-Stream-B-Measurement.md` states the requirement for all nine
endpoints at once: "Every response carries the epistemic class, `n`, **the
call ids behind each figure**, and withheld reasons." That is a property of
every figure on every screen, so it is one model here rather than nine
near-identical ones that drift.

## Why the wire format is more opinionated than `Figure`

`Figure` already makes a withheld value structurally impossible — it cannot
be constructed with both `WITHHELD` and a number. JSON gives that guarantee
back up: `value` arrives as `null`, and `value ?? 0` is one keystroke away
in every client language. A rate that renders as 0% because nobody had
enough evidence to publish it is the exact failure this layer exists to
prevent, and it would look like a working screen.

So the envelope carries `published` as its own boolean. Clients branch on a
field that means what it says, rather than on the absence of another field.
`withheld_reason` is non-null exactly when `published` is false, and the two
are built from the same source so they cannot disagree.

## Scope travels with every response

"Filters slice, never hide." A figure means nothing without the population
it was computed over, so `ScopeResponse` goes out with every payload: what
was asked for, how many calls were considered, how many matched, and what
was excluded for want of a value rather than for being out of scope. A
client that wanted to render a number without its scope would have to
discard the scope deliberately.

## Composition, not generics

Each endpoint's response model holds a `scope` field rather than
subclassing a generic `Envelope[T]`. Pydantic would serve either, but the
typed client is generated from the OpenAPI document, and a generic produces
schema names like `InsightsEnvelope_ExecScorecard_`. Nine of those is a
client nobody enjoys reading.

## A note on size

Every figure carries every call id behind it, which is what makes a figure
arguable rather than merely stated. At batch-1 volume — 100 calls — this is
free. It will not stay free: a corpus-wide figure at 10,000 calls carries
10,000 ids, and a screen holds many figures. When that bites, the answer is
a separate evidence endpoint keyed by figure, not a flag that quietly drops
the ids and leaves the figure looking the same.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from domain.aggregation.figure import EpistemicClass, WithheldReason

if TYPE_CHECKING:
    from application.ports.insights_source import CorpusQuery, CorpusSlice
    from domain.aggregation.figure import Figure
    from domain.aggregation.filters import FilteredCalls


class FigureResponse(BaseModel):
    """One number and everything needed to judge it."""

    value: float | None = Field(
        default=None,
        description=(
            "The figure, or null when it is withheld. Null is never zero: see "
            "`published`, which is the field to branch on."
        ),
    )
    published: bool = Field(
        description=(
            "False when the figure is withheld. Withheld means nobody has enough "
            "evidence to state a number, which is not the same as a number of zero."
        )
    )
    n: int = Field(description="The sample behind the figure. Equals the number of call ids.")
    epistemic: EpistemicClass = Field(
        description=(
            "MEASURED: computed from the Call Tag Schema's own fields. DERIVED: our "
            "composite rather than a workbook field, and labelled as such wherever it "
            "surfaces. WITHHELD: suppressed, with a reason."
        )
    )
    withheld_reason: WithheldReason | None = Field(
        default=None,
        description="Non-null exactly when `published` is false.",
    )
    caveats: list[str] = Field(
        default_factory=list,
        description="Generated from the numbers, never hand-written.",
    )
    call_ids: list[str] = Field(
        default_factory=list,
        description=(
            "The calls behind the figure, so it can be argued with. Present on "
            "withheld figures too: a reader told four calls is too few should still "
            "be able to open those four."
        ),
    )

    @classmethod
    def of(cls, figure: Figure) -> FigureResponse:
        return cls(
            value=figure.value,
            published=figure.published,
            n=figure.n,
            epistemic=figure.epistemic,
            withheld_reason=figure.withheld_reason,
            caveats=list(figure.caveats),
            call_ids=list(figure.call_ids),
        )


class AppliedFilterResponse(BaseModel):
    """One active filter, for the applied-filters row."""

    field: str
    values: list[str]


class UnmeasurableResponse(BaseModel):
    """Calls dropped by a filter for want of a value, not for differing."""

    field: str
    calls: int


class ScopeResponse(BaseModel):
    """The population a response's figures were computed over.

    Both counts are here because either alone misleads. `matched` without
    `considered` hides how much of the corpus was set aside; `considered`
    without `unmeasurable` makes a shortfall look like a narrower question
    when it is really a field extraction never filled.
    """

    sources: list[str] = Field(
        default_factory=list,
        description="Transcript origins included. Empty means every source.",
    )
    applied_filters: list[AppliedFilterResponse] = Field(default_factory=list)
    considered: int = Field(description="Calls offered to the filters.")
    matched: int = Field(description="Calls the filters kept.")
    unmeasurable: list[UnmeasurableResponse] = Field(
        default_factory=list,
        description=(
            "Per field, calls excluded because the filtered field was absent rather "
            "than different. These are not out of scope; they are unanswerable."
        ),
    )
    excluded_calls: int = Field(
        default=0,
        description=(
            "Stored calls that reached no figure at all — no date, or never "
            "analysed. Counted before filtering."
        ),
    )
    caveats: list[str] = Field(
        default_factory=list,
        description=(
            "Whole-corpus caveats: undated calls, unanalysed calls, and schema "
            "fields the pipeline cannot produce."
        ),
    )

    @classmethod
    def of(cls, corpus: CorpusSlice, filtered: FilteredCalls, query: CorpusQuery) -> ScopeResponse:
        return cls(
            sources=sorted(source.value for source in query.sources),
            applied_filters=[
                AppliedFilterResponse(field=entry.field, values=list(entry.values))
                for entry in filtered.applied
            ],
            considered=filtered.considered,
            matched=filtered.matched,
            unmeasurable=[
                UnmeasurableResponse(field=entry.field, calls=entry.calls)
                for entry in filtered.unmeasurable
            ],
            excluded_calls=corpus.excluded,
            caveats=list(corpus.caveats()),
        )
