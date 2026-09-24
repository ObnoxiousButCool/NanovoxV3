"""`GET /api/v1/insights/accounts/{employer_ref}` — one account's page.

## A peer comparison that cannot be computed says so

§9 insight 2 is the size-matched contact rate, and at batch-1 volume most
size bands hold no other employer with a publishable rate. `difference` is
then `null`, which the screen renders as "no peer comparison available" —
never as 0%, which would read as "in line with peers" and is the one
conclusion the data cannot support.

`peers` travels with it because a median of two is a different claim from a
median of forty, and a client that only received the median could not tell
them apart.

## Two windows on one page

Metric 1 and metric 4 have their own `window_weeks`, so the contact rate and
the repeat rate state theirs individually, exactly as the exec screen does.

## What is not here

§9 insight 7, broker-of-record drift, belongs on this page and has no
aggregation yet: `CallContext` carries both the broker named aloud and the
broker of record, but nothing compares them. Defining that comparison at
the presentation layer would put a definition somewhere the workbook cannot
see it, so the field is absent rather than approximated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, status
from pydantic import Field

from frameworks_drivers.api.camel import CamelModel
from frameworks_drivers.api.dependencies import DashboardConfigDep, GetAccountDetailDep
from frameworks_drivers.api.v1.insights.envelope import FigureResponse, ScopeResponse
from frameworks_drivers.api.v1.insights.query import InsightsQueryDep
from frameworks_drivers.api.v1.insights.risk import AccountRiskResponse, account_risk_response

if TYPE_CHECKING:
    from application.use_cases.read_insights import AccountDetail

router = APIRouter(prefix="/insights", tags=["insights"])


class WindowedFigureResponse(CamelModel):
    """A figure with the period it was computed over."""

    window_weeks: int
    figure: FigureResponse


class AccountFactsResponse(CamelModel):
    """§9 insight 8 — the facts that raise the stakes on everything else.

    From reference data, not from the pipeline, so nothing here depends on
    extraction agreement.
    """

    employer_ref: str
    name: str
    region: str
    industry: str
    enrolled: int = Field(description="Lives, the peer-band denominator.")
    renewal_month: str
    broker_ref: str = Field(description="Broker of record.")
    annual_premium: float | None = Field(
        default=None, description="Null when not recorded — never zero."
    )
    annual_fee: int


class PeerComparisonResponse(CamelModel):
    band: str | None = Field(
        default=None, description="The size band, in lives. Null when the employer fits none."
    )
    peer_median: float | None = Field(
        default=None,
        description="Median contact rate of publishable peers. Null when the band has none.",
    )
    peers: int = Field(description="Employers behind the median. A median of two is not forty.")
    difference: float | None = Field(
        default=None,
        description=(
            "The employer against its peers, as a proportion: 0.25 is '+25% vs peers'. "
            "Null when either side is missing — render that as 'no comparison "
            "available', never as 0%."
        ),
    )


class AccountResponse(CamelModel):
    scope: ScopeResponse
    as_of: str
    facts: AccountFactsResponse
    contact_rate: WindowedFigureResponse
    peers: PeerComparisonResponse
    repeat_rate: WindowedFigureResponse
    risk: AccountRiskResponse = Field(
        description="This account's risk standing, the same shape as on the risk screen."
    )
    risk_window_weeks: int


@router.get(
    "/accounts/{employer_ref}",
    response_model=AccountResponse,
    status_code=status.HTTP_200_OK,
    summary="One account: contact rate against peers, repeats, and risk",
)
async def read_account(
    employer_ref: str,
    use_case: GetAccountDetailDep,
    config: DashboardConfigDep,
    query: InsightsQueryDep,
) -> AccountResponse:
    detail = await use_case.execute(employer_ref, query.to_request())
    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No employer with reference {employer_ref!r}.",
        )
    return _response(detail, query)


def _response(detail: AccountDetail, query: InsightsQueryDep) -> AccountResponse:
    employer = detail.employer
    band = detail.peers.band
    return AccountResponse(
        scope=ScopeResponse.of(detail.scope.corpus, detail.scope.filtered, query.corpus_query()),
        as_of=detail.scope.as_of.isoformat(),
        facts=AccountFactsResponse(
            employer_ref=employer.reference,
            name=employer.name,
            region=employer.region,
            industry=employer.industry,
            enrolled=employer.enrolled,
            renewal_month=employer.renewal_month,
            broker_ref=employer.broker_ref,
            annual_premium=employer.annual_premium,
            annual_fee=employer.annual_fee,
        ),
        contact_rate=WindowedFigureResponse(
            window_weeks=round(detail.contact_rate_window.weeks),
            figure=FigureResponse.of(detail.contact_rate),
        ),
        peers=PeerComparisonResponse(
            band=band.label if band is not None else None,
            peer_median=detail.peers.peer_median,
            peers=detail.peers.peers,
            difference=detail.peers.difference,
        ),
        repeat_rate=WindowedFigureResponse(
            window_weeks=round(detail.repeat_rate_window.weeks),
            figure=FigureResponse.of(detail.repeat_rate),
        ),
        risk=account_risk_response(detail.risk, detail.observations),
        risk_window_weeks=round(detail.risk_window.weeks),
    )
