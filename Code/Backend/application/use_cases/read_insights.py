"""The insights read use cases — the exec scorecard and the risk screen.

Two use cases in one module because they share the step that actually
matters: resolving a request into *the population every figure on the screen
is computed over*. That resolution is three decisions (which sources, which
filters, as at what date), and nine screens making it three ways would be
nine chances for a figure to be right about a population nobody stated.

## What the screens are not allowed to do

`InsightsReader.scope` returns the corpus slice **and** the filter result,
not just the surviving calls. A use case that took only the calls could not
tell its endpoint how many were set aside, or why — and "filters slice,
never hide" is a promise about the response, not about the filtering.

## `as_of` is a request parameter, not a clock read

The domain takes no clock (plan §2A.1), and the scorecard needs a date to
resolve each metric's window from. A caller may supply one; when it does
not, the clock resolves it *here*, at the application boundary, and the
resolved date travels out in the response. A screen that asked for "now"
and a screen that asked for a fixed date then produce the same answer for
the same date, which is what makes a reported figure reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from application.ports.insights_source import CorpusQuery
from domain.aggregation.actions import ActionItem, OwnerWorkload, action_items, by_owner
from domain.aggregation.agent_events import (
    CONTROL_DENOMINATOR_CAVEAT,
    AgentEvents,
    AgentQuality,
    agent_events,
    agent_quality,
    control_exception_rates,
)
from domain.aggregation.broker_friction import BrokerFriction, ranked_book_friction
from domain.aggregation.call_tags import Window
from domain.aggregation.contact_rate import PeerComparison, employer_contact_rate, peer_comparison
from domain.aggregation.demand import (
    SelfInflictedDemand,
    complaint_attributed_to_choice,
    self_inflicted_demand,
)
from domain.aggregation.exec_scorecard import ExecScorecard, exec_scorecard
from domain.aggregation.indicators import observe
from domain.aggregation.isolation import (
    RegionNode,
    drill_tree,
    region_category_matrix,
    systemic_categories,
)
from domain.aggregation.patterns import window_for
from domain.aggregation.repeat_contact import failure_driven_repeat_rate
from domain.aggregation.risk_flag import (
    Exposure,
    RiskAssessment,
    assess,
    exposure,
    flagged_share,
)
from domain.aggregation.rules import (
    RuleRow,
    failures_by_area,
    failures_by_layer,
    failures_by_provenance,
    failures_by_rule,
    failures_by_touchpoint,
    knowledge_failure_rate,
)
from domain.aggregation.touchpoints import (
    PromiseGap,
    TouchpointRow,
    enrolment_promise_gaps,
    touchpoint_ranking,
    unattributed_calls,
)
from domain.aggregation.withheld import DID_IT_WORK, WithheldPanel

if TYPE_CHECKING:
    from datetime import date

    from application.ports.clock import Clock
    from application.ports.insights_source import CorpusSlice, InsightsSource
    from domain.aggregation.call_tags import EmployerFacts
    from domain.aggregation.figure import Figure
    from domain.aggregation.filters import FilteredCalls, InsightFilters
    from domain.aggregation.indicators import Observation
    from domain.dashboard_config import DashboardConfig
    from domain.value_objects.call_source import CallSource
    from domain.value_objects.category import Category
    from domain.value_objects.control_exception_type import ControlExceptionType
    from domain.value_objects.rule_confidence import RuleConfidence
    from domain.value_objects.rule_layer import RuleLayer


@dataclass(frozen=True)
class InsightsRequest:
    """What a screen asks for: a scope, a slice of it, and a date."""

    filters: InsightFilters
    #: Empty means every transcript origin. See `CorpusQuery.sources`.
    sources: frozenset[CallSource] = frozenset()
    #: The date every window ends on. `None` means today, resolved from the
    #: clock and reported back, never left implicit.
    as_of: date | None = None
    #: The requested period. It bounds which calls are read; each metric's
    #: own `window_weeks` still applies inside it, anchored on `as_of`
    #: (decision D11). `None` at either end means that end is unbounded.
    since: date | None = None
    until: date | None = None


@dataclass(frozen=True)
class ScopedCorpus:
    """The population a screen's figures rest on, with its own accounting."""

    corpus: CorpusSlice
    filtered: FilteredCalls
    as_of: date
    #: Echoed back so a response can state the period it was asked for, and
    #: so a caveat can name it when a metric's window reaches outside it.
    since: date | None = None
    until: date | None = None


@dataclass(frozen=True)
class ExecResult:
    scope: ScopedCorpus
    scorecard: ExecScorecard


@dataclass(frozen=True)
class AccountRisk:
    """One employer's standing, with the conditions that did not fire too.

    Observations ride along with the assessment rather than being fetched
    separately, because the indicator families are explicitly "other
    conditions observed" *about this account* and are meaningless detached
    from the flag they do not set.
    """

    assessment: RiskAssessment
    observations: tuple[Observation, ...]


@dataclass(frozen=True)
class RiskResult:
    scope: ScopedCorpus
    #: Employers the window gave enough calls to assess. Only these carry
    #: observations: a family that "did not fire" for an account with one
    #: call says nothing, and printing it would imply it did.
    assessed: tuple[AccountRisk, ...]
    #: Employers below the eligibility floor, by reference. Counted and
    #: named rather than folded into "not flagged" — at batch-1 volume most
    #: of the book lands here, and a page that showed 90 unflagged accounts
    #: would be claiming 90 clean bills of health it cannot support.
    ineligible: tuple[str, ...]
    exposure: Exposure
    flagged_share: Figure
    window: Window


class InsightsReader:
    """Resolves a request into the population the figures are computed over."""

    def __init__(self, source: InsightsSource, config: DashboardConfig, clock: Clock) -> None:
        self._source = source
        self._config = config
        self._clock = clock

    async def scope(self, request: InsightsRequest) -> ScopedCorpus:
        corpus = await self._source.load(
            CorpusQuery(
                sources=request.sources,
                since=request.since,
                until=request.until,
            )
        )
        filtered = request.filters.apply(
            corpus.calls,
            employers=corpus.employers,
            quality_bands=self._config.quality_bands,
        )
        as_of = request.as_of or self._clock.now().date()
        return ScopedCorpus(
            corpus=corpus,
            filtered=filtered,
            as_of=as_of,
            since=request.since,
            until=request.until,
        )


class GetExecScorecard:
    def __init__(self, reader: InsightsReader, config: DashboardConfig) -> None:
        self._reader = reader
        self._config = config

    async def execute(self, request: InsightsRequest) -> ExecResult:
        scope = await self._reader.scope(request)
        return ExecResult(
            scope=scope,
            scorecard=exec_scorecard(self._config, scope.filtered.calls, scope.as_of),
        )


class GetAccountRisk:
    def __init__(self, reader: InsightsReader, config: DashboardConfig) -> None:
        self._reader = reader
        self._config = config

    async def execute(self, request: InsightsRequest) -> RiskResult:
        scope = await self._reader.scope(request)
        window = window_for(self._config.metric("account_risk_flag"), scope.as_of)
        if window is None:  # pragma: no cover - the config would have to drop the window
            raise ValueError(
                "The account risk flag is defined over a window and the config gives it none; "
                "a rising complaint rate and a renewal date both need a period."
            )

        calls = scope.filtered.calls
        assessments = tuple(
            assess(self._config, employer, calls, window) for employer in scope.corpus.employers
        )
        assessed = tuple(
            AccountRisk(
                assessment=assessment,
                observations=observe(
                    self._config,
                    employer,
                    calls,
                    window,
                ),
            )
            for assessment, employer in zip(assessments, scope.corpus.employers, strict=True)
            if assessment.eligible
        )
        return RiskResult(
            scope=scope,
            assessed=assessed,
            ineligible=tuple(sorted(a.employer_ref for a in assessments if not a.eligible)),
            exposure=exposure(assessments, scope.corpus.employers),
            flagged_share=flagged_share(self._config, assessments),
            window=window,
        )


@dataclass(frozen=True)
class AccountDetail:
    """One employer's page.

    `contact_rate` and `repeat_rate` come back with the windows they were
    computed over, because metric 1 and metric 4 need not share one and the
    page has to say which period each number describes.
    """

    scope: ScopedCorpus
    employer: EmployerFacts
    contact_rate: Figure
    contact_rate_window: Window
    peers: PeerComparison
    repeat_rate: Figure
    repeat_rate_window: Window
    risk: RiskAssessment
    observations: tuple[Observation, ...]
    risk_window: Window


@dataclass(frozen=True)
class HierarchyView:
    """Region → broker → employer, plus the two readings over it.

    The matrix and the tree are computed over one window on purpose: the
    reading rule §9 gives — "a dark column is book-wide, a dark cell is
    local" — only holds if every cell counts the same period.
    """

    scope: ScopedCorpus
    tree: tuple[RegionNode, ...]
    matrix: tuple[tuple[str, tuple[tuple[Category, int], ...]], ...]
    systemic: tuple[Category, ...]
    #: Only brokers whose book clears the ranking floor. The rest still have
    #: rows on their own account pages; what the floor stops is a
    #: three-group agency topping a league table on one call.
    ranked_brokers: tuple[BrokerFriction, ...]
    window: Window


class GetAccountDetail:
    def __init__(self, reader: InsightsReader, config: DashboardConfig) -> None:
        self._reader = reader
        self._config = config

    async def execute(self, employer_ref: str, request: InsightsRequest) -> AccountDetail | None:
        """`None` when no such employer exists, which is a 404 and not an
        empty account — an account page for a reference nobody recognises
        would invent a business relationship."""
        scope = await self._reader.scope(request)
        employer = next(
            (e for e in scope.corpus.employers if e.reference == employer_ref),
            None,
        )
        if employer is None:
            return None

        calls = scope.filtered.calls
        contact_window = _require(self._config, "contact_rate", scope.as_of)
        repeat_window = _require(self._config, "failure_driven_repeat_rate", scope.as_of)
        risk_window = _require(self._config, "account_risk_flag", scope.as_of)
        mine = [call for call in calls if call.employer_ref == employer_ref]

        return AccountDetail(
            scope=scope,
            employer=employer,
            contact_rate=employer_contact_rate(self._config, employer, calls, contact_window),
            contact_rate_window=contact_window,
            peers=peer_comparison(
                self._config, employer, scope.corpus.employers, calls, contact_window
            ),
            repeat_rate=failure_driven_repeat_rate(
                self._config, repeat_window.calls_in(tuple(mine)), repeat_window
            ),
            repeat_rate_window=repeat_window,
            risk=assess(self._config, employer, calls, risk_window),
            observations=observe(self._config, employer, calls, risk_window),
            risk_window=risk_window,
        )


class GetHierarchy:
    def __init__(self, reader: InsightsReader, config: DashboardConfig) -> None:
        self._reader = reader
        self._config = config

    async def execute(self, request: InsightsRequest) -> HierarchyView:
        scope = await self._reader.scope(request)
        weeks = self._config.broker_pattern_test.window_weeks
        window = Window(scope.as_of - timedelta(weeks=weeks), scope.as_of)

        calls = scope.filtered.calls
        employers = scope.corpus.employers
        matrix = region_category_matrix(employers, calls, window)
        return HierarchyView(
            scope=scope,
            tree=drill_tree(employers, calls, window),
            matrix=matrix,
            systemic=systemic_categories(matrix),
            ranked_brokers=ranked_book_friction(self._config, scope.corpus.brokers, calls, window),
            window=window,
        )


def _require(config: DashboardConfig, key: str, as_of: date) -> Window:
    """A metric's window, insisting it has one.

    Every metric these two screens read is windowed in the Metrics sheet. If
    one stops being, that is a definition change and should surface as an
    error rather than as a figure quietly computed over all of history.
    """
    window = window_for(config.metric(key), as_of)
    if window is None:  # pragma: no cover - the config would have to drop the window
        raise ValueError(
            f"{key} is defined over a window and the config gives it none; "
            "a rate with no period is not the metric the sheet defines."
        )
    return window


@dataclass(frozen=True)
class DemandView:
    """Screen 3 — where the calls come from.

    `self_inflicted` keeps its four figures apart on purpose: the total is
    the share of calls meeting *any* component, over distinct calls, and is
    not the sum of the three. A call can be a repeat and carry a process
    gap, and adding them would count it twice.
    """

    scope: ScopedCorpus
    self_inflicted: SelfInflictedDemand
    #: The complaint-based cut, "stays labelled as a different measure".
    #: How often someone complained about us is related to, but not the
    #: same as, how much of this volume we created.
    complaints_about_us: Figure
    touchpoints: tuple[TouchpointRow, ...]
    #: Insight 18's residual, read off the ranking rather than recomputed so
    #: the two insights cannot report different numbers for one set of calls.
    unattributed: tuple[str, ...]
    promise_gaps: tuple[PromiseGap, ...]
    window: Window


@dataclass(frozen=True)
class ActionsView:
    """Screen 4 — the action centre, read side only.

    No lifecycle: the write path is Phase 9 and decision D6. Items carry
    what the signal says and nothing more, because a default status would
    be a claim no stored record supports.
    """

    scope: ScopedCorpus
    items: tuple[ActionItem, ...]
    owners: tuple[OwnerWorkload, ...]
    #: Metric 7 by exception type, never blended into one compliance rate —
    #: a single number hides which control failed, which is the only part
    #: anyone can fix.
    control_exceptions: tuple[tuple[ControlExceptionType, Figure], ...]
    control_denominator_caveat: str
    #: Insight 22, withheld until a comparable before and after exist.
    did_it_work: WithheldPanel
    window: Window


class GetDemand:
    def __init__(self, reader: InsightsReader, config: DashboardConfig) -> None:
        self._reader = reader
        self._config = config

    async def execute(self, request: InsightsRequest) -> DemandView:
        scope = await self._reader.scope(request)
        window = _require(self._config, "self_inflicted_demand", scope.as_of)
        calls = scope.filtered.calls
        ranking = touchpoint_ranking(calls, window)
        return DemandView(
            scope=scope,
            self_inflicted=self_inflicted_demand(self._config, calls, window),
            complaints_about_us=complaint_attributed_to_choice(self._config, calls, window),
            touchpoints=ranking,
            unattributed=unattributed_calls(ranking),
            promise_gaps=enrolment_promise_gaps(calls, window),
            window=window,
        )


class GetActions:
    def __init__(self, reader: InsightsReader, config: DashboardConfig) -> None:
        self._reader = reader
        self._config = config

    async def execute(self, request: InsightsRequest) -> ActionsView:
        scope = await self._reader.scope(request)
        window = _require(self._config, "control_exception_rate", scope.as_of)
        calls = scope.filtered.calls
        items = action_items(calls, window)
        return ActionsView(
            scope=scope,
            items=items,
            owners=by_owner(items),
            control_exceptions=control_exception_rates(self._config, calls, window),
            control_denominator_caveat=CONTROL_DENOMINATOR_CAVEAT,
            did_it_work=DID_IT_WORK,
            window=window,
        )


@dataclass(frozen=True)
class RulesView:
    """Screen 5 — rules we fail to explain.

    Counts, never a per-rule rate. §9 insight 23 forbids one: the
    denominator would have to be "calls where this rule was relevant", and
    nothing records that. `overall_rate` is the one rate here and it is
    about the corpus, not about any rule.
    """

    scope: ScopedCorpus
    rules: tuple[RuleRow, ...]
    by_layer: tuple[tuple[RuleLayer, int], ...]
    by_area: tuple[tuple[str, int], ...]
    by_provenance: tuple[tuple[RuleConfidence, int], ...]
    by_touchpoint: tuple[tuple[str, int], ...]
    overall_rate: Figure
    window: Window


@dataclass(frozen=True)
class AgentView:
    """One agent's events and score range."""

    events: AgentEvents
    quality: AgentQuality


@dataclass(frozen=True)
class AgentsView:
    """Screen 6 — agent conduct and handling.

    Events, not scores, is the prototype's own framing: the list leads with
    what happened on a call rather than with a number about the agent.
    `quality` is a range with a caveat computed from its own `n`, never a
    ranking — at batch-1 volume no agent has enough scored calls to be
    separated from another.
    """

    scope: ScopedCorpus
    agents: tuple[AgentView, ...]
    window: Window
    #: Null when the quality metric is not windowed, which it is not: a
    #: score is a property of the call, and `agent_quality_score` carries
    #: `window_weeks: null` in the Metrics sheet.
    quality_window_weeks: int | None


class GetRules:
    def __init__(self, reader: InsightsReader, config: DashboardConfig) -> None:
        self._reader = reader
        self._config = config

    async def execute(self, request: InsightsRequest) -> RulesView:
        scope = await self._reader.scope(request)
        window = window_for(self._config.metric("knowledge_failure_rate"), scope.as_of)
        if window is None:  # pragma: no cover - the config would have to drop the window
            raise ValueError(
                "Knowledge failure rate is defined over a window and the config gives "
                "it none; a rate with no period is not the metric the sheet defines."
            )

        calls = scope.filtered.calls
        rows = failures_by_rule(scope.corpus.rules, calls, window)
        return RulesView(
            scope=scope,
            rules=rows,
            by_layer=failures_by_layer(rows),
            by_area=failures_by_area(rows),
            by_provenance=failures_by_provenance(rows),
            by_touchpoint=failures_by_touchpoint(calls, window),
            overall_rate=knowledge_failure_rate(self._config, calls, window),
            window=window,
        )


class GetAgents:
    def __init__(self, reader: InsightsReader, config: DashboardConfig) -> None:
        self._reader = reader
        self._config = config

    async def execute(self, request: InsightsRequest) -> AgentsView:
        scope = await self._reader.scope(request)
        events_window = _events_window(self._config, scope.as_of)
        quality = self._config.metric("agent_quality_score")

        calls = scope.filtered.calls
        refs = sorted({call.agent_ref for call in calls if call.agent_ref is not None})
        return AgentsView(
            scope=scope,
            agents=tuple(
                AgentView(
                    events=agent_events(self._config, ref, calls, events_window),
                    quality=agent_quality(ref, calls, events_window),
                )
                for ref in refs
            ),
            window=events_window,
            quality_window_weeks=quality.window_weeks,
        )


def _events_window(config: DashboardConfig, as_of: date) -> Window:
    """The window the agent *events* are counted over.

    Metric 12 itself is unwindowed — a quality score is a property of the
    call, not of a period — but the events beside it are counts over a
    period and need one. The knowledge failure rate's four weeks is used,
    because the knowledge-error events are the same measure at agent level,
    and the response states it rather than leaving a reader to assume.
    """
    window = window_for(config.metric("knowledge_failure_rate"), as_of)
    if window is None:  # pragma: no cover - the config would have to drop the window
        raise ValueError("Agent events need a period and the config gives none.")
    return window
