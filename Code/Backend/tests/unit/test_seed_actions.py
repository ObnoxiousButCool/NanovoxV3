"""Seeding the action board from the corpus's own findings (Revised plan
Phase 4).

Two claims worth pinning: a seeded action's workflow fields are empty
(D6) — nothing invented, unlike the prototype's `WF[n % len(WF)]` fixture —
and seeding is idempotent: a key already present is skipped, never
recreated.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from application.ports.action_repository import ActionRepository, NewAction
from application.ports.clock import Clock
from application.ports.insights_source import CorpusQuery, CorpusSlice, InsightsSource
from application.ports.reference_lookup import ReferenceLookup
from application.use_cases.manage_actions import CreateAction
from application.use_cases.read_insights import InsightsReader
from application.use_cases.seed_actions import SeedActions
from domain.actions import Action, Priority
from domain.dashboard_config import (
    BrokerPatternTest,
    DashboardConfig,
    IndicatorGates,
    MetricThreshold,
    PeerSizeBand,
    QualityBands,
    RiskFlagConfig,
)
from domain.entities.agent import Agent
from domain.entities.broker import Broker
from domain.entities.employer import Employer
from domain.entities.employer_contact import EmployerContact
from domain.entities.member import Member
from domain.entities.rule import Rule
from domain.entities.touchpoint import Touchpoint
from domain.playbooks import PlaybookCatalogue
from domain.value_objects.signal_type import SignalType
from infrastructure.config.action_lifecycle_loader import load_action_lifecycle
from infrastructure.config.paths import DEFAULT_CONFIG_DIR
from infrastructure.config.playbook_loader import load_playbooks
from tests.fixtures.tagged_calls import call, day

_NOW = datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc)


class _FixedClock(Clock):
    def now(self) -> datetime:
        return _NOW


class _EmptyReferenceLookup(ReferenceLookup):
    async def find_agent(self, reference: str) -> Agent | None:
        raise NotImplementedError

    async def find_member(self, reference: str) -> Member | None:
        raise NotImplementedError

    async def find_employer_contact(self, reference: str) -> EmployerContact | None:
        raise NotImplementedError

    async def find_employer(self, reference: str) -> Employer | None:
        raise NotImplementedError

    async def list_brokers(self) -> tuple[Broker, ...]:
        raise NotImplementedError

    async def list_rules(self) -> tuple[Rule, ...]:
        raise NotImplementedError

    async def list_touchpoints(self) -> tuple[Touchpoint, ...]:
        return ()


class _FakeActionRepository(ActionRepository):
    def __init__(self) -> None:
        self._rows: dict[int, Action] = {}
        self._seed_keys_by_id: dict[int, str] = {}
        self._next_id = 1

    async def create(self, action: NewAction) -> Action:
        action_id = self._next_id
        self._next_id += 1
        created = Action(
            id=action_id,
            title=action.title,
            source_kind=action.source_kind,
            source_detail=action.source_detail,
            issue_key=action.issue_key,
            evidence=action.evidence,
            recommendation=action.recommendation,
            owner_team=action.owner_team,
            owner=action.owner,
            priority=action.priority,
            status=action.status,
            employer_ref=action.employer_ref,
            broker_ref=action.broker_ref,
            call_references=action.call_references,
            steps=action.steps,
            log=action.log,
            created_at=action.created_at,
            assigned_on=action.assigned_on,
            due=action.due,
        )
        self._rows[action_id] = created
        if action.seed_key is not None:
            self._seed_keys_by_id[action_id] = action.seed_key
        return created

    async def get(self, action_id: int) -> Action | None:
        return self._rows.get(action_id)

    async def list(self) -> tuple[Action, ...]:
        return tuple(self._rows.values())

    async def save(self, action: Action) -> None:
        raise NotImplementedError

    async def seed_keys(self) -> frozenset[str]:
        return frozenset(self._seed_keys_by_id.values())


class _FakeInsightsSource(InsightsSource):
    def __init__(self, corpus: CorpusSlice) -> None:
        self._corpus = corpus

    async def load(self, query: CorpusQuery) -> CorpusSlice:
        return self._corpus


def _config() -> DashboardConfig:
    return DashboardConfig(
        version="1.0.0",
        metrics=(
            MetricThreshold(
                key="control_exception_rate",
                sheet_row="7",
                name="Control exception rate",
                window_weeks=12,
                min_n=30,
                counts="calls",
            ),
        ),
        cost_per_call=None,
        peer_size_bands=(PeerSizeBand(label="2-24 lives", min_lives=2, max_lives=24),),
        broker_ranking_floor_lives=150,
        broker_pattern_test=BrokerPatternTest(
            min_adverse_mentions=3, min_distinct_employers=2, window_weeks=12
        ),
        quality_bands=QualityBands(good_min=86, average_min=60),
        risk_flag=RiskFlagConfig(eligibility_min_calls=3, flag_threshold=2, quote_min_calls=10),
        indicators=IndicatorGates(min_employer_calls=5, min_calls=2, min_rate=0.2),
    )


@pytest.fixture(scope="module")
def catalogue() -> PlaybookCatalogue:
    return load_playbooks(DEFAULT_CONFIG_DIR / "playbooks.yaml")


def _seed_actions(
    corpus: CorpusSlice, *, catalogue: PlaybookCatalogue, actions: ActionRepository | None = None
) -> tuple[SeedActions, ActionRepository]:
    repository = actions or _FakeActionRepository()
    reader = InsightsReader(
        source=_FakeInsightsSource(corpus), config=_config(), clock=_FixedClock()
    )
    create_action = CreateAction(
        actions=repository,
        lifecycle=load_action_lifecycle(DEFAULT_CONFIG_DIR / "action_lifecycle.yaml"),
        catalogue=catalogue,
        reference_lookup=_EmptyReferenceLookup(),
        clock=_FixedClock(),
    )
    use_case = SeedActions(
        reader=reader, actions=repository, create_action=create_action, catalogue=catalogue
    )
    return use_case, repository


async def test_a_seeded_action_carries_no_workflow_state(catalogue: PlaybookCatalogue) -> None:
    """D6: nothing invented — unlike the prototype's WF fixture cycle."""
    corpus = CorpusSlice(
        calls=(call("C-0001", signals=frozenset({SignalType.BILLING_DEFECT})),),
        available_from=day(0),
        available_until=day(0),
    )
    use_case, _ = _seed_actions(corpus, catalogue=catalogue)

    report = await use_case.execute()

    assert len(report.created) == 1
    (action,) = report.created
    assert action.owner is None
    assert action.due is None
    assert action.assigned_on is None
    assert action.action_taken is None
    assert action.outcome is None
    assert action.measurement is None


async def test_the_issue_key_and_owner_team_come_from_the_taxonomy(
    catalogue: PlaybookCatalogue,
) -> None:
    corpus = CorpusSlice(
        calls=(call("C-0001", signals=frozenset({SignalType.COMPLIANCE_DISCLOSURE_MISSING})),),
        available_from=day(0),
        available_until=day(0),
    )
    use_case, _ = _seed_actions(corpus, catalogue=catalogue)

    report = await use_case.execute()

    (action,) = report.created
    assert action.issue_key == "sig_compliance_disclosure_missing"
    assert action.owner_team == "Compliance"
    assert action.call_references == ("C-0001",)


@pytest.mark.parametrize(
    ("signal", "expected"),
    [
        (SignalType.VERIFICATION_FAILURE, Priority.HIGH),  # CRITICAL
        (SignalType.RETENTION_RISK, Priority.HIGH),  # CRITICAL
        (SignalType.COMPLIANCE_DISCLOSURE_MISSING, Priority.HIGH),  # HIGH
        (SignalType.KNOWLEDGE_ERROR, Priority.MEDIUM),  # MEDIUM
        (SignalType.REVENUE_OPPORTUNITY, Priority.LOW),  # LOW
    ],
)
async def test_priority_comes_from_signal_severity_not_the_playbook_default(
    catalogue: PlaybookCatalogue, signal: SignalType, expected: Priority
) -> None:
    """Every dynamic key's own PlaybookSeverity is MEDIUM — seeding must not
    flatten every signal to that one priority."""
    corpus = CorpusSlice(
        calls=(call("C-0001", signals=frozenset({signal})),),
        available_from=day(0),
        available_until=day(0),
    )
    use_case, _ = _seed_actions(corpus, catalogue=catalogue)

    report = await use_case.execute()

    (action,) = report.created
    assert action.priority is expected


async def test_an_already_seeded_key_is_skipped_not_duplicated(
    catalogue: PlaybookCatalogue,
) -> None:
    corpus = CorpusSlice(
        calls=(call("C-0001", signals=frozenset({SignalType.BILLING_DEFECT})),),
        available_from=day(0),
        available_until=day(0),
    )
    repository = _FakeActionRepository()
    use_case, _ = _seed_actions(corpus, catalogue=catalogue, actions=repository)

    first = await use_case.execute()
    second = await use_case.execute()

    assert len(first.created) == 1 and first.skipped == ()
    assert second.created == () and second.skipped == ("sig_billing_defect",)
    assert len(await repository.list()) == 1


async def test_one_item_per_signal_type_across_the_whole_corpus(
    catalogue: PlaybookCatalogue,
) -> None:
    """Coarser than the prototype's per-touchpoint/per-rule grouping — one
    action per signal type, the same grouping the read-only endpoint shows."""
    corpus = CorpusSlice(
        calls=(
            call("C-0001", signals=frozenset({SignalType.BILLING_DEFECT})),
            call("C-0002", signals=frozenset({SignalType.BILLING_DEFECT})),
            call("C-0003", signals=frozenset({SignalType.NETWORK_ADEQUACY})),
        ),
        available_from=day(0),
        available_until=day(0),
    )
    use_case, _ = _seed_actions(corpus, catalogue=catalogue)

    report = await use_case.execute()

    assert report.found == 2
    assert len(report.created) == 2
    billing = next(a for a in report.created if a.issue_key == "sig_billing_defect")
    assert billing.call_references == ("C-0001", "C-0002")


async def test_no_dated_calls_means_nothing_to_seed(catalogue: PlaybookCatalogue) -> None:
    corpus = CorpusSlice(calls=(), available_from=None, available_until=None)
    use_case, _ = _seed_actions(corpus, catalogue=catalogue)

    report = await use_case.execute()

    assert report.found == 0
    assert report.created == ()
    assert report.skipped == ()


async def test_the_window_spans_the_whole_corpus_not_a_recent_slice(
    catalogue: PlaybookCatalogue,
) -> None:
    """Unlike the read side's rolling metric window, seeding must not drop
    an old call — a historical corpus is mostly older than any few-week
    window anchored on today."""
    old_day = date(2020, 1, 1)
    corpus = CorpusSlice(
        calls=(call("C-0001", on=old_day, signals=frozenset({SignalType.BILLING_DEFECT})),),
        available_from=old_day,
        available_until=old_day,
    )
    use_case, _ = _seed_actions(corpus, catalogue=catalogue)

    report = await use_case.execute()

    assert len(report.created) == 1
