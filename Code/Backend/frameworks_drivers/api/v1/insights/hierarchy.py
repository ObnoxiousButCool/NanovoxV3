"""`GET /api/v1/insights/hierarchy` — isolated or systemic.

## The matrix is dense on purpose

Every category appears in every region's row, including at zero. §9's
reading rule is "a dark column is book-wide, a dark cell is local", and that
only works if the columns line up — a sparse matrix that omitted empty cells
would put different categories at different positions per row and destroy
the comparison the screen exists to make.

Zero here is a real count, not a withheld figure. The matrix is call volume,
published as base measure B1 with no min n, so there is nothing to suppress.
That is the one place on these screens where a zero may be printed plainly.

## Employers with no calls stay in the tree

`drill_tree` keeps them as empty leaves. "This employer has not called" is
information; dropping them would make a quiet region look like a small one,
which is the filters-slice-never-hide practice applied to a hierarchy.

## Two broker tables, and why

`brokers` is the screen's own table: every broker holding an account in
scope, counts only, no rate at all. `rankedBrokers` is the friction
ranking, which does publish a per-100-lives rate and therefore keeps a
floor in lives under it. Merging them would force one of the two to accept
the other's population — either a rate on ten calls, or a small broker
meeting the pattern test and never appearing.

## The ranking floor is not a filter on the data

`ranked_brokers` holds only brokers whose book clears the ranking floor in
lives. The rest are not hidden — their rows still compute for an account
page — but a three-group agency should not top a league table on one call.
`systemic` names the categories present in every region, and is deliberately
a weak test: presence, not a volume threshold, because a stronger one needs
a per-region denominator the matrix does not carry.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import Field

from frameworks_drivers.api.camel import CamelModel
from frameworks_drivers.api.dependencies import DashboardConfigDep, GetHierarchyDep
from frameworks_drivers.api.v1.insights.envelope import FigureResponse, ScopeResponse
from frameworks_drivers.api.v1.insights.query import InsightsQueryDep

router = APIRouter(prefix="/insights", tags=["insights"])


class EmployerNodeResponse(CamelModel):
    employer_ref: str
    name: str
    calls: int
    call_ids: list[str]


class BrokerNodeResponse(CamelModel):
    broker_ref: str
    calls: int
    employers: list[EmployerNodeResponse]


class RegionNodeResponse(CamelModel):
    region: str
    calls: int
    brokers: list[BrokerNodeResponse]


class MatrixRowResponse(CamelModel):
    region: str
    counts: dict[str, int] = Field(
        description=(
            "Every category, including at zero. Zero is a real count here — call "
            "volume has no min n — and the columns must line up across rows for the "
            "dark-column reading to work."
        )
    )


class RegionRowResponse(CamelModel):
    """One region, as the "By region" table counts it."""

    region: str
    accounts: int = Field(
        description=(
            "Every employer reference data puts in the region, not every one that "
            "called. A region where four of sixteen accounts rang is not a "
            "four-account region."
        )
    )
    flagged: int = Field(description="Metric 10, assessed over metric 10's own window.")
    calls: int
    unresolved: int


class BrokerRowResponse(CamelModel):
    """One broker, as the "By broker" table counts it.

    Counts only, and no rate: a three-group broker has roughly ten calls,
    and there is not enough there to divide. `rankedBrokers` publishes a
    rate over the books big enough to carry one, and answers a different
    question with a different population.
    """

    broker_ref: str
    agency: str
    name: str
    region: str
    groups_in_book: int = Field(
        description=(
            "From the Broker Master sheet, never a count of calls — so the "
            "denominator beside the numerator is not built out of it."
        )
    )
    calls: int
    adverse_mentions: int
    adverse_employers: int = Field(
        description="Distinct employers behind those mentions. The pattern test needs both."
    )
    pattern_fires: bool
    pattern_reached: str = Field(
        description="What the pattern test reached, computed from the numbers, fired or not."
    )
    flagged_accounts: int


class ComplaintOwnershipResponse(CamelModel):
    """How much of the complaint load is ours.

    Two counts over the complaints made, not a share over everyone who
    rang — a different figure from the complaint rate, and they are not
    interchangeable. Every present complaint carries a party, so the
    remainder is another party's and never unattributed.
    """

    ours: int
    total: int


class PatternTestResponse(CamelModel):
    """Trigger rule 2, reported whether or not it fired."""

    fires: bool
    adverse_mentions: int
    distinct_employers: int
    reached: str = Field(
        description="What the test reached, computed from the numbers, fired or not."
    )
    call_ids: list[str]


class BrokerFrictionResponse(CamelModel):
    broker_ref: str
    adverse_calls: list[str]
    by_touchpoint: list[tuple[str, int]] = Field(
        description="Adverse mentions by where the failure originated, worst first."
    )
    pattern: PatternTestResponse
    rate_per_hundred_lives: FigureResponse | None = Field(
        default=None,
        description=("Secondary sort only, never a headline. Null for a book under the floor."),
    )


class BrokerNamingResponse(CamelModel):
    """What the broker tables rest on, for a reader looking at noughts."""

    named: int = Field(description="Calls in scope where a caller named a broker aloud.")
    calls: int = Field(description="Calls in scope.")
    unattributed: int = Field(
        description=(
            "Calls raising a broker-conduct concern without naming anyone. The "
            "signal says a broker was at fault; only the tag says which, so "
            "these appear in no broker row."
        )
    )
    note: str = Field(
        description=(
            "The caveat with these numbers in it, for the screen to show as "
            "written. Empty when nothing is missing, so a complete corpus "
            "carries no boilerplate."
        )
    )


class HierarchyResponse(CamelModel):
    scope: ScopeResponse
    as_of: str
    window_weeks: int = Field(
        description="One window across the whole screen, so every cell counts the same period."
    )
    tree: list[RegionNodeResponse]
    matrix: list[MatrixRowResponse]
    systemic: list[str] = Field(
        description=(
            "Categories present in every region. A presence test, not a volume "
            "threshold — it names the columns worth reading first, nothing more."
        )
    )
    regions: list[RegionRowResponse] = Field(
        description="Most flagged accounts first, then most calls."
    )
    brokers: list[BrokerRowResponse] = Field(
        description=(
            "Every broker holding an account in scope, most adverse mentions first. "
            "No ranking floor: this table publishes no rate, so a floor would only "
            "hide the small broker the pattern test exists to find."
        )
    )
    complaints: ComplaintOwnershipResponse
    ranked_brokers: list[BrokerFrictionResponse] = Field(
        description="Only books clearing the ranking floor in lives, worst count first."
    )
    broker_naming: BrokerNamingResponse = Field(
        description=(
            "How much of the book the broker tables can see. A broker is "
            "counted only where a caller said the name, so a column of noughts "
            "needs this beside it to be read correctly."
        )
    )


@router.get(
    "/hierarchy",
    response_model=HierarchyResponse,
    status_code=status.HTTP_200_OK,
    summary="Region, broker and employer: isolated or systemic",
)
async def read_hierarchy(
    use_case: GetHierarchyDep,
    config: DashboardConfigDep,
    query: InsightsQueryDep,
) -> HierarchyResponse:
    view = await use_case.execute(query.to_request())
    return HierarchyResponse(
        scope=ScopeResponse.of(
            view.scope.corpus,
            view.scope.filtered,
            query.corpus_query(),
        ),
        as_of=view.scope.as_of.isoformat(),
        window_weeks=round(view.window.weeks),
        tree=[
            RegionNodeResponse(
                region=region.region,
                calls=region.calls,
                brokers=[
                    BrokerNodeResponse(
                        broker_ref=broker.broker_ref,
                        calls=broker.calls,
                        employers=[
                            EmployerNodeResponse(
                                employer_ref=node.employer_ref,
                                name=node.name,
                                calls=node.calls,
                                call_ids=list(node.call_ids),
                            )
                            for node in broker.employers
                        ],
                    )
                    for broker in region.brokers
                ],
            )
            for region in view.tree
        ],
        matrix=[
            MatrixRowResponse(
                region=region,
                counts={category.value: count for category, count in row},
            )
            for region, row in view.matrix
        ],
        systemic=[category.value for category in view.systemic],
        regions=[
            RegionRowResponse(
                region=row.region,
                accounts=row.accounts,
                flagged=row.flagged,
                calls=row.calls,
                unresolved=row.unresolved,
            )
            for row in view.regions
        ],
        brokers=[
            BrokerRowResponse(
                broker_ref=row.broker_ref,
                agency=row.agency,
                name=row.name,
                region=row.region,
                groups_in_book=row.groups_in_book,
                calls=row.calls,
                adverse_mentions=row.adverse_mentions,
                adverse_employers=row.adverse_employers,
                pattern_fires=row.pattern_fires,
                pattern_reached=row.pattern_reached,
                flagged_accounts=row.flagged_accounts,
            )
            for row in view.brokers
        ],
        complaints=ComplaintOwnershipResponse(
            ours=view.complaints.ours, total=view.complaints.total
        ),
        ranked_brokers=[
            BrokerFrictionResponse(
                broker_ref=row.broker_ref,
                adverse_calls=list(row.adverse_calls),
                by_touchpoint=list(row.by_touchpoint),
                pattern=PatternTestResponse(
                    fires=row.pattern.fires,
                    adverse_mentions=row.pattern.adverse_mentions,
                    distinct_employers=row.pattern.distinct_employers,
                    reached=row.pattern.reached(config),
                    call_ids=list(row.pattern.call_ids),
                ),
                rate_per_hundred_lives=(
                    FigureResponse.of(row.rate_per_hundred_lives)
                    if row.rate_per_hundred_lives is not None
                    else None
                ),
            )
            for row in view.ranked_brokers
        ],
        broker_naming=BrokerNamingResponse(
            named=view.broker_naming.named,
            calls=view.broker_naming.calls,
            unattributed=view.broker_naming.unattributed,
            note=view.broker_naming.note,
        ),
    )
