"""`GET /api/v1/insights/risk` — the account risk screen.

## Ineligible is not unflagged, and the wire format says so

At batch-1 volume most of the 92 employers have a single call in the
window, which is below metric 10's eligibility floor of three. Those
accounts are not low-risk; nobody has enough evidence to say anything about
them at all. If they arrived in the same list as the assessed accounts with
`flagged: false`, every client would render ninety clean bills of health
that were never issued.

So they do not arrive in that list. `assessed` holds only the employers the
window could speak about, and `ineligible` is a separate array of
references with its own count. A client has to go out of its way to conflate
them, which is the opposite of the usual arrangement.

Each assessment carries `state`, a sentence computed from the numbers,
because the three booleans (`eligible`, `flagged`, `quotable`) combine into
claims of very different strength and leaving that to a frontend `if` is
how "not eligible" becomes "not at risk".

## Conditions that did not fire are still returned

All four of metric 10's conditions travel with each assessment, met or not,
and all ten indicator families likewise. A list of only what fired cannot
tell a reader whether the rest were checked and clear or never checked —
which, on a page headed "other conditions observed", is the whole question.

## Exposure is exposure

`Exposure` sums lives and premium behind the flagged accounts and stops.
It is never multiplied by anything: there are no termination outcomes in
this corpus to fit a probability to, so an expected loss would be a number
invented at the point of display. `premium_incomplete` says when the sum is
a floor rather than the whole, because a quietly incomplete total is worse
than a missing one.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, status
from pydantic import BaseModel, Field

from frameworks_drivers.api.dependencies import GetAccountRiskDep
from frameworks_drivers.api.v1.insights.envelope import FigureResponse, ScopeResponse
from frameworks_drivers.api.v1.insights.query import InsightsQueryDep

if TYPE_CHECKING:
    from collections.abc import Sequence

    from application.use_cases.read_insights import AccountRisk
    from domain.aggregation.indicators import Observation
    from domain.aggregation.risk_flag import RiskAssessment

router = APIRouter(prefix="/insights", tags=["insights"])


class ConditionResponse(BaseModel):
    """One of metric 10's four conditions, met or not."""

    code: str
    label: str
    met: bool
    call_ids: list[str] = Field(
        default_factory=list, description="The calls that fired it. Empty when it did not."
    )


class ObservationResponse(BaseModel):
    """One indicator family's standing. Informational — it does not set the flag."""

    code: str
    label: str
    observed: bool
    hits: int
    employer_calls: int
    rate: float | None = Field(
        default=None,
        description="Null when the family cannot be computed, never zero.",
    )
    available: bool = Field(
        description="False when v9 has no field for this family. Not the same as no hits."
    )
    unavailable_because: str = ""


class AccountRiskResponse(BaseModel):
    employer_ref: str
    calls: int = Field(description="Calls for this employer in the window.")
    eligible: bool
    flagged: bool
    quotable: bool = Field(description="Whether there are enough calls to quote this as a figure.")
    state: str = Field(
        description=(
            "What the page says, computed from the numbers. Read this rather than "
            "recombining the booleans: 'not eligible' is not 'not at risk'."
        )
    )
    conditions: list[ConditionResponse]
    conditions_met: int
    evidence: list[str] = Field(
        default_factory=list, description="Every call behind every condition that fired."
    )
    observations: list[ObservationResponse]


class ExposureResponse(BaseModel):
    employers: list[str]
    lives: int
    annual_premium: float
    premium_incomplete: bool = Field(
        description="True when a flagged account has no premium recorded, so this is a floor."
    )
    caveat: str


class RiskScreenResponse(BaseModel):
    scope: ScopeResponse
    as_of: str
    window_weeks: int = Field(description="Metric 10's window, in weeks, ending on `as_of`.")
    assessed: list[AccountRiskResponse] = Field(
        description="Only employers the window could speak about."
    )
    ineligible: list[str] = Field(
        description=(
            "Employers below the eligibility floor, by reference. Kept apart from "
            "`assessed` on purpose: too few calls to assess is not a finding of low "
            "risk, and at current volume most of the book is here."
        )
    )
    ineligible_count: int
    flagged_share: FigureResponse = Field(
        description="Flagged as a share of the *eligible* employers, never of all of them."
    )
    exposure: ExposureResponse


@router.get(
    "/risk",
    response_model=RiskScreenResponse,
    status_code=status.HTTP_200_OK,
    summary="Account risk flags, with what could not be assessed",
)
async def read_account_risk(
    use_case: GetAccountRiskDep,
    query: InsightsQueryDep,
) -> RiskScreenResponse:
    result = await use_case.execute(query.to_request())
    return RiskScreenResponse(
        scope=ScopeResponse.of(result.scope.corpus, result.scope.filtered, query.corpus_query()),
        as_of=result.scope.as_of.isoformat(),
        window_weeks=round(result.window.weeks),
        assessed=[_account(entry) for entry in result.assessed],
        ineligible=list(result.ineligible),
        ineligible_count=len(result.ineligible),
        flagged_share=FigureResponse.of(result.flagged_share),
        exposure=ExposureResponse(
            employers=list(result.exposure.employers),
            lives=result.exposure.lives,
            annual_premium=result.exposure.annual_premium,
            premium_incomplete=result.exposure.premium_incomplete,
            caveat=result.exposure.caveat,
        ),
    )


def _account(entry: AccountRisk) -> AccountRiskResponse:
    return account_risk_response(entry.assessment, entry.observations)


def account_risk_response(
    assessment: RiskAssessment, observations: Sequence[Observation]
) -> AccountRiskResponse:
    """One employer's risk standing, flattened for the wire.

    Shared with the account page so a single account reads the same on both
    screens. Two shapes for one assessment would be two chances for
    "ineligible" to become "not at risk" in different ways.
    """
    return AccountRiskResponse(
        employer_ref=assessment.employer_ref,
        calls=assessment.calls,
        eligible=assessment.eligible,
        flagged=assessment.flagged,
        quotable=assessment.quotable,
        state=assessment.state,
        conditions=[
            ConditionResponse(
                code=condition.code,
                label=condition.label,
                met=condition.met,
                call_ids=list(condition.call_ids),
            )
            for condition in assessment.conditions
        ],
        conditions_met=assessment.conditions_met,
        evidence=list(assessment.evidence),
        observations=[
            ObservationResponse(
                code=observation.family.code,
                label=observation.family.label,
                observed=observation.observed,
                hits=observation.hits,
                employer_calls=observation.employer_calls,
                rate=observation.rate,
                available=observation.family.computable,
                unavailable_because=observation.family.unavailable_because,
            )
            for observation in observations
        ],
    )
