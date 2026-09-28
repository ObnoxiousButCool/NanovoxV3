"""`GET /api/v1/insights/generated` — the one AI surface per screen.

## Why it is its own endpoint

The figures must never wait on a model. A screen that embedded its insights
in `/insights/exec` would hold the whole scorecard behind a provider call
that can be slow, rate-limited or down — and the numbers are the part that
matters. So the screen paints, and the sentences arrive after.

It also keeps the failure honest. When there is no generated text, this
endpoint still answers 200 with an explicit unavailable state (U2), rather
than a screen half-failing because one panel could not be written.

## The facts are built here, never accepted from the client

The caller says which screen it is looking at and passes the same filters;
this endpoint recomputes the response and flattens *that* into facts. A
client-supplied fact set would let anyone put any number into the model's
mouth and get it back in a sentence that looks like ours.

`build_exec_response` is shared with `/insights/exec` for the same reason:
the facts are the response, not a second computation of it.

## Percentages are rounded the way the screen rounds them

The screens render a rate as `Math.round(value * 100)%`. This mirrors that
exactly, including the half-up rounding — Python's own `round` is
half-to-even and would print 12% where the screen prints 13%. The whole
guardrail rests on the model seeing the number a reader sees, so a
one-in-a-thousand disagreement here would be a sentence quoting a figure
that is not on the page.
"""

from __future__ import annotations

import math
from typing import Annotated, Literal

from fastapi import APIRouter, Query, status
from pydantic import Field

from application.use_cases.generate_insights import GenerateInsightsRequest
from domain.aggregation.exec_scorecard import SCORECARD_METRICS
from domain.insights.facts import Fact, FactSet
from domain.insights.generated import GeneratedInsights, Lens
from frameworks_drivers.api.camel import CamelModel
from frameworks_drivers.api.dependencies import (
    DashboardConfigDep,
    GenerateInsightsDep,
    GetAccountRiskDep,
    GetExecScorecardDep,
    InsightProviderDep,
)
from frameworks_drivers.api.v1.insights.envelope import FigureResponse
from frameworks_drivers.api.v1.insights.exec_scorecard import (
    ExecScorecardResponse,
    build_exec_response,
)
from frameworks_drivers.api.v1.insights.labels import CodedValue, coded
from frameworks_drivers.api.v1.insights.query import InsightsQueryDep
from frameworks_drivers.api.v1.insights.risk import (
    RiskQuery,
    RiskScreenResponse,
    build_risk_response,
)

router = APIRouter(prefix="/insights", tags=["insights"])

#: The screens that have an insight surface. The fact builders are per
#: screen because what counts as a fact is: a generic one would have to
#: guess whether a number is a rate, a count or a population, and guessing
#: wrong means the model is shown "12" where the screen shows "12%".
Screen = Literal["exec", "risk"]


def percent(value: float) -> str:
    """A rate as the screens print it: whole-number percent, half up."""
    return f"{math.floor(value * 100 + 0.5)}%"


class InsightResponse(CamelModel):
    """One generated sentence."""

    key: str
    sentence: str = Field(
        description=(
            "Generated text. Every number in it appears in the figures this screen "
            "published; a sentence that stated anything else was refused, and the "
            "whole surface would read UNAVAILABLE rather than show the rest."
        )
    )
    kind: CodedValue = Field(
        description=(
            "INFERENCE — what the figures appear to mean. RECOMMENDATION — a "
            "suggested action. Never OBSERVED: a figure's `basis` says where a "
            "number came from, and generated text is never one of those."
        )
    )
    severity: CodedValue = Field(
        description=(
            "Reading order only. Not a risk level, and never an account's: "
            "'flagged' means metric 10 and nothing else."
        )
    )
    lens: CodedValue = Field(
        description=(
            "Which of the four exec readings this sentence belongs under. A client "
            "requirement (U1), so the four and their order are fixed."
        )
    )
    fact_keys: list[str] = Field(
        description="The figures this sentence read, so it can be checked against them."
    )
    issue_key: str | None = Field(
        default=None,
        description=(
            "The playbook behind its 'what to do' link. Null when none applies, or "
            "when the model named one that does not exist."
        ),
    )


class GeneratedInsightsResponse(CamelModel):
    """The insight surface for one screen, generated or explicitly not."""

    status: CodedValue = Field(
        description=(
            "GENERATED or UNAVAILABLE. Unavailable is a state to render, not an "
            "error and not an empty list: the panel says it could not be written "
            "and why, the same way a withheld figure does."
        )
    )
    lenses: list[CodedValue] = Field(
        description=(
            "The four exec readings, in order, always — whether or not any insight "
            "was filed under one. A client requirement (U1), so it travels with the "
            "response rather than being written down a second time in each client: "
            "a grid that could only name the lenses it had sentences for would let "
            "a reader mistake 'nothing to say' for 'not considered'."
        )
    )
    insights: list[InsightResponse] = Field(
        description=(
            "Always present, empty when the status is UNAVAILABLE. Required rather "
            "than defaulted so a client never has to tell an absent list from an "
            "empty one — they would render the same and mean different things."
        )
    )
    reason: CodedValue | None = Field(
        default=None, description="Non-null exactly when the status is UNAVAILABLE."
    )
    provider: str | None = Field(
        default=None, description="Who wrote these. Null when nothing was written."
    )
    model: str | None = Field(default=None)

    @classmethod
    def of(cls, generated: GeneratedInsights) -> GeneratedInsightsResponse:
        return cls(
            status=coded(generated.status),
            lenses=[coded(lens) for lens in Lens],
            insights=[
                InsightResponse(
                    key=insight.key,
                    sentence=insight.sentence,
                    kind=coded(insight.kind),
                    severity=coded(insight.severity),
                    lens=coded(insight.lens),
                    fact_keys=list(insight.fact_keys),
                    issue_key=insight.issue_key,
                )
                for insight in generated.insights
            ],
            reason=coded(generated.reason) if generated.reason is not None else None,
            provider=generated.provider,
            model=generated.model,
        )


def _slug(label: str) -> str:
    """A fact key from a label, with every digit and separator removed.

    Fact keys are shown to the model alongside the numbers, so a key must
    never contain one.
    """
    kept = [character.lower() if character.isalpha() else " " for character in label]
    return "_".join("".join(kept).split())


def _rate(key: str, label: str, figure: FigureResponse) -> Fact:
    """One rate as a fact, printed the way the screen prints it."""
    if not figure.published:
        return Fact(
            key=key,
            label=label,
            display=None,
            n=figure.n,
            basis=figure.basis.code if figure.basis else None,
            withheld_reason=(figure.withheld_reason.code if figure.withheld_reason else "WITHHELD"),
        )
    return Fact(
        key=key,
        label=label,
        display=percent(figure.value or 0.0),
        n=figure.n,
        basis=figure.basis.code if figure.basis else None,
    )


def exec_facts(response: ExecScorecardResponse) -> FactSet:
    """The executive scorecard, flattened into what a sentence may say.

    Every published figure on the screen and every withheld one, because
    "we cannot yet say, and here is why" is a sentence worth generating and
    the model cannot write it about a figure it was never shown.
    """
    facts = [
        _rate(metric.key, metric.name, metric.figure)
        for metric in response.metrics
        if metric.key in SCORECARD_METRICS
    ]
    # Keyed from the label, never from a position. A key like
    # `escalation_1` would put the digit 1 into the facts the model reads,
    # and the guardrail counts every number it is shown as quotable — so an
    # index in a key silently licenses a number nobody measured.
    facts.extend(
        _rate(_slug(entry.label), entry.label, entry.figure) for entry in response.escalation
    )
    facts.append(_rate("intent_routed", "Commercial intent routed", response.intent_routed))

    return FactSet(
        subject="the executive scorecard",
        facts=tuple(facts),
        # The call count in the page head and the date it ends on are true of
        # the screen without being figures, so a sentence may name them.
        context_numbers=frozenset({str(response.calls), *response.as_of.split("-")}),
    )


def _count(key: str, label: str, value: int) -> Fact:
    """A population, not a rate. Printed as the screen prints it: a bare
    integer, with no percent sign to be mistaken for one."""
    return Fact(key=key, label=label, display=str(value), n=value, basis="OBSERVED")


def risk_facts(response: RiskScreenResponse) -> FactSet:
    """The risk screen, flattened into what a sentence may say.

    Four headline figures, the flag's population either side of it, and how
    the calls ended. Two deliberate omissions:

    - **The weekly series is not here.** Any sentence worth writing about a
      series is a comparison, and a comparison is a number nobody computed —
      the guardrail would refuse it, so offering the weeks would only buy
      rejected answers and the tokens to produce them.
    - **Annual premium is not here.** The screen shows lives and not money;
      facts are what the reader can see, and a figure the page withholds is
      not made quotable by being on the wire.
    """
    facts = [
        _rate("flagged_share", "Flagged, of those assessable", response.flagged_share),
        _count("accounts_assessed", "Accounts assessed", response.assessed_count),
        _count(
            "accounts_not_assessable",
            "Accounts that could not be assessed",
            response.ineligible_count,
        ),
        _count("accounts_flagged", "Accounts flagged", len(response.exposure.employers)),
        _count("lives_behind_flagged", "Lives behind the flagged", response.exposure.lives),
    ]
    facts.extend(
        _count(
            f"ended_{_slug(entry.outcome.label)}",
            f"Calls that ended {entry.outcome.label.lower()}",
            entry.calls,
        )
        for entry in response.outcomes
    )

    return FactSet(
        subject="the account risk screen",
        facts=tuple(facts),
        context_numbers=frozenset({str(response.window_weeks), *response.as_of.split("-")}),
    )


@router.get(
    "/generated",
    response_model=GeneratedInsightsResponse,
    status_code=status.HTTP_200_OK,
    summary="Generated insights for one screen",
)
async def read_generated_insights(
    use_case: GenerateInsightsDep,
    provider: InsightProviderDep,
    exec_use_case: GetExecScorecardDep,
    risk_use_case: GetAccountRiskDep,
    config: DashboardConfigDep,
    query: InsightsQueryDep,
    screen: Annotated[Screen, Query(description="Which screen's figures to read.")] = "exec",
    limit: Annotated[int, Query(ge=1, le=8, description="How many sentences at most.")] = 4,
) -> GeneratedInsightsResponse:
    # `screen` has one value today. The match stays because adding the second
    # screen must be a new fact builder, not a new branch inside one.
    match screen:
        case "exec":
            card = await exec_use_case.execute(query.to_request())
            facts = exec_facts(build_exec_response(card, config, query))
        case "risk":
            # `RiskQuery()` with nothing set, deliberately: its two filters
            # select rows, and the figures below are computed over every
            # eligible employer regardless (D12). Passing the reader's row
            # filter would not change one of these numbers.
            risk = await risk_use_case.execute(query.to_request())
            facts = risk_facts(build_risk_response(risk, query, RiskQuery()))

    generated = await use_case.execute(GenerateInsightsRequest(facts=facts, limit=limit), provider)
    return GeneratedInsightsResponse.of(generated)
