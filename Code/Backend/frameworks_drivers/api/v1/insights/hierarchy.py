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
    ranked_brokers: list[BrokerFrictionResponse] = Field(
        description="Only books clearing the ranking floor in lives, worst count first."
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
            windows=[("Broker friction", view.window)],
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
    )
