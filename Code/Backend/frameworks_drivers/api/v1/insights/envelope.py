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

from collections.abc import Sequence
from datetime import date
from typing import TYPE_CHECKING

from pydantic import Field

from domain.aggregation.call_tags import CallContext, Window
from domain.aggregation.patterns import window_note
from frameworks_drivers.api.camel import CamelModel
from frameworks_drivers.api.v1.insights.labels import CodedValue, coded

if TYPE_CHECKING:
    from application.ports.insights_source import CorpusQuery, CorpusSlice
    from domain.aggregation.figure import Figure
    from domain.aggregation.filters import FilteredCalls


class FigureResponse(CamelModel):
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
    basis: CodedValue | None = Field(
        default=None,
        description=(
            "Where the number came from, and only that — never whether it is shown. "
            "OBSERVED: counted from the Call Tag Schema's own fields. DERIVED: our "
            "composite rather than a workbook field, and labelled as such wherever it "
            "surfaces. REFERENCE: an account fact from the workbook, not from a call. "
            "Null only on a withheld figure with no origin to name — a question the "
            "v9 schema has no field for. Branch on `published` for suppression."
        ),
    )
    withheld_reason: CodedValue | None = Field(
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
            basis=coded(figure.basis) if figure.basis is not None else None,
            withheld_reason=(
                coded(figure.withheld_reason) if figure.withheld_reason is not None else None
            ),
            caveats=list(figure.caveats),
            call_ids=list(figure.call_ids),
        )


class AppliedFilterResponse(CamelModel):
    """One active filter, for the applied-filters row."""

    field: str
    values: list[str]


class UnmeasurableResponse(CamelModel):
    """Calls dropped by a filter for want of a value, not for differing."""

    field: str
    calls: int


class PeriodResponse(CamelModel):
    """The requested period, echoed so a reader can see what was asked for.

    Separate from each metric's `windowWeeks`, and deliberately so: the two
    are different things (decision D11), and collapsing them into one field
    is what would let a twelve-week rate be read as a three-week one.
    """

    from_: date | None = Field(
        default=None, alias="from", description="Earliest call date included. Null means unbounded."
    )
    to: date | None = Field(
        default=None, description="Latest call date included. Null means unbounded."
    )


class ScopeResponse(CamelModel):
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
    period: PeriodResponse | None = Field(
        default=None,
        description=(
            "The period the caller asked for, echoed back. Null at either end "
            "means that end was unbounded. It bounds which calls were read and "
            "does not narrow any metric's own window — see `caveats`."
        ),
    )
    corpus_period: PeriodResponse | None = Field(
        default=None,
        description=(
            "The full extent of dated calls available, ignoring the requested "
            "period. This is what a period control offers: without it a client "
            "that has narrowed once has no way to know what it narrowed from. "
            "Null when no call carries a date."
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
    def of(
        cls,
        corpus: CorpusSlice,
        filtered: FilteredCalls,
        query: CorpusQuery,
        *,
        windows: Sequence[tuple[str, Window]] = (),
    ) -> ScopeResponse:
        """The scope, plus a caveat for every window that disagrees with it.

        `windows` is what this endpoint actually computed over, named as a
        reader would name it. Passing them is how decision D11 becomes
        visible rather than merely true: the period bounds the corpus, each
        metric keeps its own window, and where the two disagree the response
        says so instead of quietly publishing a narrower figure.

        Two ways they disagree, and `window_note` says both in one
        sentence: a window can reach **outside** the period asked for, and
        it can **leave calls out** of the scope. They were two sentences
        from two functions, one of them written per metric, and a reader
        picking a single week met six paragraphs above the figures.
        """
        return cls(
            sources=sorted(source.value for source in query.sources),
            period=(
                PeriodResponse(**{"from": query.since, "to": query.until})
                if query.since is not None or query.until is not None
                else None
            ),
            corpus_period=(
                PeriodResponse(**{"from": corpus.available_from, "to": corpus.available_until})
                if corpus.available_from is not None or corpus.available_until is not None
                else None
            ),
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
            caveats=[
                *corpus.caveats(),
                *_window_notes(windows, filtered.calls, query.since, query.until),
            ],
        )


def _window_notes(
    windows: Sequence[tuple[str, Window]],
    calls: Sequence[CallContext],
    since: date | None,
    until: date | None,
) -> list[str]:
    """One sentence per distinct window, not per metric.

    The executive screen's five metrics run over two windows, and a sentence
    each put five near-identical paragraphs above the figures. Grouped by
    the window's own bounds, in the order the endpoint listed them, so the
    sentences stay stable between requests.
    """
    grouped: dict[tuple[date, date], list[str]] = {}
    spans: dict[tuple[date, date], Window] = {}
    for subject, window in windows:
        key = (window.start, window.end)
        grouped.setdefault(key, []).append(subject)
        spans.setdefault(key, window)
    notes = []
    for key, subjects in grouped.items():
        note = window_note(spans[key], calls, since, until, subjects=subjects)
        if note is not None:
            notes.append(note)
    return notes
