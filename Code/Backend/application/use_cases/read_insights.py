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
from domain.aggregation.broker_friction import BrokerFriction, ranked_book_friction
from domain.aggregation.call_tags import Window
from domain.aggregation.contact_rate import PeerComparison, employer_contact_rate, peer_comparison
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


@dataclass(frozen=True)
class InsightsRequest:
    """What a screen asks for: a scope, a slice of it, and a date."""

    filters: InsightFilters
    #: Empty means every transcript origin. See `CorpusQuery.sources`.
    sources: frozenset[CallSource] = frozenset()
    #: The date every window ends on. `None` means today, resolved from the
    #: clock and reported back, never left implicit.
    as_of: date | None = None


@dataclass(frozen=True)
class ScopedCorpus:
    """The population a screen's figures rest on, with its own accounting."""

    corpus: CorpusSlice
    filtered: FilteredCalls
    as_of: date


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
        corpus = await self._source.load(CorpusQuery(sources=request.sources))
        filtered = request.filters.apply(
            corpus.calls,
            employers=corpus.employers,
            quality_bands=self._config.quality_bands,
        )
        as_of = request.as_of or self._clock.now().date()
        return ScopedCorpus(corpus=corpus, filtered=filtered, as_of=as_of)


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
