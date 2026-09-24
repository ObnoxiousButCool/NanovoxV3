"""`/insights/accounts/{ref}` and `/insights/hierarchy`.

The claims worth pinning: a peer comparison nobody can compute comes back
null rather than zero, an unknown account is a 404 rather than an empty
page, and the hierarchy keeps the rows that would otherwise disappear —
quiet employers and empty matrix cells.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.integration.test_insights_endpoints import AS_OF, seed

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

pytestmark = pytest.mark.asyncio


class TestAccount:
    async def test_an_unknown_employer_is_a_404_not_an_empty_page(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """An account page for a reference nobody recognises would invent a
        business relationship."""
        await seed(session_factory, calls_per_employer={"EMP-01": 3})

        response = client.get("/api/v1/insights/accounts/EMP-NOPE", params={"asOf": AS_OF})

        assert response.status_code == 404

    async def test_the_account_facts_come_from_reference_data(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(session_factory, calls_per_employer={"EMP-01": 3})

        body = client.get("/api/v1/insights/accounts/EMP-01", params={"asOf": AS_OF}).json()

        assert body["facts"]["employerRef"] == "EMP-01"
        assert body["facts"]["enrolled"] == 120
        assert body["facts"]["brokerRef"] == "BRK-01"
        assert body["facts"]["renewalMonth"] == "January"

    async def test_a_peer_comparison_nobody_can_compute_is_null_not_zero(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Zero would read as 'in line with peers', which is the one
        conclusion a single-employer band cannot support."""
        await seed(session_factory, calls_per_employer={"EMP-01": 3})

        body = client.get("/api/v1/insights/accounts/EMP-01", params={"asOf": AS_OF}).json()

        assert body["peers"]["difference"] is None
        assert body["peers"]["peers"] == 0

    async def test_the_two_rates_state_their_own_windows(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(session_factory, calls_per_employer={"EMP-01": 3})

        body = client.get("/api/v1/insights/accounts/EMP-01", params={"asOf": AS_OF}).json()

        assert body["contactRate"]["windowWeeks"] == 12
        assert body["repeatRate"]["windowWeeks"] == 12

    async def test_risk_reads_the_same_as_on_the_risk_screen(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """One shape, so 'ineligible' cannot mean two things."""
        await seed(session_factory, calls_per_employer={"EMP-01": 4})

        account = client.get("/api/v1/insights/accounts/EMP-01", params={"asOf": AS_OF}).json()[
            "risk"
        ]
        screen = client.get("/api/v1/insights/risk", params={"asOf": AS_OF}).json()["assessed"][0]

        assert account == screen

    async def test_an_ineligible_account_still_has_a_page(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Too few calls to assess is not too few calls to exist."""
        await seed(session_factory, calls_per_employer={"EMP-01": 1})

        body = client.get("/api/v1/insights/accounts/EMP-01", params={"asOf": AS_OF}).json()

        assert body["risk"]["eligible"] is False
        assert "Not eligible" in body["risk"]["state"]


class TestHierarchy:
    async def test_the_tree_keeps_employers_that_never_called(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """A quiet region must not look like a small one."""
        await seed(session_factory, calls_per_employer={"EMP-01": 3, "EMP-02": 0})

        body = client.get("/api/v1/insights/hierarchy", params={"asOf": AS_OF}).json()

        leaves = {
            node["employerRef"]: node["calls"]
            for region in body["tree"]
            for broker in region["brokers"]
            for node in broker["employers"]
        }
        assert leaves == {"EMP-01": 3, "EMP-02": 0}

    async def test_the_matrix_carries_every_category_in_every_row(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """The columns have to line up for 'a dark column is book-wide'."""
        await seed(session_factory, calls_per_employer={"EMP-01": 3})

        body = client.get("/api/v1/insights/hierarchy", params={"asOf": AS_OF}).json()

        row = body["matrix"][0]
        assert len(row["counts"]) == 7
        assert row["counts"]["Claims & EOB"] == 3
        assert row["counts"]["Provider Network"] == 0

    async def test_the_screen_states_one_window(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(session_factory, calls_per_employer={"EMP-01": 3})

        body = client.get("/api/v1/insights/hierarchy", params={"asOf": AS_OF}).json()

        assert body["windowWeeks"] == 12
        assert body["asOf"] == AS_OF

    async def test_a_book_under_the_ranking_floor_is_not_ranked(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """120 lives is under the 150-life floor, so no league table row."""
        await seed(session_factory, calls_per_employer={"EMP-01": 3})

        body = client.get("/api/v1/insights/hierarchy", params={"asOf": AS_OF}).json()

        assert body["rankedBrokers"] == []

    async def test_a_filter_narrows_the_hierarchy_and_says_so(
        self, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await seed(session_factory, calls_per_employer={"EMP-01": 3, "EMP-02": 2})

        body = client.get(
            "/api/v1/insights/hierarchy", params={"asOf": AS_OF, "employer": "EMP-01"}
        ).json()

        assert body["scope"]["matched"] == 3
        assert body["scope"]["considered"] == 5
        leaves = {
            node["employerRef"]: node["calls"]
            for region in body["tree"]
            for broker in region["brokers"]
            for node in broker["employers"]
        }
        assert leaves["EMP-02"] == 0
