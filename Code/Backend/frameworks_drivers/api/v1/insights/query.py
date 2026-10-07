"""The filter set as query parameters, shared by every insights endpoint.

One model because the filter bar is one filter bar: the prototype's scope
row is the same on all nine screens, and nine endpoints each parsing their
own subset would let the screens quietly disagree about what a filter means.

## camelCase, like the response keys

A query parameter is the same surface a client reads, so the multi-word
ones are `productLine` and `asOf` rather than `product_line` and `as_of`.
Splitting the convention between the response body and the query string
would leave every caller guessing which half they are in.

## Repeated parameters, not comma-separated lists

`?category=Claims%20%26%20EOB&category=Billing%20%26%20Premium` rather than
one comma-joined value. The Metrics sheet's own category names contain `&`
and spaces, and at least one product line could reasonably contain a comma
later; a separator that can appear inside a value is a parser waiting to
split the wrong string. Repetition has no such failure mode and every HTTP
client already speaks it.

## Unset is not empty

A parameter that was not sent narrows nothing. That matches
`InsightFilters`, where an empty selection means "no narrowing on this
field" rather than "match nothing" — an unfiltered dashboard is the common
case, and a selection that matched nothing would render it blank.

## Validation happens here, not deeper

An unknown category is rejected at the edge with a 422 naming the field,
because the alternative is a figure computed over a filter that silently
matched nothing. FastAPI does that for free once the parameter is typed as
the enum, which is why these are typed as the domain's own enums rather
than as strings mapped later.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Annotated

from fastapi import Depends, Query

from application.ports.insights_source import CorpusQuery
from application.use_cases.read_insights import InsightsRequest
from domain.aggregation.filters import InsightFilters
from domain.errors import ValidationError
from domain.value_objects.call_source import CallSource
from domain.value_objects.category import Category
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.intent_type import IntentType
from domain.value_objects.outcome import Outcome
from domain.value_objects.product_line import ProductLine
from domain.value_objects.quality_band import QualityBand
from domain.value_objects.signal_type import SignalType


@dataclass(frozen=True)
class InsightsQuery:
    """Every insights endpoint's filter set, as it arrives."""

    # --- Account scope
    region: Annotated[list[str] | None, Query(description="Employer region.")] = None
    broker: Annotated[
        list[str] | None,
        Query(description="Broker of record, from reference data — not who was named aloud."),
    ] = None
    employer: Annotated[list[str] | None, Query(description="Employer reference.")] = None
    agent: Annotated[list[str] | None, Query(description="Agent reference.")] = None

    # --- Call attributes
    category: Annotated[list[Category] | None, Query()] = None
    product_line: Annotated[
        list[ProductLine] | None,
        Query(
            alias="productLine",
            description="Calls touching this line. A call may touch several.",
        ),
    ] = None
    touchpoint: Annotated[
        list[str] | None,
        Query(description="Where the failure originated, not where it surfaced."),
    ] = None
    outcome: Annotated[list[Outcome] | None, Query()] = None
    signal: Annotated[list[SignalType] | None, Query()] = None
    intent: Annotated[list[IntentType] | None, Query()] = None
    complaint_target: Annotated[
        list[ComplaintAttribution] | None, Query(alias="complaintTarget")
    ] = None
    quality_band: Annotated[list[QualityBand] | None, Query(alias="qualityBand")] = None

    # --- Yes/no. Omitted means unset; false is a real selection.
    escalated: Annotated[bool | None, Query()] = None
    complaint: Annotated[bool | None, Query(description="Whether a complaint was made.")] = None
    compliance_exception: Annotated[bool | None, Query(alias="complianceException")] = None
    repeat: Annotated[
        bool | None,
        Query(
            description=(
                "Keep only repeat contacts, or only calls that are not one. Omitted "
                "means both. A repeat is a relationship between two calls rather than "
                "a property of one, so it is computed over the whole corpus and "
                "applied after the other filters — a repeat does not stop being one "
                "because the call it followed was filtered out."
            )
        ),
    ] = None

    # --- Corpus scope, which is not a filter over calls
    source: Annotated[
        list[CallSource] | None,
        Query(
            description=(
                "Transcript origins to include. Omitted means every source. The "
                "published dashboard reads CORPUS_PDF alone, so a transcript pasted "
                "to try the pipeline out never lands in a metric."
            )
        ),
    ] = None
    #: The requested period. It bounds which calls enter the corpus slice and
    #: does **not** redefine any metric's window — decision D11 in `Documents/notes/plan.md`
    #: §5. `dashboard.yaml` sets `window_weeks` per metric and they differ on
    #: one screen (contact rate 12, first-contact resolution 4), so a single
    #: period could not stand in for all of them without silently making some
    #: figure mean something else.
    from_: Annotated[
        date | None,
        Query(
            alias="from",
            description=(
                "Earliest call date to include. Omitted means no lower bound. "
                "Bounds the corpus, not a metric's window."
            ),
        ),
    ] = None
    to: Annotated[
        date | None,
        Query(
            description=(
                "Latest call date to include. Omitted means no upper bound. "
                "Bounds the corpus, not a metric's window."
            ),
        ),
    ] = None
    as_of: Annotated[
        date | None,
        Query(
            alias="asOf",
            description=(
                "The date every window ends on. Omitted means today. Supplying it "
                "makes a figure reproducible."
            ),
        ),
    ] = None

    def __post_init__(self) -> None:
        """Reject an inverted range here rather than returning an empty screen.

        A `from` after `to` selects no calls at all, and every figure would
        come back withheld for want of a sample — which reads as "we have no
        evidence" when the truth is "you asked for nothing". A 400 naming the
        two values is the only answer that cannot be misread.

        This is a `ValidationError`, so it surfaces as this application's 400
        problem document. 422 here means the request did not match the schema,
        which FastAPI produces on its own; an inverted range parses perfectly
        and fails a rule, which is what a `ValidationError` is for.
        """
        if self.from_ is not None and self.to is not None and self.from_ > self.to:
            raise ValidationError(
                "The period starts after it ends.",
                detail=f"from={self.from_.isoformat()} is later than to={self.to.isoformat()}.",
            )

    def filters(self) -> InsightFilters:
        return InsightFilters(
            regions=_set(self.region),
            broker_refs=_set(self.broker),
            employer_refs=_set(self.employer),
            agent_refs=_set(self.agent),
            categories=_set(self.category),
            product_lines=_set(self.product_line),
            touchpoints=_set(self.touchpoint),
            outcomes=_set(self.outcome),
            signals=_set(self.signal),
            intents=_set(self.intent),
            complaint_targets=_set(self.complaint_target),
            quality_bands=_set(self.quality_band),
            escalated=self.escalated,
            complaint_present=self.complaint,
            compliance_exception=self.compliance_exception,
        )

    def corpus_query(self) -> CorpusQuery:
        """The corpus scope, echoed into the response's `scope`."""
        return CorpusQuery(sources=_set(self.source), since=self.from_, until=self.to)

    def to_request(self) -> InsightsRequest:
        return InsightsRequest(
            filters=self.filters(),
            sources=_set(self.source),
            as_of=self.as_of,
            since=self.from_,
            until=self.to,
            repeat=self.repeat,
        )


def _set[T](values: list[T] | None) -> frozenset[T]:
    """An unsent parameter narrows nothing, so `None` becomes empty."""
    return frozenset(values or ())


InsightsQueryDep = Annotated[InsightsQuery, Depends()]
