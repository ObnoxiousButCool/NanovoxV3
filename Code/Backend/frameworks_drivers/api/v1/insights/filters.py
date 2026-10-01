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
**`agents`** is the Agent Roster, so the bar can offer a name rather than
AGT-01, and **`touchpoints`** is not returned by any endpoint at all. And
the **labels** for the coded filters live in `labels.py`, server-side;
without them a client copies the map, and a copied map drifts from the
sheet it was copied from.

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

## Enum filters, and the one with no display wording

The enum-backed filters are already in the generated client, so this
endpoint does not repeat their values — only their labels, where
`labels.py` defines any: `outcome`, `product line`, `intent` and
`quality band` all have real wording there now.

`category` is the one with **no display wording defined anywhere**: not in
`labels.py`, not in the workbook. `labels.py` records why ("already words",
straight from the sheet, and a label identical to its own code is not a
label) — `category` travels as a plain string, and this endpoint names it
in `unlabelledFilters` rather than inventing a second vocabulary for it.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import Field

from application.use_cases.read_insights import FilterOptions
from domain.value_objects.category import Category
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.control_exception_type import ControlExceptionType
from domain.value_objects.intent_type import IntentType
from domain.value_objects.outcome import Outcome
from domain.value_objects.product_line import ProductLine
from domain.value_objects.quality_band import QualityBand
from domain.value_objects.rule_confidence import RuleConfidence
from domain.value_objects.rule_layer import RuleLayer
from domain.value_objects.signal_severity import SignalSeverity
from domain.value_objects.signal_type import SignalType, severity_of
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


class AgentOptionResponse(CamelModel):
    ref: str
    name: str = Field(description="The roster's name, or the reference for an agent not on it.")
    band: str = Field(description="Empty for an agent who took a call and is not on the roster.")


class EmployerOptionResponse(CamelModel):
    ref: str
    name: str
    region: str
    broker_ref: str = Field(description="Broker of record, for a dependent filter.")


class SignalOptionResponse(CamelModel):
    code: str
    label: str
    severity: CodedValue = Field(
        description=(
            "Fixed per signal type by the Signal Taxonomy sheet — never decided per "
            "call, the same source `EvidencedItem.severity` reads."
        )
    )


class FilterOptionsResponse(CamelModel):
    """Every value the filter bar can offer, by where it came from."""

    regions: list[str] = Field(description="From reference data. Complete.")
    brokers: list[BrokerOptionResponse] = Field(
        description="From reference data. Every broker, including those with no calls."
    )
    employers: list[EmployerOptionResponse] = Field(
        description="From reference data. Every employer, including those with no calls."
    )
    agents: list[AgentOptionResponse] = Field(
        description=(
            "The Agent Roster, so the filter can offer a name rather than AGT-01. An "
            "agent who took a call and is not on the roster keeps a row under their "
            "reference — dropping them would remove a filter for calls that exist."
        )
    )
    touchpoints: list[str] = Field(
        description="Observed on calls, not reference data. Grows with the corpus."
    )
    categories: list[str] = Field(
        description=(
            "The Call Tag Schema's own wording, like `touchpoints` — not mapped in "
            "`labels.py` because the workbook's values are already the words a reader "
            "wants, and a label identical to its own code is not a label."
        )
    )

    signals: list[SignalOptionResponse]
    signal_severities: list[CodedValue]
    complaint_targets: list[CodedValue]
    control_exception_types: list[CodedValue]
    rule_layers: list[CodedValue]
    rule_confidences: list[CodedValue]
    product_lines: list[CodedValue]
    outcomes: list[CodedValue]
    intents: list[CodedValue]
    quality_bands: list[CodedValue]

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
#:
#: `outcome`, `productLine`, `intent` and `qualityBand` moved out once
#: `labels.py` gained real wording for them — `category` stays: the
#: workbook's values are already the words a reader wants, and (as
#: `labels.py` puts it for `Preventable`) a label identical to its own code
#: is not a label.
UNLABELLED = ("category",)


def _signal_option(signal: SignalType) -> SignalOptionResponse:
    base = coded(signal)
    return SignalOptionResponse(
        code=base.code, label=base.label, severity=coded(severity_of(signal))
    )


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
        agents=[
            AgentOptionResponse(ref=agent.reference, name=agent.name, band=agent.band)
            for agent in options.agents
        ],
        touchpoints=list(options.touchpoints),
        categories=[category.value for category in Category],
        signals=[_signal_option(signal) for signal in SignalType],
        signal_severities=[coded(severity) for severity in SignalSeverity],
        complaint_targets=[coded(target) for target in ComplaintAttribution],
        control_exception_types=[coded(kind) for kind in ControlExceptionType],
        rule_layers=[coded(layer) for layer in RuleLayer],
        rule_confidences=[coded(confidence) for confidence in RuleConfidence],
        product_lines=[coded(line) for line in ProductLine],
        outcomes=[coded(outcome) for outcome in Outcome],
        intents=[coded(intent) for intent in IntentType],
        quality_bands=[coded(band) for band in QualityBand],
        corpus_period=(
            PeriodResponse(**{"from": options.available_from, "to": options.available_until})
            if options.available_from is not None or options.available_until is not None
            else None
        ),
        unlabelled_filters=list(UNLABELLED),
    )
