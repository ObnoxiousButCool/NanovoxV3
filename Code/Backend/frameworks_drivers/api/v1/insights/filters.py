"""What the filter bar can offer.

## What this is not

It is **not** true that a client cannot otherwise discover these values.
`GET /insights/hierarchy` already returns `scope.corpus.employers` and
`scope.corpus.brokers` — the unfiltered reference data, not the filtered
slice — so complete employer and broker lists are reachable today. Any
reasoning here that starts "a client can only see what it asked for" is
wrong about those two, and an earlier draft of this module said exactly
that.

## What it is

Three lists that exist nowhere else, and one structural point.

**`regions`** is only derivable by a client re-deriving it from employers.
**`agentRefs`** and **`touchpoints`** are not returned by any endpoint at
all. And the **labels** for the coded filters live in `labels.py`,
server-side; without them a client copies the map, and a copied map drifts
from the sheet it was copied from.

The structural point is cost and coupling. Scraping a filter bar's options
out of `/insights/hierarchy` means computing a whole screen — the drill
tree, the region by category matrix, systemic categories and ranked broker
friction — to populate four dropdowns, and it ties every screen's filter bar
to the shape of one other screen's payload. A filter bar that breaks because
the hierarchy response changed is a bug nobody would look for there.

## Two kinds of list, and the response keeps them apart

**Reference lists** — regions, brokers, employers — come from the workbook's
master data, so they are complete whether or not anyone called. A broker
with no calls this period is still a broker you may filter by, and leaving
it out would read as "this broker does not exist".

**Observed lists** — agents and touchpoints — have no reference sheet. They
exist only as tags on calls, so the list is what the corpus happens to
contain and will grow as more calls are analysed. Presenting five lists as
if they were all the same kind of thing would hide that.

## Filters are not applied here, and that part is load-bearing

This endpoint reads the corpus scope — sources and period — and deliberately
ignores `request.filters`. Narrowing the options by the current selection is
a one-way door: filter to one broker, and a bar built from the response
offers one broker and the reader cannot widen again.

## Enum filters, and the ones with no display wording

The enum-backed filters are already in the generated client, so this
endpoint does not repeat their values — only their labels, where
`labels.py` defines any.

The rest — outcome, category, product line, intent, quality band — have
**no display wording defined anywhere**: not in `labels.py`, not in the
workbook. `labels.py` records why for categories ("already words", straight
from the sheet), but `RESOLVED` and `PARTIALLY RESOLVED` are codes a screen
will have to render somehow, and nobody has said how. That is a real gap
rather than an oversight here, so this endpoint names them in
`unlabelledFilters` instead of inventing wording that would then be hard to
dislodge.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import Field

from application.use_cases.read_insights import FilterOptions
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.control_exception_type import ControlExceptionType
from domain.value_objects.rule_confidence import RuleConfidence
from domain.value_objects.rule_layer import RuleLayer
from domain.value_objects.signal_severity import SignalSeverity
from domain.value_objects.signal_type import SignalType
from frameworks_drivers.api.camel import CamelModel
from frameworks_drivers.api.dependencies import GetFilterOptionsDep
from frameworks_drivers.api.v1.insights.envelope import PeriodResponse
from frameworks_drivers.api.v1.insights.labels import CodedValue, coded
from frameworks_drivers.api.v1.insights.query import InsightsQueryDep

router = APIRouter(prefix="/insights", tags=["insights"])


class BrokerOptionResponse(CamelModel):
    ref: str
    agency: str = Field(description="What a reader calls this broker.")
    name: str = Field(description="The individual contact, not the agency.")
    region: str


class EmployerOptionResponse(CamelModel):
    ref: str
    name: str
    region: str
    broker_ref: str = Field(description="Broker of record, for a dependent filter.")


class FilterOptionsResponse(CamelModel):
    """Every value the filter bar can offer, by where it came from."""

    regions: list[str] = Field(description="From reference data. Complete.")
    brokers: list[BrokerOptionResponse] = Field(
        description="From reference data. Every broker, including those with no calls."
    )
    employers: list[EmployerOptionResponse] = Field(
        description="From reference data. Every employer, including those with no calls."
    )
    agent_refs: list[str] = Field(
        description=(
            "Observed on calls, not reference data, so this grows as more calls are "
            "analysed. References only — agent names are not available to this layer."
        )
    )
    touchpoints: list[str] = Field(
        description="Observed on calls, not reference data. Grows with the corpus."
    )

    signals: list[CodedValue]
    signal_severities: list[CodedValue]
    complaint_targets: list[CodedValue]
    control_exception_types: list[CodedValue]
    rule_layers: list[CodedValue]
    rule_confidences: list[CodedValue]

    corpus_period: PeriodResponse | None = Field(
        default=None,
        description=(
            "The first and last dated call available. The period control needs it to "
            "offer weeks and months: a client cannot name a week of a corpus whose "
            "extent it does not know. Null when no call carries a date."
        ),
    )
    unlabelled_filters: list[str] = Field(
        description=(
            "Filters whose values have no display wording anywhere — not here, not in "
            "the workbook. A client must render the code. Named rather than silently "
            "omitted, so the gap is visible instead of being filled by invented text."
        )
    )


#: Filters the client already has values for, but which nobody has defined
#: display wording for. Listed so the absence is a stated finding rather than
#: something each screen quietly solves its own way.
UNLABELLED = ("outcome", "category", "productLine", "intent", "qualityBand")


@router.get(
    "/filters",
    response_model=FilterOptionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Every value the filter bar can offer",
)
async def read_filter_options(
    use_case: GetFilterOptionsDep,
    query: InsightsQueryDep,
) -> FilterOptionsResponse:
    options: FilterOptions = await use_case.execute(query.to_request())

    return FilterOptionsResponse(
        regions=list(options.regions),
        brokers=[
            BrokerOptionResponse(
                ref=broker.reference,
                agency=broker.agency,
                name=broker.name,
                region=broker.region,
            )
            for broker in options.brokers
        ],
        employers=[
            EmployerOptionResponse(
                ref=employer.reference,
                name=employer.name,
                region=employer.region,
                broker_ref=employer.broker_ref,
            )
            for employer in options.employers
        ],
        agent_refs=list(options.agent_refs),
        touchpoints=list(options.touchpoints),
        signals=[coded(signal) for signal in SignalType],
        signal_severities=[coded(severity) for severity in SignalSeverity],
        complaint_targets=[coded(target) for target in ComplaintAttribution],
        control_exception_types=[coded(kind) for kind in ControlExceptionType],
        rule_layers=[coded(layer) for layer in RuleLayer],
        rule_confidences=[coded(confidence) for confidence in RuleConfidence],
        corpus_period=(
            PeriodResponse(**{"from": options.available_from, "to": options.available_until})
            if options.available_from is not None or options.available_until is not None
            else None
        ),
        unlabelled_filters=list(UNLABELLED),
    )
