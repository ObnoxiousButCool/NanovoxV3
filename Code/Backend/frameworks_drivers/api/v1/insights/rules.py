"""`GET /api/v1/insights/rules` — rules we fail to explain.

## Counts, and exactly one rate

§9 insight 23 forbids a per-rule rate, and the reason is a missing
denominator rather than a stylistic preference: the divisor would have to be
"calls where this rule was relevant", and nothing in v9 records that. So a
rule row carries a count of calls that got it wrong and the references
behind them, and no rate at all.

`overall_rate` is metric 8 and is about the corpus, not about any rule:
calls carrying a knowledge failure over all calls. It is the one rate this
screen publishes, and it is gated like any other figure.

## Never labelled an agent error

Decision D7 is open with Karim. The workbook contradicts itself — a call can
be RESOLVED, score 91, and still carry a knowledge failure — so the tag is
reported as the schema defines it, rolled up by rule id and by touchpoint,
and nothing here calls it a mistake by the agent. The separate
`knowledge_error` signal is the agent-conduct event, and it lives on the
agents screen.

## Rules with no failures are still listed

The rewrite list ranks over the whole rulebook. A rule nobody got wrong is a
different thing from a rule that does not exist, and a screen that showed
only cited rules could not tell a reader which they were looking at.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import Field

from frameworks_drivers.api.camel import CamelModel
from frameworks_drivers.api.dependencies import GetRulesDep
from frameworks_drivers.api.v1.insights.envelope import FigureResponse, ScopeResponse
from frameworks_drivers.api.v1.insights.labels import CodedValue, coded
from frameworks_drivers.api.v1.insights.query import InsightsQueryDep

router = APIRouter(prefix="/insights", tags=["insights"])


class RuleRowResponse(CamelModel):
    """One rule and the calls that got it wrong. No rate — see the module docstring."""

    rule_ref: str
    layer: CodedValue = Field(
        description="Program, Administration or Carrier — whose rulebook it is."
    )
    area: str
    confidence: CodedValue = Field(
        description=(
            "The rule's own provenance grade from the Rules sheets. Provenance of the "
            "rule, not of any figure about it, and not an epistemic class."
        )
    )
    commonly_confused_with: str = Field(
        default="",
        description="The Rules sheets' own column — what people mistake this rule for.",
    )
    failures: int
    failed_call_ids: list[str]


class CountResponse(CamelModel):
    """One cut of the failures. `value` carries its own label where the
    thing being counted is a coded value rather than free text."""

    value: CodedValue
    failures: int


class RulesResponse(CamelModel):
    scope: ScopeResponse
    as_of: str
    window_weeks: int
    overall_rate: FigureResponse = Field(
        description=(
            "Metric 8: calls carrying a knowledge failure, over all calls. About the "
            "corpus, never about one rule."
        )
    )
    rules: list[RuleRowResponse] = Field(
        description="The rewrite list, worst first. Every rule, including those with no failures."
    )
    by_layer: list[CountResponse] = Field(description="Whose rulebook is the problem.")
    by_area: list[CountResponse]
    by_provenance: list[CountResponse] = Field(
        description=(
            "A misstated UNVERIFIED rule says our source is weak; a misstated VERIFIED "
            "one says our training is."
        )
    )
    by_touchpoint: list[CountResponse] = Field(
        description="Where the failure originated — the same rule in two documents is two fixes."
    )


@router.get(
    "/rules",
    response_model=RulesResponse,
    status_code=status.HTTP_200_OK,
    summary="Rules we fail to explain, by rule, layer, area, provenance and touchpoint",
)
async def read_rules(
    use_case: GetRulesDep,
    query: InsightsQueryDep,
) -> RulesResponse:
    view = await use_case.execute(query.to_request())
    return RulesResponse(
        scope=ScopeResponse.of(view.scope.corpus, view.scope.filtered, query.corpus_query()),
        as_of=view.scope.as_of.isoformat(),
        window_weeks=round(view.window.weeks),
        overall_rate=FigureResponse.of(view.overall_rate),
        rules=[
            RuleRowResponse(
                rule_ref=row.rule_ref,
                layer=coded(row.layer),
                area=row.area,
                confidence=coded(row.confidence),
                commonly_confused_with=row.commonly_confused_with,
                failures=row.failures,
                failed_call_ids=list(row.failed_call_ids),
            )
            for row in view.rules
        ],
        by_layer=[CountResponse(value=coded(layer), failures=n) for layer, n in view.by_layer],
        by_area=[
            CountResponse(value=CodedValue(code=area, label=area), failures=n)
            for area, n in view.by_area
        ],
        by_provenance=[
            CountResponse(value=coded(grade), failures=n) for grade, n in view.by_provenance
        ],
        by_touchpoint=[
            CountResponse(value=CodedValue(code=where, label=where), failures=n)
            for where, n in view.by_touchpoint
        ],
    )
