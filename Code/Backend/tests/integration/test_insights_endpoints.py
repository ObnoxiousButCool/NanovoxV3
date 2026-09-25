"""`/insights/exec` and `/insights/risk` over a real application.

The assertions that matter here are not "the endpoint returns 200". They
are the three things the wire format exists to protect: a withheld figure
never arrives as a zero, a figure states the window it was computed over,
and an account nobody could assess never appears as an account found clean.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.value_objects.call_source import CallSource
from domain.value_objects.category import Category
from domain.value_objects.outcome import Outcome
from infrastructure.persistence.tables import (
    BrokerRow,
    CallExtractionRow,
    CallRow,
    EmployerRow,
)

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

AS_OF = "2026-09-28"


def _employer(reference: str, broker_id: int, *, enrolled: int = 120) -> EmployerRow:
    return EmployerRow(
        reference=reference,
        name=f"Employer {reference}",
        industry="Retail",
        design_churn_profile="STABLE",
        eligible=200,
        enrolled=enrolled,
        region="West",
        renewal_month="January",
        broker_id=broker_id,
        dental_sponsorship="voluntary",
        lines_held="dental",
        planned_calls=10,
        planned_member_calls=8,
        planned_employer_calls=2,
        fee_band=3,
        annual_fee=4200,
        annual_premium=98000.0,
        cobra_regime="federal",
    )


async def seed(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    calls_per_employer: dict[str, int],
    day: int = 20,
) -> None:
    """Employers with a given number of calls each, all recently."""
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

        index = 0
        for employer_ref, count in calls_per_employer.items():
            employer = _employer(employer_ref, broker.id)
            session.add(employer)
            await session.flush()
            for _ in range(count):
                index += 1
                call = CallRow(
                    reference=f"C-{index:04d}",
                    source=CallSource.CORPUS_PDF.value,
                    occurred_at=datetime(2026, 9, day, 10, 0, tzinfo=timezone.utc),
                    aht_seconds=400,
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
                    )
                )


@pytest.mark.asyncio
async def test_exec_states_a_window_per_metric(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The reason the response is not a flat row of figures."""
    await seed(session_factory, calls_per_employer={"EMP-01": 5})

    body = client.get("/api/v1/insights/exec", params={"asOf": AS_OF}).json()

    windows = {metric["key"]: metric["windowWeeks"] for metric in body["metrics"]}
    assert windows["first_contact_resolution"] == 4
    assert windows["escalation_integrity"] == 12
    assert body["asOf"] == AS_OF


@pytest.mark.asyncio
async def test_a_withheld_figure_is_never_a_zero_on_the_wire(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Five calls is under every min n on this screen."""
    await seed(session_factory, calls_per_employer={"EMP-01": 5})

    body = client.get("/api/v1/insights/exec", params={"asOf": AS_OF}).json()

    withheld = [m for m in body["metrics"] if not m["figure"]["published"]]
    assert withheld, "expected small samples to be withheld"
    for metric in withheld:
        assert metric["figure"]["value"] is None
        assert metric["figure"]["withheldReason"] is not None
        assert metric["figure"]["published"] is False


@pytest.mark.asyncio
async def test_intent_routed_is_withheld_for_want_of_a_field(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed(session_factory, calls_per_employer={"EMP-01": 5})

    body = client.get("/api/v1/insights/exec", params={"asOf": AS_OF}).json()

    assert body["intentRouted"]["withheldReason"]["code"] == "NO_FIELD"
    assert body["intentRouted"]["value"] is None


@pytest.mark.asyncio
async def test_both_escalation_views_travel_together(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed(session_factory, calls_per_employer={"EMP-01": 5})

    body = client.get("/api/v1/insights/exec", params={"asOf": AS_OF}).json()

    assert len(body["escalation"]) == 2
    assert "warranted" in body["escalation"][0]["label"]


@pytest.mark.asyncio
async def test_scope_reports_the_population_not_just_the_figures(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed(session_factory, calls_per_employer={"EMP-01": 5})

    body = client.get(
        "/api/v1/insights/exec", params={"asOf": AS_OF, "source": "CORPUS_PDF"}
    ).json()

    assert body["scope"]["considered"] == 5
    assert body["scope"]["matched"] == 5
    assert body["scope"]["sources"] == ["CORPUS_PDF"]
    assert any("control_exceptions" in caveat for caveat in body["scope"]["caveats"])


@pytest.mark.asyncio
async def test_a_filter_narrows_and_says_so(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed(session_factory, calls_per_employer={"EMP-01": 3, "EMP-02": 2})

    body = client.get("/api/v1/insights/exec", params={"asOf": AS_OF, "employer": "EMP-01"}).json()

    assert body["scope"]["matched"] == 3
    assert body["scope"]["considered"] == 5
    assert body["scope"]["appliedFilters"] == [{"field": "employer_refs", "values": ["EMP-01"]}]


@pytest.mark.asyncio
async def test_an_unknown_filter_value_is_rejected_at_the_edge(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Better a 422 than a figure over a filter that matched nothing."""
    await seed(session_factory, calls_per_employer={"EMP-01": 3})

    response = client.get("/api/v1/insights/exec", params={"category": "Not A Category"})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_risk_keeps_ineligible_accounts_out_of_the_assessed_list(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The finding this endpoint exists to protect.

    EMP-02 has one call, below metric 10's floor of three. It must not
    appear as an account assessed and found unflagged.
    """
    await seed(session_factory, calls_per_employer={"EMP-01": 4, "EMP-02": 1})

    body = client.get("/api/v1/insights/risk", params={"asOf": AS_OF}).json()

    assessed = {account["employerRef"] for account in body["assessed"]}
    assert assessed == {"EMP-01"}
    assert body["ineligible"] == ["EMP-02"]
    assert body["ineligibleCount"] == 1


@pytest.mark.asyncio
async def test_an_assessed_account_carries_its_state_sentence(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed(session_factory, calls_per_employer={"EMP-01": 4})

    body = client.get("/api/v1/insights/risk", params={"asOf": AS_OF}).json()

    account = body["assessed"][0]
    assert account["eligible"] is True
    assert "Not flagged" in account["state"]
    assert len(account["conditions"]) == 4
    assert len(account["observations"]) == 10


@pytest.mark.asyncio
async def test_unavailable_indicator_families_are_not_reported_as_zero(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed(session_factory, calls_per_employer={"EMP-01": 4})

    body = client.get("/api/v1/insights/risk", params={"asOf": AS_OF}).json()

    unavailable = [o for o in body["assessed"][0]["observations"] if not o["available"]]
    assert unavailable, "at least one family needs a field v9 does not have"
    for observation in unavailable:
        assert observation["rate"] is None
        assert observation["unavailableBecause"]


@pytest.mark.asyncio
async def test_the_risk_row_filters_do_not_move_the_denominator(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """D12's filters select rows, not the population.

    `flaggedShare` is flagged over *eligible*, and `exposure` sums the
    flagged accounts. If narrowing the visible list narrowed those too, a
    reader who filtered to "flagged only" would see a share of 100% and an
    exposure that grew as they filtered — a different statistic wearing the
    same label. The filter is applied after both are computed, and this is
    the test that says so.
    """
    await seed(session_factory, calls_per_employer={"EMP-01": 4, "EMP-02": 4})

    unfiltered = client.get("/api/v1/insights/risk", params={"asOf": AS_OF}).json()
    filtered = client.get("/api/v1/insights/risk", params={"asOf": AS_OF, "flagged": "true"}).json()

    assert filtered["flaggedShare"] == unfiltered["flaggedShare"]
    assert filtered["exposure"] == unfiltered["exposure"]
    assert all(account["flagged"] is True for account in filtered["assessed"])


@pytest.mark.asyncio
async def test_a_narrowed_risk_list_still_says_how_many_were_assessed(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Filters slice, never hide (§9).

    Without `assessedCount` a reader cannot tell "two accounts fired three
    indicators" from "only two accounts were assessable at all", and those
    are very different screens.
    """
    await seed(session_factory, calls_per_employer={"EMP-01": 4, "EMP-02": 4})

    body = client.get("/api/v1/insights/risk", params={"asOf": AS_OF, "minIndicators": 10}).json()

    assert body["assessedCount"] == 2
    assert len(body["assessed"]) <= body["assessedCount"]


@pytest.mark.asyncio
async def test_there_is_no_band_parameter(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """D12 leaves no band to filter by, and the API must not invent one.

    The prototype filtered on `band=High`. Accepting it here — even
    ignoring it — would let a client believe it had narrowed the screen
    when it had not. FastAPI ignores unknown parameters, so the guard is
    that `band` appears nowhere in the schema for this path.
    """
    schema = client.get("/openapi.json").json()
    names = {
        parameter["name"]
        for parameter in schema["paths"]["/api/v1/insights/risk"]["get"]["parameters"]
    }

    assert "band" not in names
    assert {"flagged", "minIndicators"} <= names


@pytest.mark.asyncio
async def test_an_out_of_range_indicator_count_is_refused(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """There are ten families, so eleven is a question with no answer."""
    await seed(session_factory, calls_per_employer={"EMP-01": 4})

    response = client.get("/api/v1/insights/risk", params={"asOf": AS_OF, "minIndicators": 11})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_exposure_is_never_an_expected_loss(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed(session_factory, calls_per_employer={"EMP-01": 4})

    body = client.get("/api/v1/insights/risk", params={"asOf": AS_OF}).json()

    assert "not expected loss" in body["exposure"]["caveat"]


@pytest.mark.asyncio
async def test_flagged_share_divides_by_the_eligible_not_the_book(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """With nothing eligible the share is withheld, never reported as 0%."""
    await seed(session_factory, calls_per_employer={"EMP-01": 1, "EMP-02": 1})

    body = client.get("/api/v1/insights/risk", params={"asOf": AS_OF}).json()

    assert body["assessed"] == []
    assert body["flaggedShare"]["published"] is False
    assert body["flaggedShare"]["value"] is None
    assert body["flaggedShare"]["withheldReason"]["code"] == "NOT_ELIGIBLE"
