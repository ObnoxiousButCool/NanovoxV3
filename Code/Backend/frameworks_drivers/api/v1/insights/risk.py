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

from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Query, status
from pydantic import Field

from frameworks_drivers.api.camel import CamelModel
from frameworks_drivers.api.dependencies import GetAccountRiskDep
from frameworks_drivers.api.v1.insights.envelope import FigureResponse, ScopeResponse
from frameworks_drivers.api.v1.insights.labels import CodedValue, coded
from frameworks_drivers.api.v1.insights.query import InsightsQuery, InsightsQueryDep

if TYPE_CHECKING:
    from collections.abc import Sequence

    from application.use_cases.read_insights import AccountRisk, RiskResult
    from domain.aggregation.distributions import WeekShare
    from domain.aggregation.indicators import Observation
    from domain.aggregation.risk_drivers import Driver
    from domain.aggregation.risk_flag import RiskAssessment

router = APIRouter(prefix="/insights", tags=["insights"])


class ConditionResponse(CamelModel):
    """One of metric 10's four conditions, met or not."""

    code: str
    label: str
    met: bool
    call_ids: list[str] = Field(
        default_factory=list, description="The calls that fired it. Empty when it did not."
    )


class ObservationResponse(CamelModel):
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
    call_ids: list[str] = Field(
        default_factory=list,
        description=(
            "The calls this family was observed on, so the reader can open them. "
            "The envelope's rule — every figure travels with the call ids behind "
            "it — applies to an indicator as much as to a rate: a family reported "
            "on three calls that names none of them cannot be argued with."
        ),
    )
    unavailable_because: str = ""


class AccountRiskResponse(CamelModel):
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
    renewal_month: str | None = Field(
        default=None,
        description=(
            "The employer's renewal month, carried so a screen naming this account "
            "does not have to look it up separately. Null only for a caller — the "
            "account page — that already states its own employer's renewal at the "
            "top level and has no use for a second copy here."
        ),
    )
    months_to_renewal: int | None = Field(
        default=None,
        description=(
            "Whole months from `as_of` to the next renewal. Null when the reference "
            "data's renewal month could not be read, which sorts and reads as "
            "unknown rather than as renewing now."
        ),
    )


class ExposureResponse(CamelModel):
    employers: list[str]
    lives: int
    annual_premium: float
    premium_incomplete: bool = Field(
        description="True when a flagged account has no premium recorded, so this is a floor."
    )
    caveat: str


@dataclass(frozen=True)
class RiskQuery:
    """The two row filters the risk screen adds, per **D12**.

    Separate from `InsightsQuery` on purpose. That model is shared by every
    insights endpoint because the filter bar is one filter bar; these two
    mean something on this screen alone, and a parameter that is silently
    ignored on eight endpoints is exactly the quiet disagreement the shared
    model exists to prevent.

    **There is no `band` parameter, and there will not be one.** D12 leaves
    no band to filter by: the flag is metric 10's and the indicator families
    are a count. `minIndicators` is that count, named as a count.

    These select **rows**, not the population. `flaggedShare` and `exposure`
    are computed over every eligible employer regardless of what is set
    here — a share whose denominator moved with the row filter would be a
    different statistic wearing the same label.
    """

    flagged: Annotated[
        bool | None,
        Query(
            description=(
                "Metric 10's flag. Omitted means both. Note this never selects "
                "ineligible employers — they are not in `assessed` at all, because "
                "too few calls to assess is not a finding of low risk."
            )
        ),
    ] = None
    min_indicators: Annotated[
        int | None,
        Query(
            alias="minIndicators",
            ge=0,
            le=10,
            description=(
                "Keep accounts where at least this many of the ten indicator "
                "families fired. A count, never a risk level: the families are "
                "informational and do not set the flag (D2, D12)."
            ),
        ),
    ] = None

    def keeps(self, entry: AccountRisk) -> bool:
        if self.flagged is not None and entry.assessment.flagged is not self.flagged:
            return False
        return not (self.min_indicators is not None and entry.indicator_count < self.min_indicators)


RiskQueryDep = Annotated[RiskQuery, Depends()]


class OutcomeCountResponse(CamelModel):
    """One outcome and its calls. Zero is a real count, not a gap."""

    outcome: CodedValue
    calls: int


class WeekShareResponse(CamelModel):
    """One week of a share series.

    Two kinds of nothing, kept apart: `calls` is null when the corpus is
    silent about the week, and `share` is null when calls happened but too
    few to publish a rate. A chart draws the first as a gap in the line and
    the second as a gap in the share while still showing the count.
    """

    start: str
    end: str
    calls: int | None = None
    matched: int | None = None
    share: float | None = Field(
        default=None,
        description=(
            "Null below the five-call floor, which is the prototype's own: "
            '"weeks with fewer than five calls are left blank rather than shown '
            'as a swing". Never zero for a week that was not measured.'
        ),
    )


class ChangeResponse(CamelModel):
    """How a driver moved between the first and last part of the window.

    Counts and a noise verdict, never a percentage. At this corpus's volume
    two calls becoming four is "+100%" and is also a coin flip, so
    `beyondNoise` is the only field a screen should use to decide whether to
    say anything happened. It is the same test the exec page's movements
    carry, for the same reason.
    """

    now: int = Field(description="Calls in the last part of the window.")
    prior: int = Field(description="Calls in the first part.")
    expected: float = Field(
        description=(
            "What the later part would have shown if nothing changed except how "
            "busy it was. Without this scaling every busy period reads as a "
            "deterioration."
        )
    )
    beyond_noise: bool
    worse: bool = Field(description="Whether the move is in the bad direction for this family.")


class DriverResponse(CamelModel):
    """One indicator family's share of the book's calls."""

    code: str
    label: str
    calls: int
    call_ids: list[str] = Field(description="So the driver can be argued with.")
    top_category: str | None = Field(
        default=None,
        description=(
            "What these calls were most often about. Context for the driver, "
            "never a second measurement of it. Null when none is recorded."
        ),
    )
    top_touchpoint: str | None = None
    available: bool = Field(
        description=(
            "False when v9 carries no field for this family. Such a driver is "
            "reported with its reason and never as zero — 'we cannot look' and "
            "'nobody raised it' are different findings."
        )
    )
    unavailable_because: str = ""
    change: ChangeResponse | None = Field(
        default=None,
        description=(
            "Null when the window is too short to split, or the family cannot be "
            "computed. Absent is not 'no change'."
        ),
    )


class WithheldPanelResponse(CamelModel):
    """Insight 9 — withheld unconditionally (plan.md's Phase 8 note): no gate
    unlocks it, only a schema change nobody has made."""

    insight: int
    question: str
    why: str
    unlocked_by: str


class RiskScreenResponse(CamelModel):
    scope: ScopeResponse
    as_of: str
    window_weeks: int = Field(description="Metric 10's window, in weeks, ending on `as_of`.")
    assessed: list[AccountRiskResponse] = Field(
        description=(
            "Only employers the window could speak about, most indicators first and "
            "then soonest renewal (D12). Narrowed by `flagged` and `minIndicators`."
        )
    )
    assessed_count: int = Field(
        description=(
            "How many employers were assessed **before** `flagged` and "
            "`minIndicators` narrowed the list. Filters slice, never hide: a "
            "reader has to be able to tell a narrow screen from an empty one."
        )
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
    outcomes: list[OutcomeCountResponse] = Field(
        default_factory=list,
        description=(
            "How the window's calls ended, every outcome including the ones at zero "
            "and in the workbook's order. Categories that reorder with the data "
            "cannot be compared against last week's chart."
        ),
    )
    weekly_unresolved: list[WeekShareResponse] = Field(default_factory=list)
    weekly_resolved: list[WeekShareResponse] = Field(default_factory=list)
    weekly_quality: list[WeekShareResponse] = Field(default_factory=list)
    drivers: list[DriverResponse] = Field(
        default_factory=list,
        description=(
            "Which of the ten indicator families account for the most calls, most "
            "first. Includes the families at zero: these ten are the flag's own "
            "inputs, so 'nobody raised this' is a finding about the book."
        ),
    )
    handling_unavailable: str = Field(
        default="",
        description=(
            "Why the prototype's Handling distribution has no counterpart here. "
            "Said rather than rendered as an empty chart beside a full one."
        ),
    )
    band_calibration: WithheldPanelResponse = Field(
        description="Insight 9, withheld until a termination/renewal outcome exists per employer."
    )
    escalations_triggered: int = Field(description="Metric 6's denominator, over this window.")
    escalations_missed: int = Field(
        description="Warranted and not handled — `Escalation.missed`'s own definition."
    )
    exit_language_calls: int = Field(
        description="Calls carrying the retention_risk signal — exit language, verbatim."
    )


@router.get(
    "/risk",
    response_model=RiskScreenResponse,
    status_code=status.HTTP_200_OK,
    summary="Account risk flags, with what could not be assessed",
)
async def read_account_risk(
    use_case: GetAccountRiskDep,
    query: InsightsQueryDep,
    rows: RiskQueryDep,
) -> RiskScreenResponse:
    result = await use_case.execute(query.to_request())
    return build_risk_response(result, query, rows)


def build_risk_response(
    result: RiskResult, query: InsightsQuery, rows: RiskQuery
) -> RiskScreenResponse:
    """The risk screen on the wire.

    Extracted from the route so `/insights/generated` can read the same
    response this screen renders rather than recomputing it — two builders
    that agree today are two builders, and the day they disagree a sentence
    quotes a number nobody can see on the page.
    """
    shown = [entry for entry in result.assessed if rows.keeps(entry)]
    return RiskScreenResponse(
        scope=ScopeResponse.of(
            result.scope.corpus,
            result.scope.filtered,
            query.corpus_query(),
            windows=[("The account risk flag", result.window)],
        ),
        as_of=result.scope.as_of.isoformat(),
        window_weeks=round(result.window.weeks),
        assessed=[_account(entry) for entry in shown],
        assessed_count=len(result.assessed),
        ineligible=list(result.ineligible),
        ineligible_count=len(result.ineligible),
        flagged_share=FigureResponse.of(result.flagged_share),
        outcomes=[
            # `coded` is the one place an enum becomes a label, so this
            # chart cannot drift from the wording every other panel uses.
            OutcomeCountResponse(outcome=coded(entry.outcome), calls=entry.calls)
            for entry in result.outcomes
        ],
        weekly_unresolved=[_week(entry) for entry in result.weekly_unresolved],
        weekly_resolved=[_week(entry) for entry in result.weekly_resolved],
        weekly_quality=[_week(entry) for entry in result.weekly_quality],
        drivers=[_driver(entry) for entry in result.drivers],
        handling_unavailable=HANDLING_UNAVAILABLE,
        escalations_triggered=result.escalations_triggered,
        escalations_missed=result.escalations_missed,
        exit_language_calls=result.exit_language_calls,
        band_calibration=WithheldPanelResponse(
            insight=result.band_calibration.insight,
            question=result.band_calibration.question,
            why=result.band_calibration.why,
            unlocked_by=result.band_calibration.unlocked_by,
        ),
        exposure=ExposureResponse(
            employers=list(result.exposure.employers),
            lives=result.exposure.lives,
            annual_premium=result.exposure.annual_premium,
            premium_incomplete=result.exposure.premium_incomplete,
            caveat=result.exposure.caveat,
        ),
    )


def _driver(driver: Driver) -> DriverResponse:
    return DriverResponse(
        code=driver.family.code,
        label=driver.family.label,
        calls=driver.calls,
        call_ids=list(driver.call_ids),
        # `category.value` is the workbook's own wording, which `labels.py`
        # deliberately does not remap.
        top_category=driver.top_category.value if driver.top_category else None,
        top_touchpoint=driver.top_touchpoint,
        available=driver.family.computable,
        unavailable_because=driver.family.unavailable_because,
        change=(
            ChangeResponse(
                now=driver.change.now,
                prior=driver.change.prior,
                expected=round(driver.change.expected, 2),
                beyond_noise=driver.change.beyond_noise,
                worse=driver.change.worse,
            )
            if driver.change is not None
            else None
        ),
    )


def _account(entry: AccountRisk) -> AccountRiskResponse:
    return account_risk_response(
        entry.assessment,
        entry.observations,
        renewal_month=entry.renewal_month,
        months_to_renewal=entry.months_to_renewal,
    )


def account_risk_response(
    assessment: RiskAssessment,
    observations: Sequence[Observation],
    *,
    renewal_month: str | None = None,
    months_to_renewal: int | None = None,
) -> AccountRiskResponse:
    """One employer's risk standing, flattened for the wire.

    Shared with the account page so a single account reads the same on both
    screens. Two shapes for one assessment would be two chances for
    "ineligible" to become "not at risk" in different ways.

    `renewal_month` and `months_to_renewal` are keyword-only and default to
    `None`: the account page already states its own employer's renewal at
    the top level (`AccountResponse.renewal_month`) and calls this without
    them, while the risk list's own `_account` passes both so a screen
    reading this list alone can say when a flagged account renews.
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
                call_ids=list(observation.call_ids),
                observed=observation.observed,
                hits=observation.hits,
                employer_calls=observation.employer_calls,
                rate=observation.rate,
                available=observation.family.computable,
                unavailable_because=observation.family.unavailable_because,
            )
            for observation in observations
        ],
        renewal_month=renewal_month,
        months_to_renewal=months_to_renewal,
    )


#: Conflict C8a, said on the wire rather than left as a missing chart.
HANDLING_UNAVAILABLE = (
    "The prototype also splits these calls by handling archetype. `archetype` is not "
    "one of the sixteen Call Tag Schema fields and has no workbook source (conflict "
    "C8a), so it is absent rather than invented."
)


def _week(entry: WeekShare) -> WeekShareResponse:
    return WeekShareResponse(
        start=entry.start,
        end=entry.end,
        calls=entry.calls,
        matched=entry.matched,
        share=entry.share,
    )
