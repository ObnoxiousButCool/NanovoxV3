"""`/insights/rules` and `/insights/agents`.

The claims worth pinning: a rule row carries counts and no rate, rules
nobody got wrong are still listed, the agent score range states that it
cannot rank, and metric 12's absent window is reported as null rather than
filled in with someone else's.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.value_objects.call_source import CallSource
from domain.value_objects.category import Category
from domain.value_objects.outcome import Outcome
from domain.value_objects.signal_type import SignalType
from infrastructure.persistence.tables import (
    BrokerRow,
    CallExtractionRow,
    CallRow,
    RuleRow,
    SignalRow,
)
from tests.integration.test_insights_endpoints import AS_OF, _employer

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

pytestmark = pytest.mark.asyncio


async def seed(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    failed_rules: list[str | None],
    signals: list[list[SignalType]] | None = None,
    scores: list[int | None] | None = None,
    agent_refs: list[str] | None = None,
) -> None:
    """One call per entry in `failed_rules`, plus the published rulebook."""
    async with session_factory() as session, session.begin():
        broker = BrokerRow(
            reference="BRK-01",
            name="Broker",
            agency="Agency",
            region="West",
            groups_in_book=4,
            signal_profile="neutral",
        )
        session.add(broker)
        await session.flush()
        employer = _employer("EMP-01", broker.id)
        session.add(employer)
        await session.flush()

        for reference, area in (("P-14", "Eligibility"), ("A-09", "Billing")):
            session.add(
                RuleRow(
                    reference=reference,
                    layer=reference[0],
                    area=area,
                    text="...",
                    commonly_confused_with=f"not-{reference}",
                    source="Program doc",
                    confidence="VERIFIED",
                )
            )

        for index, rule_id in enumerate(failed_rules, start=1):
            call = CallRow(
                reference=f"C-{index:04d}",
                source=CallSource.CORPUS_PDF.value,
                occurred_at=datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc),
                aht_seconds=300,
                caller_type="MEMBER",
                caller_ref="MEM-1",
                agent_ref=(agent_refs or ["AG-01"] * len(failed_rules))[index - 1],
                agent_name="Alex",
                resolution_status="RESOLVED",
                employer_id=employer.id,
            )
            session.add(call)
            await session.flush()
            session.add(
                CallExtractionRow(
                    call_id=call.id,
                    outcome=Outcome.RESOLVED.value,
                    category=Category.CLAIMS_AND_EOB.value,
                    complaint_present=False,
                    escalation_triggered=False,
                    knowledge_failure_present=rule_id is not None,
                    knowledge_failure_rule_id=rule_id,
                    touchpoint="Enrolment" if rule_id else None,
                    quality_score=(scores or [None] * len(failed_rules))[index - 1],
                    control_exceptions=[],
                )
            )
            for signal in (signals or [[]] * len(failed_rules))[index - 1]:
                session.add(SignalRow(call_id=call.id, type=signal.value, quote="q", turn_seq=1))


class TestRules:
    async def test_a_rule_row_carries_counts_and_no_rate(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Per-rule rates need a denominator nothing records."""
        await seed(session_factory, failed_rules=["P-14", "P-14", None])

        body = client.get("/api/v1/insights/rules", params={"as_of": AS_OF}).json()

        top = body["rules"][0]
        assert top["rule_ref"] == "P-14"
        assert top["failures"] == 2
        assert top["failed_call_ids"] == ["C-0001", "C-0002"]
        assert "rate" not in top

    async def test_rules_nobody_got_wrong_are_still_listed(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """A rule with no failures is not a rule that does not exist."""
        await seed(session_factory, failed_rules=["P-14"])

        body = client.get("/api/v1/insights/rules", params={"as_of": AS_OF}).json()

        assert {row["rule_ref"] for row in body["rules"]} == {"P-14", "A-09"}
        assert next(r for r in body["rules"] if r["rule_ref"] == "A-09")["failures"] == 0

    async def test_the_confused_with_column_reaches_the_screen(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(session_factory, failed_rules=["P-14"])

        body = client.get("/api/v1/insights/rules", params={"as_of": AS_OF}).json()

        assert body["rules"][0]["commonly_confused_with"] == "not-P-14"

    async def test_the_only_rate_is_about_the_corpus(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(session_factory, failed_rules=["P-14", None])

        body = client.get("/api/v1/insights/rules", params={"as_of": AS_OF}).json()

        assert "overall_rate" in body
        assert body["overall_rate"]["n"] == 2

    async def test_the_cuts_add_up_to_the_same_failures(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(session_factory, failed_rules=["P-14", "A-09"])

        body = client.get("/api/v1/insights/rules", params={"as_of": AS_OF}).json()

        assert sum(row["failures"] for row in body["by_layer"]) == 2
        assert sum(row["failures"] for row in body["by_provenance"]) == 2
        assert sum(row["failures"] for row in body["by_touchpoint"]) == 2


class TestAgents:
    async def test_events_lead_and_the_score_range_sits_beside_them(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(
            session_factory,
            failed_rules=[None, None],
            signals=[[SignalType.KNOWLEDGE_ERROR], []],
            scores=[90, 70],
        )

        body = client.get("/api/v1/insights/agents", params={"as_of": AS_OF}).json()

        (agent,) = body["agents"]
        assert agent["agent_ref"] == "AG-01"
        assert agent["knowledge_errors"] == ["C-0001"]
        assert agent["quality"]["median_score"] == 80

    async def test_the_score_range_says_it_cannot_rank(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(session_factory, failed_rules=[None], scores=[90])

        body = client.get("/api/v1/insights/agents", params={"as_of": AS_OF}).json()

        assert "cannot separate one" in body["agents"][0]["quality"]["caveat"]

    async def test_an_unscored_agent_has_a_null_median_not_a_zero(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(session_factory, failed_rules=[None], scores=[None])

        body = client.get("/api/v1/insights/agents", params={"as_of": AS_OF}).json()

        quality = body["agents"][0]["quality"]
        assert quality["median_score"] is None
        assert "No scored call" in quality["caveat"]

    async def test_metric_twelve_reports_no_window_rather_than_borrowing_one(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """A score is a property of the call, not of a period."""
        await seed(session_factory, failed_rules=[None], scores=[90])

        body = client.get("/api/v1/insights/agents", params={"as_of": AS_OF}).json()

        assert body["quality_window_weeks"] is None
        assert body["window_weeks"] == 4

    async def test_one_entry_per_agent_with_calls(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(
            session_factory,
            failed_rules=[None, None, None],
            agent_refs=["AG-01", "AG-02", "AG-01"],
        )

        body = client.get("/api/v1/insights/agents", params={"as_of": AS_OF}).json()

        assert [agent["agent_ref"] for agent in body["agents"]] == ["AG-01", "AG-02"]
        assert len(body["agents"][0]["calls"]) == 2
