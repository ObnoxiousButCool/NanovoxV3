"""The period filter over a real application (decision D11).

The rule this file exists to protect is one sentence: **a period filter
narrows the corpus; it does not redefine a metric's window.** Everything
below is a way of catching the moment that stops being true.

The tempting bug is the opposite reading — that asking for three weeks
makes every figure a three-week figure. It is tempting because it is what
a reader expects, it produces smaller and tidier numbers, and nothing
crashes. It would publish a twelve-week rate under a three-week definition
the Metrics sheet does not carry, with nothing on screen to say so.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
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
EXEC = "/api/v1/insights/exec"
RISK = "/api/v1/insights/risk"


def _employer(reference: str, broker_id: int) -> EmployerRow:
    return EmployerRow(
        reference=reference,
        name=f"Employer {reference}",
        industry="Retail",
        design_churn_profile="STABLE",
        eligible=200,
        enrolled=120,
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
    days: list[int],
    undated: int = 0,
) -> None:
    """One call per entry in `days` (September 2026), plus `undated` with no date."""
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

        occurred: list[datetime | None] = [
            datetime(2026, 9, day, 10, 0, tzinfo=timezone.utc) for day in days
        ]
        occurred.extend([None] * undated)

        for index, when in enumerate(occurred, start=1):
            call = CallRow(
                reference=f"C-{index:04d}",
                source=CallSource.CORPUS_PDF.value,
                occurred_at=when,
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


# --------------------------------------------------------------------------
# The bounds themselves
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_period_narrows_the_corpus(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Calls outside the period are not read at all."""
    await seed(session_factory, days=[2, 4, 20, 22])

    whole = client.get(EXEC, params={"asOf": AS_OF}).json()
    narrowed = client.get(
        EXEC, params={"asOf": AS_OF, "from": "2026-09-15", "to": "2026-09-30"}
    ).json()

    assert whole["scope"]["considered"] == 4
    assert narrowed["scope"]["considered"] == 2


@pytest.mark.asyncio
async def test_both_bounds_are_inclusive(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """A call on the boundary is in, not out. Off-by-one here is silent."""
    await seed(session_factory, days=[10, 20])

    body = client.get(EXEC, params={"asOf": AS_OF, "from": "2026-09-10", "to": "2026-09-20"}).json()

    assert body["scope"]["considered"] == 2


@pytest.mark.asyncio
async def test_one_open_end_bounds_only_the_other(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed(session_factory, days=[2, 20])

    from_only = client.get(EXEC, params={"asOf": AS_OF, "from": "2026-09-10"}).json()
    to_only = client.get(EXEC, params={"asOf": AS_OF, "to": "2026-09-10"}).json()

    assert from_only["scope"]["considered"] == 1
    assert to_only["scope"]["considered"] == 1


@pytest.mark.asyncio
async def test_an_undated_call_survives_both_bounds_and_is_still_reported(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The calls the port exists to report must not be dropped by a bound.

    A naive `occurred_at >= since` is false for NULL, so undated calls would
    vanish from `excludedCalls` and from the caveat — and the one number
    that says "some calls reached no figure at all" would quietly become
    zero. That reads as a clean corpus.
    """
    await seed(session_factory, days=[20], undated=3)

    body = client.get(EXEC, params={"asOf": AS_OF, "from": "2026-09-01", "to": "2026-09-30"}).json()

    assert body["scope"]["excludedCalls"] == 3
    assert any("no date" in caveat for caveat in body["scope"]["caveats"])


# --------------------------------------------------------------------------
# The period is echoed, not assumed
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_period_is_echoed_back(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed(session_factory, days=[20])

    body = client.get(EXEC, params={"asOf": AS_OF, "from": "2026-09-01", "to": "2026-09-30"}).json()

    assert body["scope"]["period"] == {"from": "2026-09-01", "to": "2026-09-30"}


@pytest.mark.asyncio
async def test_no_period_asked_means_no_period_claimed(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Null, not a made-up range. An invented period would be a claim."""
    await seed(session_factory, days=[20])

    body = client.get(EXEC, params={"asOf": AS_OF}).json()

    assert body["scope"]["period"] is None


# --------------------------------------------------------------------------
# D11 itself: the window is NOT narrowed, and the response says so
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_metric_window_is_not_narrowed_to_the_period(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The whole point of D11. `windowWeeks` is the metric's, not the ask."""
    await seed(session_factory, days=[20])

    body = client.get(EXEC, params={"asOf": AS_OF, "from": "2026-09-21", "to": "2026-09-28"}).json()

    windows = {metric["key"]: metric["windowWeeks"] for metric in body["metrics"]}
    assert windows["first_contact_resolution"] == 4
    assert windows["escalation_integrity"] == 12


@pytest.mark.asyncio
async def test_a_window_reaching_outside_the_period_says_so(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """A one-week ask against a 4- and 12-week screen. Both must be named."""
    await seed(session_factory, days=[20])

    body = client.get(EXEC, params={"asOf": AS_OF, "from": "2026-09-21", "to": "2026-09-28"}).json()

    caveats = " ".join(body["scope"]["caveats"])
    assert "reaches outside the period you asked for" in caveats
    assert "First-contact resolution" in caveats
    assert "Escalation integrity" in caveats


@pytest.mark.asyncio
async def test_no_caveat_when_every_window_sits_inside_the_period(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """A caveat printed every time stops being read."""
    await seed(session_factory, days=[20])

    body = client.get(EXEC, params={"asOf": AS_OF, "from": "2020-01-01", "to": "2030-01-01"}).json()

    assert not any("reaches outside" in caveat for caveat in body["scope"]["caveats"])


@pytest.mark.asyncio
async def test_calls_a_window_leaves_out_are_counted_on_the_page(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The gap that had no sentence.

    `period_caveat` only fires when a period is asked for, so with no filter
    at all the screen said nothing — and a window ending on today's date
    drops the oldest calls of a corpus that ended earlier. The risk screen
    counted 562 of the 600 its own filter bar reported in scope.
    """
    # Read as at 20 October, which puts the 4-week window's start at
    # 22 September: day 25 is inside it and day 2 is not, while both sit
    # inside the 12-week window. The fixture's dates are September-only.
    await seed(session_factory, days=[2, 25])

    body = client.get(EXEC, params={"asOf": "2026-10-20"}).json()

    caveats = " ".join(body["scope"]["caveats"])
    assert "leaves out 1 of the 2 calls in scope" in caveats
    assert body["scope"]["matched"] == 2


@pytest.mark.asyncio
async def test_a_window_covering_every_call_says_nothing(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed(session_factory, days=[20])

    body = client.get(RISK, params={"asOf": AS_OF}).json()

    assert body["scope"]["matched"] == 1
    assert not any("leaves out" in caveat for caveat in body["scope"]["caveats"])


@pytest.mark.asyncio
async def test_metrics_sharing_a_window_are_named_in_one_sentence(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Five metrics over two windows was five near-identical paragraphs
    above the figures, which is how a caveat stops being read."""
    await seed(session_factory, days=[2, 25])

    body = client.get(EXEC, params={"asOf": "2026-10-20"}).json()

    left_out = [caveat for caveat in body["scope"]["caveats"] if "leaves out" in caveat]
    # One sentence, naming both metrics that share the 4-week window. The
    # 12-week metrics cover every call here, so they say nothing.
    assert len(left_out) == 1
    assert "First-contact resolution and Knowledge failure rate are computed" in left_out[0]


@pytest.mark.asyncio
async def test_every_insights_endpoint_accepts_the_period(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """One filter bar means one filter set. A 422 here is a divergence."""
    await seed(session_factory, days=[20])
    params = {"asOf": AS_OF, "from": "2026-09-01", "to": "2026-09-30"}

    paths = [
        "/api/v1/insights/exec",
        "/api/v1/insights/risk",
        "/api/v1/insights/accounts/EMP-01",
        "/api/v1/insights/hierarchy",
        "/api/v1/insights/demand",
        "/api/v1/insights/actions",
        "/api/v1/insights/rules",
        "/api/v1/insights/agents",
    ]
    for path in paths:
        response = client.get(path, params=params)
        assert response.status_code == 200, f"{path} -> {response.status_code}"
        assert response.json()["scope"]["period"] == {
            "from": "2026-09-01",
            "to": "2026-09-30",
        }, path


# --------------------------------------------------------------------------
# Rejected at the edge
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_inverted_period_is_refused_rather_than_answered_empty(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """An empty screen would read as "no evidence" rather than "bad request"."""
    await seed(session_factory, days=[20])

    response = client.get(EXEC, params={"asOf": AS_OF, "from": "2026-09-30", "to": "2026-09-01"})

    assert response.status_code == 400
    body = response.json()
    assert body["code"] == "validation_error"
    assert "2026-09-30" in body["detail"] and "2026-09-01" in body["detail"]


@pytest.mark.asyncio
async def test_a_malformed_date_is_refused_by_the_schema(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed(session_factory, days=[20])

    response = client.get(EXEC, params={"asOf": AS_OF, "from": "last Tuesday"})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_a_single_day_period_is_allowed(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """from == to is a legitimate one-day question, not an inverted range."""
    await seed(session_factory, days=[20, 21])

    body = client.get(EXEC, params={"asOf": AS_OF, "from": "2026-09-20", "to": "2026-09-20"}).json()

    assert body["scope"]["considered"] == 1


# --------------------------------------------------------------------------
# The corpus extent: what a period control has to offer
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_corpus_extent_is_reported(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed(session_factory, days=[2, 11, 25])

    body = client.get(EXEC, params={"asOf": AS_OF}).json()

    assert body["scope"]["corpusPeriod"] == {"from": "2026-09-02", "to": "2026-09-25"}


@pytest.mark.asyncio
async def test_narrowing_the_period_does_not_shrink_the_corpus_extent(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Otherwise a control could narrow once and never widen again.

    Deriving the extent from the slice just loaded is the obvious shortcut
    and it is a one-way door: ask for one week, and the only week the
    picker can now offer is that week.
    """
    await seed(session_factory, days=[2, 11, 25])

    body = client.get(EXEC, params={"asOf": AS_OF, "from": "2026-09-10", "to": "2026-09-12"}).json()

    assert body["scope"]["period"] == {"from": "2026-09-10", "to": "2026-09-12"}
    assert body["scope"]["corpusPeriod"] == {"from": "2026-09-02", "to": "2026-09-25"}


@pytest.mark.asyncio
async def test_undated_calls_do_not_define_the_extent(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed(session_factory, days=[11], undated=3)

    body = client.get(EXEC, params={"asOf": AS_OF}).json()

    assert body["scope"]["corpusPeriod"] == {"from": "2026-09-11", "to": "2026-09-11"}


@pytest.mark.asyncio
async def test_no_dated_call_means_no_extent_claimed(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Null, not today's date. An invented range would be a claim."""
    await seed(session_factory, days=[], undated=2)

    body = client.get(EXEC, params={"asOf": AS_OF}).json()

    assert body["scope"]["corpusPeriod"] is None


# --------------------------------------------------------------------------
# Trends on the executive screen
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exec_reports_movement_against_an_equal_window(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed(session_factory, days=[2, 11, 25])

    trends = client.get(EXEC, params={"asOf": AS_OF}).json()["trends"]

    assert trends["windowWeeks"] == 4
    span = date.fromisoformat(trends["windowEnd"]) - date.fromisoformat(trends["windowStart"])
    prior_span = date.fromisoformat(trends["priorEnd"]) - date.fromisoformat(trends["priorStart"])
    assert span == prior_span, "windows must be the same length to be comparable"
    assert trends["priorEnd"] < trends["windowStart"]


@pytest.mark.asyncio
async def test_a_silent_week_is_null_on_the_wire_not_zero(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The distinction has to survive serialisation, or the chart cannot draw it."""
    await seed(session_factory, days=[25])

    weeks = client.get(EXEC, params={"asOf": AS_OF}).json()["trends"]["weeks"]

    assert any(week["calls"] is None for week in weeks), "expected a silent week"
    assert all(week["calls"] != 0 for week in weeks), "a silent week must not serialise as 0"


@pytest.mark.asyncio
async def test_every_movement_says_whether_it_beat_the_noise(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed(session_factory, days=[2, 11, 25])

    movements = client.get(EXEC, params={"asOf": AS_OF}).json()["trends"]["movements"]

    assert movements
    for move in movements:
        assert set(move) >= {"label", "now", "prior", "expected", "z", "beyondNoise", "worse"}


@pytest.mark.asyncio
async def test_resolved_calls_are_not_bad_when_they_rise(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Direction is not meaning, and the wire has to carry that."""
    await seed(session_factory, days=[20, 21, 22])

    movements = client.get(EXEC, params={"asOf": AS_OF}).json()["trends"]["movements"]
    resolved = next(m for m in movements if m["label"] == "Resolved calls")

    assert resolved["now"] > resolved["prior"]
    assert not resolved["worse"]


@pytest.mark.asyncio
async def test_emerging_counts_are_not_shares(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed(session_factory, days=[20, 21, 22])

    rows = client.get(EXEC, params={"asOf": AS_OF}).json()["trends"]["emerging"]

    assert rows
    for row in rows:
        for bucket in row["buckets"]:
            assert isinstance(bucket["hits"], int)
            assert "calls" in bucket, "a bucket states its denominator rather than implying one"


@pytest.mark.asyncio
async def test_trends_narrow_with_the_filters(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """A movement beside a filtered scorecard must be about the same calls.

    Otherwise the screen contradicts itself without saying so.
    """
    await seed(session_factory, days=[20, 21, 22])

    unfiltered = client.get(EXEC, params={"asOf": AS_OF}).json()["trends"]
    filtered = client.get(EXEC, params={"asOf": AS_OF, "outcome": "UNRESOLVED"}).json()["trends"]

    total = next(m for m in unfiltered["movements"] if m["label"] == "Resolved calls")
    none_left = next(m for m in filtered["movements"] if m["label"] == "Resolved calls")
    assert total["now"] > 0
    assert none_left["now"] == 0
