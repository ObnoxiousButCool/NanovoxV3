"""The filter options endpoint.

Employers and brokers are also reachable from `/insights/hierarchy`, so the
lists this adds are `regions`, `agentRefs`, `touchpoints` and the labels —
and one guarantee that matters more than any of them.

**Applying the current filters to the options is a one-way door.** Narrow to
one broker and a bar built from the response offers one broker; the reader
cannot widen again, and nothing on screen explains why. The first test here
pins that, and it is the one to keep if the others ever look redundant.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.integration.test_insights_period_filter import AS_OF, seed

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

FILTERS = "/api/v1/insights/filters"


@pytest.mark.asyncio
async def test_options_do_not_narrow_with_the_filters(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The whole point. Narrowing once must not remove the way back."""
    await seed(session_factory, days=[20])

    everything = client.get(FILTERS, params={"asOf": AS_OF}).json()
    narrowed = client.get(FILTERS, params={"asOf": AS_OF, "region": "Nowhere"}).json()

    assert narrowed["employers"] == everything["employers"]
    assert narrowed["brokers"] == everything["brokers"]
    assert narrowed["regions"] == everything["regions"]


@pytest.mark.asyncio
async def test_reference_lists_include_parties_with_no_calls(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """A broker with no calls is still a broker you may filter by.

    Leaving it out would read as "this broker does not exist".
    """
    await seed(session_factory, days=[])

    body = client.get(FILTERS, params={"asOf": AS_OF}).json()

    assert body["brokers"], "reference data, not call-derived"
    assert body["employers"]


@pytest.mark.asyncio
async def test_observed_lists_come_from_the_calls(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Agents and touchpoints have no reference sheet, so they are what the
    corpus contains — and are empty when it contains nothing."""
    await seed(session_factory, days=[])

    body = client.get(FILTERS, params={"asOf": AS_OF}).json()

    assert body["agentRefs"] == []
    assert body["touchpoints"] == []


@pytest.mark.asyncio
async def test_an_agent_seen_on_a_call_is_offered(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed(session_factory, days=[20])

    body = client.get(FILTERS, params={"asOf": AS_OF}).json()

    assert body["agentRefs"] == ["AG-01"]


@pytest.mark.asyncio
async def test_labelled_enums_carry_their_wording(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """So a client never copies the label map and lets it drift."""
    await seed(session_factory, days=[20])

    body = client.get(FILTERS, params={"asOf": AS_OF}).json()

    signals = {entry["code"]: entry["label"] for entry in body["signals"]}
    assert signals["billing_defect"] == "Billing defect"
    layers = {entry["code"]: entry["label"] for entry in body["ruleLayers"]}
    assert layers["P"] == "Program"


@pytest.mark.asyncio
async def test_filters_with_no_display_wording_are_named_not_hidden(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The gap is stated rather than filled with invented text.

    Nothing defines how `PARTIALLY RESOLVED` should read on a screen. Naming
    the gap keeps it one decision instead of five screens each solving it
    their own way.
    """
    await seed(session_factory, days=[20])

    body = client.get(FILTERS, params={"asOf": AS_OF}).json()

    assert "outcome" in body["unlabelledFilters"]
    assert "qualityBand" in body["unlabelledFilters"]


@pytest.mark.asyncio
async def test_lists_are_ordered_for_a_reader_not_by_insertion(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed(session_factory, days=[20])

    body = client.get(FILTERS, params={"asOf": AS_OF}).json()

    assert body["regions"] == sorted(body["regions"])
    assert [b["agency"] for b in body["brokers"]] == sorted(b["agency"] for b in body["brokers"])
    assert [e["name"] for e in body["employers"]] == sorted(e["name"] for e in body["employers"])


@pytest.mark.asyncio
async def test_an_employer_option_carries_its_broker_for_a_dependent_filter(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed(session_factory, days=[20])

    body = client.get(FILTERS, params={"asOf": AS_OF}).json()

    assert body["employers"][0]["brokerRef"]
