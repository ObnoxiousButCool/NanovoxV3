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

## Insight 7 — broker-of-record drift

Now built, in `domain/aggregation/broker_drift.py` rather than here: the
comparison is a definition, and a definition written in a router is one the
workbook cannot see.

`drift` carries `checked` and `mismatches` separately so the panel can tell
a clean book from an unexamined one. Zero mismatches out of fourteen
mentions is a finding; zero mentions is not. The sheet asks for a flag
rather than a rate, so nothing here divides.
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
    eligible: int = Field(
        description="Lives the plan covers. `enrolled` of these is the participation."
    )
    participation: float | None = Field(
        default=None,
        description=(
            "Enrolled over eligible. Null where the workbook records none — never "
            "0.0, which would read as 'nobody enrolled'."
        ),
    )
    lines_held: str
    cobra_regime: str
    dental_sponsorship: str = Field(
        description=(
            "ER for employer-sponsored, VOL for voluntary. Rule P-18 reaches only the first."
        )
    )
    planned_calls: int = Field(
        description=(
            "Calls the workbook's design plans for this account at full corpus. "
            "A plan, never a count: the corpus is a sample of it."
        )
    )
    renewal_in_months: int | None = Field(
        default=None,
        description=(
            "Whole months to the renewal, 0 meaning this month. Null where the "
            "workbook's month could not be parsed — never a guessed countdown."
        ),
    )


class StakeResponse(CamelModel):
    """One workbook fact that raises the stakes on everything else.

    Reference, not observation. Nothing here counts a call: these are true
    whether or not anybody rang, which is why the screen puts them beneath
    the indicators rather than among them.
    """

    code: str
    label: str
    detail: str = Field(
        description=(
            "The figures behind the note, already worded, including the rule "
            "reference where one sets the threshold."
        )
    )


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


class DriftResponse(CamelModel):
    """§9 insight 7. A flag, never a rate."""

    flagged: bool
    checked: int = Field(
        description=(
            "Broker mentions where both sides resolved, so the comparison could be "
            "made. Zero checked with zero mismatches is not a clean book — it is an "
            "unexamined one, and `finding` says which."
        )
    )
    mismatches: list[str] = Field(
        default_factory=list,
        description="Calls where the named broker is not the broker of record.",
    )
    unresolved: list[str] = Field(
        default_factory=list,
        description=(
            "Mentions where one side was unknown. Not counted as drift: an unknown "
            "is not a disagreement, and scoring it as one would manufacture a "
            "finding out of a gap."
        ),
    )
    finding: str = Field(
        description="The sentence the panel shows, including when nothing is wrong."
    )


class TopicCountResponse(CamelModel):
    """One category this account called about."""

    category: str = Field(
        description="The workbook's own wording, e.g. 'Claims & EOB'. Not a code."
    )
    calls: int


class AccountProfileResponse(CamelModel):
    """The account's own calls, counted.

    Counts, never rates, so none of these is suppressed: zero unresolved out
    of four calls is a true statement where a zero *rate* over four is not.

    **There is no average quality here, and there will not be one.** Metric
    12 is defined per agent, and `domain/aggregation/agent_events.py` states
    that rolling it up to an employer is forbidden by the Metrics sheet. The
    v2 prototype shows an "Average call quality" tile on this page; the
    prototype wins on presentation and the workbook wins on definitions
    (`plan.md` §3.0), so that tile is carried as a conflict rather than
    served.

    `scored_calls` is not that figure in disguise. It counts how many calls
    carry a score, which is coverage of a per-call figure the calls table
    already prints; it says nothing about how high those scores are. It is
    sent so the screen can state the withholding with a number behind it
    rather than leaving a silent hole where the prototype has a tile.
    """

    calls: int = Field(description="This account's calls in the risk window.")
    unresolved: int
    repeat_contacts: int = Field(
        description=(
            "Metric 4's own numerator over this account, so the count cannot "
            "disagree with the repeat rate beside it."
        )
    )
    escalations_missed: int = Field(
        description="Warranted and not handled. A call with no escalation is in neither."
    )
    uncategorised: int = Field(
        description=(
            "Calls whose category the pipeline never filled. Sent so the topics "
            "below can be reconciled against `calls` rather than quietly falling "
            "short of it."
        )
    )
    scored_calls: int = Field(
        description=(
            "How many of `calls` carry a quality score. Coverage, not quality: "
            "no average over an employer is published, here or anywhere."
        )
    )
    topics: list[TopicCountResponse] = Field(
        description=(
            "What they called about, most first. Only the categories this account "
            "raised — unlike the outcome chart, a category nobody called about is "
            "not a finding here."
        )
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
    drift: DriftResponse
    profile: AccountProfileResponse
    stakes: list[StakeResponse] = Field(
        description=(
            "Workbook facts that raise the stakes, most consequential first. "
            "Empty is a real answer: nothing structural stands out."
        )
    )
    calls_in_period: int = Field(
        description=(
            "This account's calls in the selected period. `profile.calls` counts "
            "the risk window instead, so the two differ when the period is wider "
            "— sent so a screen can say which calls its counts leave out."
        )
    )


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
    return build_account_response(detail, query)


def build_account_response(detail: AccountDetail, query: InsightsQueryDep) -> AccountResponse:
    employer = detail.employer
    band = detail.peers.band
    return AccountResponse(
        scope=ScopeResponse.of(
            detail.scope.corpus,
            detail.scope.filtered,
            query.corpus_query(),
            windows=[
                ("Contact rate", detail.contact_rate_window),
                ("Repeat rate", detail.repeat_rate_window),
                ("The account risk flag", detail.risk_window),
            ],
        ),
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
            eligible=employer.eligible,
            participation=employer.participation,
            lines_held=employer.lines_held,
            cobra_regime=employer.cobra_regime,
            dental_sponsorship=employer.dental_sponsorship,
            planned_calls=employer.planned_calls,
            renewal_in_months=detail.renewal_in_months,
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
        drift=DriftResponse(
            flagged=detail.drift.flagged,
            checked=detail.drift.checked,
            mismatches=list(detail.drift.mismatches),
            unresolved=list(detail.drift.unresolved),
            finding=detail.drift.finding,
        ),
        stakes=[
            StakeResponse(code=stake.code, label=stake.label, detail=stake.detail)
            for stake in detail.stakes
        ],
        calls_in_period=detail.calls_in_period,
        profile=AccountProfileResponse(
            calls=detail.profile.calls,
            unresolved=detail.profile.unresolved,
            repeat_contacts=detail.profile.repeat_contacts,
            escalations_missed=detail.profile.escalations_missed,
            uncategorised=detail.profile.uncategorised,
            scored_calls=detail.profile.scored_calls,
            topics=[
                # `category.value` is the workbook's own wording; `labels.py`
                # deliberately does not map categories, because re-labelling
                # them would put a second vocabulary beside the sheet's.
                TopicCountResponse(category=topic.category.value, calls=topic.calls)
                for topic in detail.profile.topics
            ],
        ),
    )
