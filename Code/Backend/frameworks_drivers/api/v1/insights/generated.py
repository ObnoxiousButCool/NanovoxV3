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

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import Field

from application.use_cases.generate_insights import GenerateInsightsRequest
from application.use_cases.read_insights import AgentsView, HierarchyView
from domain.aggregation.exec_scorecard import SCORECARD_METRICS
from domain.insights.facts import Fact, FactSet
from domain.insights.generated import GeneratedInsights, Lens, UnavailableReason
from frameworks_drivers.api.camel import CamelModel
from frameworks_drivers.api.dependencies import (
    DashboardConfigDep,
    GenerateInsightsDep,
    GetAccountDetailDep,
    GetAccountRiskDep,
    GetAgentsDep,
    GetExecScorecardDep,
    GetHierarchyDep,
    InsightProviderDep,
)
from frameworks_drivers.api.v1.insights.accounts import (
    AccountResponse,
    WindowedFigureResponse,
    build_account_response,
)
from frameworks_drivers.api.v1.insights.envelope import FigureResponse
from frameworks_drivers.api.v1.insights.exec_scorecard import (
    CategoryConcernResponse,
    ExecScorecardResponse,
    TrendsResponse,
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
Screen = Literal["exec", "risk", "account", "hierarchy", "agents"]

#: How many sentences a screen shows when the caller does not say.
DEFAULT_INSIGHTS = 4

#: How many sentences an account page shows at most.
ACCOUNT_INSIGHTS = 2

#: How many sentences the exec page shows at most — **three per lens across
#: the four lenses**, which is what `exec.html` renders and what the panel's
#: own subtitle promises the reader. The shared default of four filled one
#: lens each and left the subtitle making a promise the API could not keep.
EXEC_INSIGHTS = 12

#: Emerging entries the exec screen actually draws: every riser that gained
#: at least `MIN_RISE` calls as a card, and the five largest fallers in the
#: "Easing" aside. Mirrors `EmergingPanel` in `ExecScreen.tsx` — the
#: selection lives there because the panel owns its own layout, and a fact
#: the reader cannot see is the one thing a generated sentence may never
#: rest on. If that panel's rule changes, this changes with it.
#:
#: A threshold and not a count: the panel takes everything that clears the
#: bar, so a run with six risers draws six cards and a cap of three here
#: would starve the model of two of them.
MIN_RISE = 5
EASING_SHOWN = 5


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


class FactResponse(CamelModel):
    """One figure a sentence was allowed to read, as the screen prints it.

    The evidence behind a generated sentence is the figures it was given,
    so this is what the card opens to show. Sent from here rather than
    resolved on the client: the fact set is built per screen by
    `exec_facts`, `risk_facts` and the rest, and a second implementation in
    TypeScript would be a second definition of what counts as a fact.

    A withheld fact travels too. "Commercial intent capture — too few calls
    to publish" is a reading the model is entitled to write about, and the
    card has to be able to show what it read.
    """

    key: str
    label: str = Field(description="How a reader would name it.")
    display: str | None = Field(
        default=None,
        description="The number as printed, e.g. '74%'. Null exactly when withheld.",
    )
    n: int = Field(description="The sample behind it.")
    basis: str | None = None
    withheld_reason: str | None = Field(
        default=None, description="Why there is no number. Non-null exactly when `display` is null."
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
    facts: list[FactResponse] = Field(
        default_factory=list,
        description=(
            "Every figure offered to the model for this screen, so a card can "
            "show the ones its sentence read rather than naming their keys. "
            "Empty when nothing was generated."
        ),
    )
    reason: CodedValue | None = Field(
        default=None, description="Non-null exactly when the status is UNAVAILABLE."
    )
    provider: str | None = Field(
        default=None, description="Who wrote these. Null when nothing was written."
    )
    model: str | None = Field(default=None)

    @classmethod
    def of(
        cls, generated: GeneratedInsights, facts: FactSet | None = None
    ) -> GeneratedInsightsResponse:
        """`facts` is omitted where nothing was generated to read them."""
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
            facts=[
                FactResponse(
                    key=fact.key,
                    label=fact.label,
                    display=fact.display,
                    n=fact.n,
                    basis=fact.basis,
                    withheld_reason=fact.withheld_reason,
                )
                for fact in (facts.facts if facts is not None else ())
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
            # The label, not the code: the model is given the words a
            # reader would see, for the same reason `display` carries the
            # printed number. Handed `BELOW_MIN_N` it writes "BELOW_MIN_N",
            # and handed `WITHHELD` it wrote "is WITHHELD" into a sentence.
            withheld_reason=(
                figure.withheld_reason.label if figure.withheld_reason else "not published"
            ),
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
    facts.extend(_concern_facts(response.area_of_concern))
    facts.extend(_emerging_facts(response.trends))

    return FactSet(
        subject="the executive scorecard",
        facts=tuple(facts),
        # The call count in the page head and the date it ends on are true of
        # the screen without being figures, so a sentence may name them.
        context_numbers=frozenset({str(response.calls), *response.as_of.split("-")}),
    )


def _concern_facts(concern: CategoryConcernResponse | None) -> list[Fact]:
    """The "Area of concern" panel, as facts.

    Three of its four numbers, because the panel prints three: the
    unresolved count and the two escalation counts. `calls` is on the wire
    and not on the screen, so it is not here — a sentence may only rest on
    what the reader can check.

    Without these the four lenses had nothing to read but eight rates, and
    every sentence came back a restatement of one of them.
    """
    if concern is None:
        return []
    return [
        _count(
            "area_of_concern_unresolved",
            f"Unresolved calls in {concern.category}",
            concern.unresolved,
        ),
        _count(
            "area_of_concern_escalations_handled",
            f"Escalations handled in {concern.category}",
            concern.escalations_handled,
        ),
        _count(
            "area_of_concern_escalations_triggered",
            f"Escalations warranted in {concern.category}",
            concern.escalations_triggered,
        ),
    ]


def _emerging_facts(trends: TrendsResponse) -> list[Fact]:
    """The "Emerging issues" panel, as facts — and only the rows it draws.

    `trends.emerging` carries every tracked category, touchpoint, signal and
    product line; the panel draws every riser that gained `MIN_RISE` calls or
    more, and the five largest fallers. Offering the whole list would licence
    the model to quote a count sitting in no panel on the page.

    A row that rose and has since fallen back is not here, because `rising`
    excludes it and the panel gives it no card — only a line saying how many
    there were. A sentence about one of those would be about something the
    reader cannot point at.

    A riser carries both ends of its own bars, so "rose from two to five" is
    two facts the reader can see rather than a subtraction the model
    performed. A faller carries its latest slice only: the aside prints the
    count and the change chip, not a sparkline to read a first slice off.
    """
    rising = sorted(
        (entry for entry in trends.emerging if entry.rising and entry.delta >= MIN_RISE),
        key=lambda entry: -entry.delta,
    )
    easing = sorted(
        (entry for entry in trends.emerging if entry.delta < 0),
        key=lambda entry: entry.delta,
    )[:EASING_SHOWN]

    facts: list[Fact] = []
    for entry in rising:
        if not entry.buckets:
            continue
        key = f"rising_{_slug(entry.kind)}_{_slug(entry.label)}"
        facts.append(
            _count(
                f"{key}_latest", f"{entry.label}, calls in the latest slice", entry.buckets[-1].hits
            )
        )
        facts.append(
            _count(
                f"{key}_first", f"{entry.label}, calls in the first slice", entry.buckets[0].hits
            )
        )
    for entry in easing:
        if not entry.buckets:
            continue
        facts.append(
            _count(
                f"easing_{_slug(entry.kind)}_{_slug(entry.label)}",
                f"{entry.label}, calls in the latest slice",
                entry.buckets[-1].hits,
            )
        )
    return facts


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


def hierarchy_facts(view: HierarchyView) -> FactSet:
    """Isolated or systemic, flattened into what a sentence may say.

    Counts only, which is what the screen publishes: the page's own note is
    that a region holds about sixteen calls in batch 1, too few for a rate,
    so there is no rate here for a sentence to quote.

    The heatmap is not here. Any sentence worth writing about a matrix is a
    comparison between cells, and a comparison is a number nobody computed
    — the guardrail would refuse it, so offering the cells would only buy
    rejected answers. `systemic` is here instead: it is the reading of the
    matrix the screen itself offers, already computed.
    """
    adverse = [row for row in view.brokers if row.adverse_mentions]
    facts = [
        _count("complaints_about_us", "Complaints attributed to us", view.complaints.ours),
        _count("complaints_total", "Complaints made", view.complaints.total),
        _count("brokers_named_adversely", "Brokers named adversely", len(adverse)),
        _count(
            "adverse_mentions",
            "Calls naming a broker adversely",
            sum(row.adverse_mentions for row in view.brokers),
        ),
        _count(
            "brokers_meeting_the_pattern_test",
            "Brokers meeting the pattern test",
            sum(1 for row in view.brokers if row.pattern_fires),
        ),
        _count("brokers_in_scope", "Brokers holding an account in scope", len(view.brokers)),
        _count(
            "regions_with_a_flagged_account",
            "Regions with a flagged account",
            sum(1 for row in view.regions if row.flagged),
        ),
        _count("regions", "Regions", len(view.regions)),
        _count(
            "categories_in_every_region",
            "Call topics present in every region",
            len(view.systemic),
        ),
    ]
    # Every region, because the region table is the largest thing on the
    # page and a sentence about it will reach for a number in it. Offering
    # only the top row left the model quoting a figure nobody published,
    # and the guardrail rejected the whole surface rather than show it.
    for row in view.regions:
        facts.append(_count(f"calls_{_slug(row.region)}", f"Calls from {row.region}", row.calls))
        facts.append(
            _count(
                f"unresolved_{_slug(row.region)}",
                f"Unresolved calls from {row.region}",
                row.unresolved,
            )
        )
        facts.append(
            _count(
                f"flagged_{_slug(row.region)}",
                f"Flagged accounts in {row.region}",
                row.flagged,
            )
        )
        facts.append(
            _count(f"accounts_{_slug(row.region)}", f"Accounts in {row.region}", row.accounts)
        )
    return FactSet(
        subject="the isolated-or-systemic screen",
        facts=tuple(facts),
        context_numbers=frozenset(
            {str(round(view.window.weeks)), *view.scope.as_of.isoformat().split("-")}
        ),
    )


def agents_facts(view: AgentsView) -> FactSet:
    """Agent conduct, flattened into what a sentence may say.

    Events, never scores. The page's whole framing is that an event can be
    attributed to a person at any volume and an average cannot, so the
    per-agent quality range is deliberately absent from the facts: a
    sentence quoting it would be doing the thing the screen refuses.

    The band medians are absent for the same reason one step removed. They
    are publishable figures, but a sentence about them is a comparison
    between bands, and that number is not computed anywhere.
    """
    exceptions = sum(count for entry in view.agents for _, count in entry.events.control_exceptions)
    rules = sum(len(entry.events.knowledge_errors) for entry in view.agents)
    missed = sum(len(entry.events.escalations_missed) for entry in view.agents)
    minimum = view.min_calls_for_a_rate or 0
    facts = [
        _count("compliance_exceptions", "Compliance exceptions", exceptions),
        _count("rules_stated_wrongly", "Rules stated wrongly", rules),
        _count(
            "agents_stating_a_rule_wrongly",
            "Agents who stated a rule wrongly",
            sum(1 for entry in view.agents if entry.events.knowledge_errors),
        ),
        _count("escalations_missed", "Escalations missed", missed),
        _count(
            "escalations_refused",
            "Calls where the caller asked for a supervisor and did not get one",
            len(view.escalations_refused),
        ),
        _count("agents_on_the_roster", "Agents on the roster", len(view.roster)),
        _count(
            "agents_with_enough_calls",
            f"Agents with the {minimum} calls a rate needs",
            sum(1 for entry in view.agents if len(entry.events.calls) >= minimum) if minimum else 0,
        ),
        _count(
            "busiest_agent_calls",
            "Calls taken by the busiest agent",
            max((len(entry.events.calls) for entry in view.agents), default=0),
        ),
    ]
    return FactSet(
        subject="the agent conduct screen",
        facts=tuple(facts),
        context_numbers=frozenset(
            {str(minimum), str(round(view.window.weeks)), *view.scope.as_of.isoformat().split("-")}
        ),
    )


def _per_thousand(key: str, label: str, entry: WindowedFigureResponse) -> Fact:
    """A rate per 1,000 lives, printed as the account page prints it.

    One decimal place, matching `per1000` on the screen. The whole guardrail
    rests on the model seeing the number a reader sees, so this mirrors the
    frontend's formatting rather than choosing its own.
    """
    figure = entry.figure
    if not figure.published:
        return Fact(
            key=key,
            label=label,
            display=None,
            n=figure.n,
            basis=figure.basis.code if figure.basis else None,
            # The label, not the code: the model is given the words a
            # reader would see, for the same reason `display` carries the
            # printed number. Handed `BELOW_MIN_N` it writes "BELOW_MIN_N",
            # and handed `WITHHELD` it wrote "is WITHHELD" into a sentence.
            withheld_reason=(
                figure.withheld_reason.label if figure.withheld_reason else "not published"
            ),
        )
    return Fact(
        key=key,
        label=label,
        display=f"{figure.value or 0.0:.1f}",
        n=figure.n,
        basis=figure.basis.code if figure.basis else None,
    )


def account_facts(response: AccountResponse) -> FactSet:
    """One account, flattened into what a sentence about it may say.

    The account's own counts, its two rates, how it sits against its peers,
    and the flag's standing. Three deliberate omissions:

    - **Enrolled lives, premium and the renewal month.** They are reference
      facts about what the account *is*, and the page labels them so. A
      generated sentence that mixed "1,450 lives" into a reading of the
      calls would blur the one distinction the REFERENCE chip exists to
      make.
    - **The topic ranking.** Its categories are prose, and offering the
      model a list of labels invites a sentence built from the shape of the
      list rather than from a figure.
    - **Anything about quality.** Metric 12 is per agent; an account-level
      quality figure does not exist and must not appear to.
    """
    profile = response.profile
    facts = [
        _count("calls_in_period", "Calls in the period", profile.calls),
        _count("unresolved", "Calls that ended unresolved", profile.unresolved),
        _count("repeat_contacts", "Repeat contacts", profile.repeat_contacts),
        _count(
            "escalations_missed",
            "Escalations warranted and not handled",
            profile.escalations_missed,
        ),
        _per_thousand("contact_rate", "Contact rate per 1,000 lives", response.contact_rate),
        _rate("repeat_rate", "Failure-driven repeat rate", response.repeat_rate.figure),
        _count(
            "conditions_met",
            # Digits, not "of four": a spelled number is refused on sight,
            # and a label that cannot be quoted is a label that rejects
            # every sentence naming its figure.
            "Risk conditions met, of 4",
            response.risk.conditions_met,
        ),
        _count(
            "indicator_families_observed",
            "Indicator families observed",
            len([o for o in response.risk.observations if o.observed]),
        ),
        _count(
            "broker_mismatches",
            "Calls naming a broker other than the one on record",
            len(response.drift.mismatches),
        ),
    ]

    peers = response.peers
    if peers.peer_median is not None and peers.peers > 0:
        facts.append(
            Fact(
                key="peer_median_contact_rate",
                label=f"Median contact rate for the {peers.band or 'peer'} band",
                display=f"{peers.peer_median:.1f}",
                # The peers are the sample behind this median, not calls.
                n=peers.peers,
                basis="DERIVED",
            )
        )

    return FactSet(
        subject=f"the account page for {response.facts.name}",
        facts=tuple(facts),
        context_numbers=frozenset({str(response.risk_window_weeks), *response.as_of.split("-")}),
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
    account_use_case: GetAccountDetailDep,
    hierarchy_use_case: GetHierarchyDep,
    agents_use_case: GetAgentsDep,
    config: DashboardConfigDep,
    query: InsightsQueryDep,
    screen: Annotated[Screen, Query(description="Which screen's figures to read.")] = "exec",
    limit: Annotated[
        int | None,
        Query(
            ge=1,
            le=12,
            description=(
                "How many sentences at most. Omitted, each screen uses its own default: "
                "twelve on the exec page, which groups them under four lenses, and two on "
                "an account page, which has fewer figures to read."
            ),
        ),
    ] = None,
    employer_ref: Annotated[
        str | None,
        Query(
            alias="employerRef",
            description="Required when `screen` is `account`; ignored otherwise.",
        ),
    ] = None,
) -> GeneratedInsightsResponse:
    # One fact builder per screen, never a branch inside one: what counts as
    # a fact differs per page, and a shared builder would have to guess
    # whether a number is a rate, a count or a population.
    per_screen_limit = DEFAULT_INSIGHTS if limit is None else limit

    match screen:
        case "exec":
            card = await exec_use_case.execute(query.to_request())
            facts = exec_facts(build_exec_response(card, config, query))
            # Twelve, not four. The page groups its sentences under four
            # lenses (U1) and the shared default gave each lens one, under a
            # subtitle promising three. A caller who names a limit keeps it.
            if limit is None:
                per_screen_limit = EXEC_INSIGHTS
        case "account":
            if employer_ref is None:
                raise HTTPException(
                    # `HTTP_422_UNPROCESSABLE_ENTITY` is deprecated in the
                    # installed Starlette, and this project turns warnings
                    # into errors, so reading it raises rather than warns.
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="`employerRef` is required when screen is `account`.",
                )
            detail = await account_use_case.execute(employer_ref, query.to_request())
            if detail is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No employer with reference {employer_ref!r}.",
                )
            account = build_account_response(detail, query)
            if not account.risk.eligible:
                # No model call at all. An account the risk screen could not
                # assess has too few calls to carry a reading: its counts are
                # true and already on the tiles, and a sentence restating one
                # is worth neither the wait nor the spend. Most of the book
                # lands here at this corpus's volume, which is the point.
                #
                # The threshold is metric 10's own eligibility floor rather
                # than a number invented here.
                return GeneratedInsightsResponse.of(
                    GeneratedInsights.unavailable(UnavailableReason.NOT_ASSESSABLE)
                )
            facts = account_facts(account)
            # Two, not four. An account offers fewer figures than the exec
            # page and most of its counts are already on tiles, so a longer
            # list is padding by construction.
            per_screen_limit = min(per_screen_limit, ACCOUNT_INSIGHTS)
        case "hierarchy":
            facts = hierarchy_facts(await hierarchy_use_case.execute(query.to_request()))
        case "agents":
            facts = agents_facts(await agents_use_case.execute(query.to_request()))
        case "risk":
            # `RiskQuery()` with nothing set, deliberately: its two filters
            # select rows, and the figures below are computed over every
            # eligible employer regardless (D12). Passing the reader's row
            # filter would not change one of these numbers.
            risk = await risk_use_case.execute(query.to_request())
            facts = risk_facts(build_risk_response(risk, query, RiskQuery()))

    generated = await use_case.execute(
        GenerateInsightsRequest(facts=facts, limit=per_screen_limit), provider
    )
    # The same fact set the model was given, so a card's evidence is the
    # figures its sentence read rather than a list of their names.
    return GeneratedInsightsResponse.of(generated, facts)
