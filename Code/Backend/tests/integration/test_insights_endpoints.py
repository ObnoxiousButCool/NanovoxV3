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
async def test_the_risk_screen_carries_its_headline_tile_counts(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Wiring, not scenario coverage: `seed()` writes every call with
    `escalation_triggered=False` and no signals, so this only confirms the
    three counts reach the wire and read as zero against zero warranted
    escalations and zero exit-language calls — not that a real missed
    escalation or a real retention_risk signal is counted correctly. That
    needs `seed()` extended to accept escalation/signal data per call,
    which is a larger change than this endpoint test should make on its
    own; `test_call_tags.py`'s
    `test_a_triggered_and_unhandled_escalation_is_missed` already covers
    the `Escalation.missed` logic this count is built from."""
    await seed(session_factory, calls_per_employer={"EMP-01": 4})

    body = client.get("/api/v1/insights/risk", params={"asOf": AS_OF}).json()

    assert body["escalationsTriggered"] == 0
    assert body["escalationsMissed"] == 0
    assert body["exitLanguageCalls"] == 0


@pytest.mark.asyncio
async def test_a_request_with_no_as_of_is_dated_from_the_corpus_not_the_clock(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Every window is measured back from `asOf`, and the corpus is a fixed
    historical batch.

    Dating it from the wall clock slid the windows off the data a day at a
    time: with the corpus ending 25 September and the clock on 1 October,
    metric 10's twelve weeks began 9 July and left out the 38 calls of
    6-8 July -- so the risk screen counted 562 under a filter bar reading
    600, and the gap grew daily until the screen would have shown nothing.
    """
    await seed(session_factory, calls_per_employer={"EMP-01": 4}, day=20)

    body = client.get("/api/v1/insights/risk").json()

    assert body["asOf"] == "2026-09-20"
    # The whole corpus is inside the window now, so the outcome bar and the
    # filter bar above it count the same calls.
    assert sum(entry["calls"] for entry in body["outcomes"]) == body["scope"]["matched"]


@pytest.mark.asyncio
async def test_an_explicit_as_of_still_wins(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The default moved; the parameter did not. A reader asking what the
    book looked like on a date still gets that date."""
    await seed(session_factory, calls_per_employer={"EMP-01": 4}, day=20)

    body = client.get("/api/v1/insights/risk", params={"asOf": "2026-09-28"}).json()

    assert body["asOf"] == "2026-09-28"


@pytest.mark.asyncio
async def test_a_period_filter_does_not_move_the_as_of(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """D11 from the other side.

    The anchor is the corpus extent *before* the period bounds, so
    narrowing to a few days bounds which calls are counted and does not
    redefine what any metric is computed over. Anchoring to the filtered
    slice would have made every window move with a dropdown.
    """
    await seed(session_factory, calls_per_employer={"EMP-01": 4}, day=20)

    narrowed = client.get(
        "/api/v1/insights/risk", params={"from": "2026-09-19", "to": "2026-09-21"}
    ).json()

    assert narrowed["asOf"] == "2026-09-20"


@pytest.mark.asyncio
async def test_the_risk_screen_carries_insight_9_withheld(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Insight 9 renders withheld unconditionally (plan.md's Phase 8 note) —
    no filter or corpus state changes this, since no gate unlocks it."""
    await seed(session_factory, calls_per_employer={"EMP-01": 4})

    body = client.get("/api/v1/insights/risk", params={"asOf": AS_OF}).json()

    panel = body["bandCalibration"]
    assert panel["insight"] == 9
    assert panel["question"]
    assert panel["why"]
    assert panel["unlockedBy"]


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

    response = client.get("/api/v1/insights/risk", params={"asOf": AS_OF})
    assert response.status_code == 200, response.text
    body = response.json()

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


@pytest.mark.asyncio
async def test_an_assessed_account_carries_its_renewal(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """D12 sorts by renewal; a screen naming an account needs the date itself.

    `_employer` seeds every account with January, so an `as_of` of
    2026-09-28 is four whole months out.
    """
    await seed(session_factory, calls_per_employer={"EMP-01": 4})

    body = client.get("/api/v1/insights/risk", params={"asOf": AS_OF}).json()

    account = body["assessed"][0]
    assert account["renewalMonth"] == "January"
    assert account["monthsToRenewal"] == 4


async def _seed_with_category_and_escalation(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    calls: list[tuple[Category, Outcome, bool, bool]],
) -> None:
    """Employer EMP-01 with one call per `(category, outcome, triggered, handled)`."""
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

        for index, (category, outcome, triggered, handled) in enumerate(calls, start=1):
            call = CallRow(
                reference=f"C-{index:04d}",
                source=CallSource.CORPUS_PDF.value,
                occurred_at=datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc),
                aht_seconds=400,
                caller_type="MEMBER",
                caller_ref="MEM-1",
                agent_ref="AG-01",
                agent_name="Alex",
                resolution_status=outcome.value,
                employer_id=employer.id,
            )
            session.add(call)
            await session.flush()
            session.add(
                CallExtractionRow(
                    call_id=call.id,
                    outcome=outcome.value,
                    category=category.value,
                    complaint_present=False,
                    escalation_triggered=triggered,
                    escalation_handled=handled if triggered else None,
                    knowledge_failure_present=False,
                )
            )


@pytest.mark.asyncio
async def test_area_of_concern_names_the_category_with_most_unresolved_calls(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_with_category_and_escalation(
        session_factory,
        calls=[
            (Category.CLAIMS_AND_EOB, Outcome.UNRESOLVED, False, False),
            (Category.COVERAGE_AND_BENEFITS, Outcome.UNRESOLVED, True, False),
            (Category.COVERAGE_AND_BENEFITS, Outcome.UNRESOLVED, False, False),
            (Category.COVERAGE_AND_BENEFITS, Outcome.RESOLVED, False, False),
        ],
    )

    body = client.get("/api/v1/insights/exec", params={"asOf": AS_OF}).json()

    concern = body["areaOfConcern"]
    assert concern is not None
    assert concern["category"] == "Coverage & Benefits"
    assert concern["unresolved"] == 2
    assert concern["escalationsTriggered"] == 1
    assert concern["escalationsHandled"] == 0


@pytest.mark.asyncio
async def test_area_of_concern_is_null_when_nothing_is_unresolved(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """A clean book names no concern rather than picking one anyway."""
    await seed(session_factory, calls_per_employer={"EMP-01": 4})

    body = client.get("/api/v1/insights/exec", params={"asOf": AS_OF}).json()

    assert body["areaOfConcern"] is None


# --- D12's order, amended 2026-09-29: the flag first -------------------------


async def _flagged_and_quiet(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Two accounts that rank in opposite orders under the two keys.

    `EMP-FLAG` has three calls: enough for metric 10's eligibility floor of
    three, under the indicator families' floor of five. Two of the four
    conditions fire, so it is flagged with nought indicators observed —
    Junipero's shape exactly.

    `EMP-QUIET` has eight unresolved calls: over the family floor, so the
    unresolved family is observed, and no condition of metric 10's fires.
    Unflagged, with an indicator count.

    Under the old key the quiet account came first.
    """
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

        flagged = _employer("EMP-FLAG", broker.id)
        # Renewal next month, so the fourth condition's window is open over
        # these calls -- `_next_renewal` rolls a month already begun forward
        # to next year, which would put them a year early.
        flagged.renewal_month = "October"
        session.add(flagged)
        quiet = _employer("EMP-QUIET", broker.id)
        session.add(quiet)
        await session.flush()

        for index in range(3):
            call = CallRow(
                reference=f"F-{index:04d}",
                source=CallSource.CORPUS_PDF.value,
                occurred_at=datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc),
                aht_seconds=400,
                caller_type="MEMBER",
                caller_ref="MEM-F",
                agent_ref="AG-01",
                agent_name="Alex",
                resolution_status="UNRESOLVED",
                employer_id=flagged.id,
            )
            session.add(call)
            await session.flush()
            session.add(
                CallExtractionRow(
                    call_id=call.id,
                    outcome=Outcome.UNRESOLVED.value,
                    category=Category.CLAIMS_AND_EOB.value,
                    complaint_present=True,
                    complaint_attributed_to="CHOICE",
                    intent=[{"type": "market_test", "quote": "We are shopping.", "turn_seq": 1}],
                    escalation_triggered=False,
                    knowledge_failure_present=False,
                )
            )

        for index in range(8):
            call = CallRow(
                reference=f"Q-{index:04d}",
                source=CallSource.CORPUS_PDF.value,
                occurred_at=datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc),
                aht_seconds=400,
                caller_type="MEMBER",
                caller_ref=f"MEM-Q{index}",
                agent_ref="AG-01",
                agent_name="Alex",
                resolution_status="UNRESOLVED",
                employer_id=quiet.id,
            )
            session.add(call)
            await session.flush()
            session.add(
                CallExtractionRow(
                    call_id=call.id,
                    outcome=Outcome.UNRESOLVED.value,
                    category=Category.CLAIMS_AND_EOB.value,
                    complaint_present=False,
                    escalation_triggered=False,
                    knowledge_failure_present=False,
                )
            )


@pytest.mark.asyncio
async def test_a_flagged_account_ranks_above_an_unflagged_one_with_more_indicators(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """D12 made the flag the one scoring system and the ten families
    informational. Ranking on the count first put the informational system
    back in front, and it buried the accounts this screen exists to surface:
    the flag is eligible from three calls and the families are gated from
    five, so a flagged account can score nought without one family having
    been checked.
    """
    await _flagged_and_quiet(session_factory)

    body = client.get("/api/v1/insights/risk", params={"asOf": AS_OF}).json()

    order = [account["employerRef"] for account in body["assessed"]]
    assert order[0] == "EMP-FLAG", "a flagged account must not sit below an unflagged one"

    flagged = body["assessed"][0]
    quiet = body["assessed"][1]
    assert flagged["flagged"] is True
    assert quiet["flagged"] is False
    # And the reason the old key got it wrong: the flagged account has fewer.
    assert sum(1 for o in flagged["observations"] if o["observed"]) < sum(
        1 for o in quiet["observations"] if o["observed"]
    )


@pytest.mark.asyncio
async def test_the_risk_screen_carries_lives_per_account_and_never_nought(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """`index.html` prints lives beside the flag, so the wire has to carry
    them per account and not only summed into `exposure`.

    The two must agree: `exposure.lives` is the only total on the screen, and
    a reader who adds the column up has to arrive at the same book.
    """
    await seed(session_factory, calls_per_employer={"EMP-01": 4})

    body = client.get("/api/v1/insights/risk", params={"asOf": AS_OF}).json()

    account = body["assessed"][0]
    assert account["lives"] is not None
    assert account["lives"] > 0
    flagged = [a["lives"] for a in body["assessed"] if a["flagged"]]
    assert sum(flagged) == body["exposure"]["lives"]


@pytest.mark.asyncio
async def test_the_risk_screen_counts_accounts_new_to_the_indicator_list(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The sixth tile. It says what it counts from, because a bare number of
    newly flagged accounts is unreadable without the date."""
    await seed(session_factory, calls_per_employer={"EMP-01": 4})

    body = client.get("/api/v1/insights/risk", params={"asOf": AS_OF}).json()

    tile = body["newlyFlagged"]
    assert tile is not None
    assert tile["count"] == len(tile["employers"])
    assert tile["since"]
    assert tile["weeks"] > 0
    # Stated on the wire rather than left for a screen to remember: this is
    # the one figure here the filter bar does not narrow.
    assert tile["unfiltered"] is True
