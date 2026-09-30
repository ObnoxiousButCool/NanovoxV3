"""`GET /api/v1/insights/exec` — the executive scorecard.

## Why every figure states its own window

The Metrics sheet gives each metric its own `window_weeks`, and this one
screen spans two: first contact resolution and knowledge failure rate look
back four weeks, escalation integrity and commercial intent twelve. So the
response cannot carry a single period next to a row of figures — it would
be right about three of them and wrong about two, and nothing on the wire
would say which.

Each metric therefore arrives as its own entry carrying `key`, the sheet's
own `name`, its `window_weeks`, and the figure. `as_of` is the one date
they share: every window ends there.

## Escalation is a pair and stays a pair

`escalation_integrity_pair` returns both views with their labels because
which is which is a definition, not a presentation choice. Handled over
warranted is the control measure; warranted over all calls is the scale it
rests on. A client that took the first alone would publish a number that
reads as good news at exactly the moment it is worst, so they travel
together in one field rather than as two entries a client can pick between.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import Field

from application.use_cases.read_insights import ExecResult, ExecTrends
from domain.aggregation.exec_scorecard import SCORECARD_METRICS, escalation_integrity_pair
from domain.aggregation.patterns import window_for
from domain.dashboard_config import DashboardConfig
from domain.value_objects.product_line import ProductLine
from domain.value_objects.signal_type import SignalType
from frameworks_drivers.api.camel import CamelModel
from frameworks_drivers.api.dependencies import DashboardConfigDep, GetExecScorecardDep
from frameworks_drivers.api.v1.insights.envelope import FigureResponse, ScopeResponse
from frameworks_drivers.api.v1.insights.labels import coded, touchpoint_label
from frameworks_drivers.api.v1.insights.query import InsightsQuery, InsightsQueryDep

router = APIRouter(prefix="/insights", tags=["insights"])


class MetricFigureResponse(CamelModel):
    """One published metric, with the window it was computed over."""

    key: str = Field(description="The metric's key in dashboard.yaml.")
    name: str = Field(description="The Metrics sheet's own name for it.")
    window_weeks: int | None = Field(
        default=None,
        description=(
            "How far back this metric looks from `as_of`. Metrics on one screen "
            "differ; null means the metric is not windowed at all."
        ),
    )
    figure: FigureResponse


class LabelledFigureResponse(CamelModel):
    label: str
    figure: FigureResponse


class WeekResponse(CamelModel):
    """One week of the movement window."""

    start: str
    end: str
    #: Calls that week, or **null** where the corpus has none at all. Null is
    #: not zero: a silent week is an absence of evidence, and a chart draws it
    #: as a gap rather than a point on the baseline.
    calls: int | None


class MovementResponse(CamelModel):
    """One measure's change, and whether the change means anything.

    `beyondNoise` is the only field a screen should branch on. `now` and
    `prior` alone will differ almost every period, and reporting every
    difference is how a reader learns to ignore the screen.
    """

    label: str
    now: int
    prior: int
    calls_now: int = Field(
        description="Calls in the later window, the volume `expected` scales by."
    )
    calls_prior: int
    expected: float = Field(
        description=(
            "What the later window would have shown if nothing changed except how "
            "many calls came in."
        )
    )
    z: float = Field(description="Standard deviations from `expected`.")
    beyond_noise: bool = Field(
        description="Whether the move exceeds what call volume explains. Branch on this."
    )
    worse: bool = Field(
        description=(
            "Whether the move is in the bad direction for this measure. Direction is "
            "not meaning: unresolved rising is bad, resolved rising is good."
        )
    )


class BucketResponse(CamelModel):
    start: str
    end: str
    calls: int = Field(description="Calls in the slice, which `hits` is not a share of.")
    hits: int


class EmergingResponse(CamelModel):
    """One value of some attribute, counted across equal slices.

    Counts, never shares. At about eight calls a week a share would be two or
    three calls, so a percentage would imply precision the corpus cannot
    support.

    For a multi-valued attribute — a call may raise several signals — the
    hits across keys sum to more than the calls in the slice. That is why
    each bucket reports `calls` beside `hits` instead of leaving a reader to
    treat the two as comparable.
    """

    kind: str = Field(description="category | touchpoint | signal | product_line")
    key: str
    label: str = Field(
        description=(
            "The words for `key`. Categories arrive from the workbook as prose "
            "already; touchpoints, signals and product lines are coded values "
            "and this is what `labels.py` says a reader should see for them."
        )
    )
    buckets: list[BucketResponse]
    delta: int = Field(description="Latest slice minus earliest.")
    rising: bool


class CategoryConcernResponse(CamelModel):
    """The call topic carrying the most unresolved calls this period, and how
    its escalations fared there.

    "Area of concern"'s one figure `trends.movements` cannot already answer:
    a movement is one measure across every call, and this is the same two
    measures broken out by the category driving them. `None` when no
    category had an unresolved call — not a gap, the absence of a finding.
    """

    category: str
    calls: int
    unresolved: int
    escalations_triggered: int
    escalations_handled: int


class TrendsResponse(CamelModel):
    """Movement and emerging issues, over the same filtered calls as the scorecard.

    Deliberately separate from `metrics`. Those are the Metrics sheet's own
    figures, each gated on its own min n. This is a reading of movement
    across windows, which the sheet does not define — so it is ours, and the
    response keeps the two apart rather than presenting them as one list.
    """

    window_weeks: int = Field(
        description=(
            "Length of the movement window, and of the equal-length window before it "
            "that it is compared against. No workbook defines this; see MOVEMENT_WEEKS."
        )
    )
    window_start: str
    window_end: str
    prior_start: str
    prior_end: str
    weeks: list[WeekResponse]
    movements: list[MovementResponse]
    emerging: list[EmergingResponse]


class ExecScorecardResponse(CamelModel):
    scope: ScopeResponse
    as_of: str = Field(description="The date every window on this screen ends on.")
    calls: int = Field(
        description=(
            "Calls in the longest window on the screen, which contains every other. "
            "Never the sample behind any one figure — read that figure's own `n`."
        )
    )
    metrics: list[MetricFigureResponse]
    escalation: list[LabelledFigureResponse] = Field(
        description=(
            "Both escalation views, in reading order. Handled over warranted is the "
            "control measure; warranted over all calls is its scale. Shown together "
            "because either alone misleads."
        )
    )
    trends: TrendsResponse = Field(
        description=(
            "What moved since the equal-length window before, and what is emerging. "
            "Separate from `metrics` because these are not the Metrics sheet's figures."
        )
    )
    intent_routed: FigureResponse = Field(
        description=(
            "Always withheld on v9 data: whether commercial intent reached anyone who "
            "could act on it is not a field. Zero would claim we checked."
        )
    )
    area_of_concern: CategoryConcernResponse | None = Field(
        default=None,
        description=(
            "The category with the most unresolved calls this period, and how its "
            "escalations fared. Null when no category had an unresolved call."
        ),
    )


@router.get(
    "/exec",
    response_model=ExecScorecardResponse,
    status_code=status.HTTP_200_OK,
    summary="The executive scorecard",
)
async def read_exec_scorecard(
    use_case: GetExecScorecardDep,
    config: DashboardConfigDep,
    query: InsightsQueryDep,
) -> ExecScorecardResponse:
    result = await use_case.execute(query.to_request())
    return build_exec_response(result, config, query)


def build_exec_response(
    result: ExecResult,
    config: DashboardConfig,
    query: InsightsQuery,
) -> ExecScorecardResponse:
    """The scorecard on the wire.

    Extracted from the route so the insight surface can read the *same*
    response this screen renders. `/insights/generated` must not recompute
    the figures its sentences describe: two builders that agree today are
    two builders, and the day they disagree the model will be quoting a
    number no reader can see.
    """
    card = result.scorecard
    figures = {
        "first_contact_resolution": card.first_contact_resolution,
        "failure_driven_repeat_rate": card.failure_driven_repeat_rate,
        "escalation_integrity": card.escalation_integrity,
        "knowledge_failure_rate": card.knowledge_failure_rate,
        "commercial_intent_capture": card.commercial_intent_capture,
    }
    return ExecScorecardResponse(
        scope=ScopeResponse.of(
            result.scope.corpus,
            result.scope.filtered,
            query.corpus_query(),
            # One caveat per metric, because the windows differ on this one
            # screen: first-contact resolution is 4 weeks and the repeat rate
            # is 12. A single scope-level sentence would have to speak for
            # both, and would be wrong about one of them.
            windows=[
                (config.metric(key).name, window)
                for key in SCORECARD_METRICS
                if (window := window_for(config.metric(key), card.as_of)) is not None
            ],
        ),
        as_of=card.as_of.isoformat(),
        calls=card.calls,
        metrics=[
            MetricFigureResponse(
                key=key,
                name=config.metric(key).name,
                window_weeks=config.metric(key).window_weeks,
                figure=FigureResponse.of(figures[key]),
            )
            for key in SCORECARD_METRICS
        ],
        escalation=[
            LabelledFigureResponse(label=label, figure=FigureResponse.of(figure))
            for label, figure in escalation_integrity_pair(card)
        ],
        trends=_trends(result.trends),
        intent_routed=FigureResponse.of(card.intent_routed),
        area_of_concern=(
            CategoryConcernResponse(
                category=result.area_of_concern.category,
                calls=result.area_of_concern.calls,
                unresolved=result.area_of_concern.unresolved,
                escalations_triggered=result.area_of_concern.escalations_triggered,
                escalations_handled=result.area_of_concern.escalations_handled,
            )
            if result.area_of_concern is not None
            else None
        ),
    )


def _trends(trends: ExecTrends) -> TrendsResponse:
    """Map the domain's trends onto the wire, dates as ISO strings."""
    return TrendsResponse(
        window_weeks=round(trends.window.weeks),
        window_start=trends.window.start.isoformat(),
        window_end=trends.window.end.isoformat(),
        prior_start=trends.prior.start.isoformat(),
        prior_end=trends.prior.end.isoformat(),
        weeks=[
            WeekResponse(
                start=week.start.isoformat(),
                end=week.end.isoformat(),
                calls=calls,
            )
            # `weeks` and `weekly_calls` are produced by the same walk over
            # the window, so they are the same length by construction. `strict`
            # says so rather than trusting it: a silent mismatch would shift
            # every value onto the wrong week.
            for week, calls in zip(trends.weeks, trends.weekly_calls, strict=True)
        ],
        movements=[
            MovementResponse(
                label=move.label,
                now=move.now,
                prior=move.prior,
                calls_now=move.calls_now,
                calls_prior=move.calls_prior,
                expected=round(move.expected, 2),
                z=round(move.z, 2),
                beyond_noise=move.beyond_noise,
                worse=move.worse,
            )
            for move in trends.movements
        ],
        emerging=[
            EmergingResponse(
                kind=row.kind,
                key=row.key,
                label=_emerging_label(row.kind, row.key),
                buckets=[
                    BucketResponse(
                        start=bucket.window.start.isoformat(),
                        end=bucket.window.end.isoformat(),
                        calls=bucket.calls,
                        hits=bucket.hits,
                    )
                    for bucket in row.buckets
                ],
                delta=row.delta,
                rising=row.rising,
            )
            for row in trends.emerging
        ],
    )


def _emerging_label(kind: str, key: str) -> str:
    """Words for an emerging row's `key`, by which of the four kinds it is.

    Categories are already the workbook's own prose (`Category`'s docstring
    in `labels.py`), so they pass through unchanged. Touchpoints, signals
    and product lines are coded values, and this is the one place `kind`
    decides which map reads them — `_touchpoint_keys` etc. in
    `read_insights.py` is where each kind's raw key comes from.
    """
    if kind == "touchpoint":
        return touchpoint_label(key)
    if kind == "signal":
        return coded(SignalType(key)).label
    if kind == "product_line":
        return coded(ProductLine(key)).label
    return key
