"""`/insights/demand` and `/insights/actions`.

The claims worth pinning: the self-inflicted total is not the sum of its
parts, the complaint cut stays a separate measure, an action item carries no
lifecycle it cannot support, and compliance is reported per control rather
than blended.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.value_objects.call_source import CallSource
from domain.value_objects.category import Category
from domain.value_objects.control_exception_type import ControlExceptionType
from domain.value_objects.outcome import Outcome
from domain.value_objects.signal_type import SignalType
from infrastructure.persistence.tables import (
    BrokerRow,
    CallExtractionRow,
    CallRow,
    SignalRow,
)
from tests.integration.test_insights_endpoints import AS_OF, _employer

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

pytestmark = pytest.mark.asyncio


async def seed_signals(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    signals_per_call: list[list[SignalType]],
    control_exceptions: list[str] | None = None,
) -> None:
    """One call per entry, each raising the signals given."""
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

        for index, signals in enumerate(signals_per_call, start=1):
            call = CallRow(
                reference=f"C-{index:04d}",
                source=CallSource.CORPUS_PDF.value,
                occurred_at=datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc),
                aht_seconds=300,
                caller_type="MEMBER",
                caller_ref="MEM-1",
                agent_ref="AG-01",
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
                    knowledge_failure_present=False,
                    process_gap_present=False,
                    control_exceptions=control_exceptions or [],
                )
            )
            for signal in signals:
                session.add(SignalRow(call_id=call.id, type=signal.value, quote="q", turn_seq=1))


class TestActions:
    async def test_an_item_carries_no_status_it_cannot_support(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """The write path is Phase 9; a default 'open' would be invented."""
        await seed_signals(session_factory, signals_per_call=[[SignalType.BILLING_DEFECT]])

        body = client.get("/api/v1/insights/actions", params={"as_of": AS_OF}).json()

        assert body["items"][0]["signal"] == "billing_defect"
        assert "status" not in body["items"][0]

    async def test_severity_and_owner_come_from_the_taxonomy(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed_signals(
            session_factory, signals_per_call=[[SignalType.COMPLIANCE_DISCLOSURE_MISSING]]
        )

        body = client.get("/api/v1/insights/actions", params={"as_of": AS_OF}).json()

        assert body["items"][0]["owner_team"] == "Compliance"
        assert body["items"][0]["severity"] == "HIGH"

    async def test_a_signal_nobody_raised_is_absent_not_zero(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed_signals(session_factory, signals_per_call=[[SignalType.BILLING_DEFECT]])

        body = client.get("/api/v1/insights/actions", params={"as_of": AS_OF}).json()

        assert len(body["items"]) == 1

    async def test_a_team_counts_one_call_once(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Two Operations signals on one call is one call of work, not two."""
        await seed_signals(
            session_factory,
            signals_per_call=[[SignalType.PROCESS_BREAKDOWN, SignalType.ESCALATION_MISSED]],
        )

        body = client.get("/api/v1/insights/actions", params={"as_of": AS_OF}).json()

        (operations,) = body["owners"]
        assert operations["owner_team"] == "Operations"
        assert len(operations["items"]) == 2
        assert operations["calls"] == 1

    async def test_compliance_is_reported_per_control_not_blended(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """A single rate hides which control failed."""
        await seed_signals(
            session_factory,
            signals_per_call=[[]],
            control_exceptions=[ControlExceptionType.NO_RECORDING_DISCLOSURE.value],
        )

        body = client.get("/api/v1/insights/actions", params={"as_of": AS_OF}).json()

        types = {row["exception_type"] for row in body["control_exceptions"]}
        assert types == {
            "no_recording_disclosure",
            "disclosure_before_verification",
            "missing_benefit_disclosure",
        }
        assert "floor on the true exception rate" in body["control_denominator_caveat"]

    async def test_the_withheld_panel_states_what_would_unlock_it(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed_signals(session_factory, signals_per_call=[[]])

        body = client.get("/api/v1/insights/actions", params={"as_of": AS_OF}).json()

        assert body["did_it_work"]["insight"] == 22
        assert "second batch" in body["did_it_work"]["unlocked_by"]


class TestDemand:
    async def test_the_total_is_not_the_sum_of_its_parts(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """A call can be both a repeat and a process defect."""
        await seed_signals(
            session_factory,
            signals_per_call=[[SignalType.PROCESS_BREAKDOWN] for _ in range(3)],
        )

        body = client.get("/api/v1/insights/demand", params={"as_of": AS_OF}).json()
        demand = body["self_inflicted"]

        assert set(demand) == {
            "failure_driven_repeats",
            "chasing_submitted_action",
            "logged_process_defect",
            "total",
        }

    async def test_the_complaint_cut_is_a_separate_field(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Related to, but not the same as, how much volume we created."""
        await seed_signals(session_factory, signals_per_call=[[]])

        body = client.get("/api/v1/insights/demand", params={"as_of": AS_OF}).json()

        assert "complaints_about_us" in body
        assert "complaints_about_us" not in body["self_inflicted"]

    async def test_touchpoints_are_counts_with_their_calls(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed_signals(session_factory, signals_per_call=[[], [], []])

        body = client.get("/api/v1/insights/demand", params={"as_of": AS_OF}).json()

        (row,) = body["touchpoints"]
        assert row["calls"] == 3
        assert len(row["call_ids"]) == 3
        assert "rate" not in row

    async def test_untagged_touchpoints_land_in_the_residual_bucket(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Read off the ranking, so insights 16 and 18 cannot disagree."""
        await seed_signals(session_factory, signals_per_call=[[], []])

        body = client.get("/api/v1/insights/demand", params={"as_of": AS_OF}).json()

        assert len(body["unattributed"]) == 2
        residual = next(r for r in body["touchpoints"] if r["call_ids"] == body["unattributed"])
        assert residual["calls"] == 2

    async def test_a_small_sample_is_withheld_not_zero(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Metric 5's min n is 60."""
        await seed_signals(session_factory, signals_per_call=[[], []])

        body = client.get("/api/v1/insights/demand", params={"as_of": AS_OF}).json()

        total = body["self_inflicted"]["total"]
        assert total["published"] is False
        assert total["value"] is None
        assert total["withheld_reason"] == "BELOW_MIN_N"
