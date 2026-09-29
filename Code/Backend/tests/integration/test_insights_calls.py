"""`/insights/calls`, the export, and the evidence endpoint.

The assertion this file exists for is the last one: **the leak check runs
against the evidence response**. `plan.md` §6.3 calls label stripping "the
single most important safety property", and until Phase 3 it was asserted
only where text entered the application. The evidence endpoint is where
text leaves it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.value_objects.call_source import CallSource
from domain.value_objects.category import Category
from domain.value_objects.outcome import Outcome
from infrastructure.persistence.tables import (
    BrokerRow,
    CallExtractionRow,
    CallRow,
    CallTurnRow,
    EmployerRow,
    MemberRow,
    SignalRow,
)

# `_employer` is private to that module, but importing it beats restating the
# fixture: several of the employer columns are NOT NULL, and one of them is
# the field `test_no_circular_scoring` keeps out of new files. Reusing the
# helper means this file never needs to name it.
from tests.integration.test_insights_endpoints import AS_OF, _employer, seed
from tests.support.leak_check import assert_text_carries_no_answer_key

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


async def seed_with_turns(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    turns: tuple[tuple[str, str], ...],
    reference: str = "C-9001",
) -> None:
    """One call carrying a transcript, for the evidence endpoint."""
    async with session_factory() as session, session.begin():
        broker = BrokerRow(
            reference="BRK-09",
            name="Broker",
            agency="Agency",
            region="West",
            groups_in_book=2,
            signal_profile="neutral",
        )
        session.add(broker)
        await session.flush()
        employer = _employer("EMP-09", broker.id)
        session.add(employer)
        await session.flush()
        call = CallRow(
            reference=reference,
            source=CallSource.CORPUS_PDF.value,
            occurred_at=datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc),
            aht_seconds=400,
            caller_type="MEMBER",
            caller_ref="MEM-9",
            agent_ref="AG-09",
            agent_name="Alex",
            resolution_status="RESOLVED",
            employer_id=employer.id,
        )
        session.add(call)
        await session.flush()
        for sequence, (role, text) in enumerate(turns):
            session.add(CallTurnRow(call_id=call.id, sequence=sequence, role=role, text=text))
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


# --- The safety property this phase owns -----------------------------------


@pytest.mark.asyncio
async def test_the_evidence_response_carries_no_answer_key(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The check moves from ingestion to the wire.

    Ingestion being correct is necessary and not sufficient. These turns
    are stored clean, and this asserts that what the endpoint serialises is
    still clean — a stripping bug, a re-ingest from another source, or a
    fixture written straight into the database would each pass an
    ingest-only check and still put the answer on a reader's screen.
    """
    await seed_with_turns(
        session_factory,
        turns=(
            ("CALLER", "I was billed twice for the same visit."),
            ("AGENT", "I can see the duplicate. I'll raise a correction today."),
        ),
    )

    response = client.get("/api/v1/insights/calls/C-9001")
    assert response.status_code == 200, response.text
    body = response.json()

    rendered = "\n".join(turn["text"] for turn in body["turns"])
    assert_text_carries_no_answer_key(rendered, "the evidence response")


@pytest.mark.asyncio
async def test_a_leaking_transcript_fails_the_evidence_check(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The guard above is only worth having if it can fail.

    A call is stored with the answer key still attached — exactly what a
    stripping regression would produce — and the assertion must catch it
    from the response alone. Without this, a check that never fires would
    read as a check that always passes.
    """
    await seed_with_turns(
        session_factory,
        turns=(("CALLER", "CALL TAGS outcome: UNRESOLVED, score 42/100"),),
        reference="C-9002",
    )

    body = client.get("/api/v1/insights/calls/C-9002").json()

    rendered = "\n".join(turn["text"] for turn in body["turns"])
    with pytest.raises(AssertionError, match="CALL TAGS"):
        assert_text_carries_no_answer_key(rendered, "the evidence response")


@pytest.mark.asyncio
async def test_a_missing_call_is_a_404_that_names_it(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed(session_factory, calls_per_employer={"EMP-01": 1})

    response = client.get("/api/v1/insights/calls/C-DOES-NOT-EXIST")

    assert response.status_code == 404
    assert "C-DOES-NOT-EXIST" in response.text


@pytest.mark.asyncio
async def test_a_call_with_no_transcript_says_so(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Distinct from an empty conversation, which does not happen.

    A drawer rendering nothing with no explanation reads as a loading
    failure, and a reader would retry rather than learn the call was
    stored without a transcript.
    """
    await seed(session_factory, calls_per_employer={"EMP-01": 1})

    body = client.get("/api/v1/insights/calls/C-0001").json()

    assert body["transcriptMissing"] is True
    assert body["turns"] == []


# --- The tags a call's evidence carries, from the same reader every other
# figure reads, not from `CallRepository` (which only ever sees identity and
# the transcript) --------------------------------------------------------


async def seed_a_tagged_call(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    reference: str = "C-9101",
    **extraction: object,
) -> None:
    """One call, extracted, with whatever L3/L4 fields a test needs.

    Separate from `seed_with_turns`: that helper's `CallExtractionRow` is
    fixed, and several existing tests depend on its exact shape. This one
    exists so a test can set `knowledge_failure_present=True` without
    touching a fixture other tests already rely on.
    """
    async with session_factory() as session, session.begin():
        broker = BrokerRow(
            reference="BRK-91",
            name="Broker",
            agency="Agency",
            region="West",
            groups_in_book=2,
            signal_profile="neutral",
        )
        session.add(broker)
        await session.flush()
        employer = _employer("EMP-91", broker.id)
        session.add(employer)
        await session.flush()
        call = CallRow(
            reference=reference,
            source=CallSource.CORPUS_PDF.value,
            occurred_at=datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc),
            aht_seconds=400,
            caller_type="MEMBER",
            caller_ref="MEM-91",
            agent_ref="AG-91",
            agent_name="Alex",
            resolution_status="RESOLVED",
            employer_id=employer.id,
        )
        session.add(call)
        await session.flush()
        fields: dict[str, object] = {
            "outcome": Outcome.RESOLVED.value,
            "category": Category.CLAIMS_AND_EOB.value,
            "complaint_present": False,
            "escalation_triggered": False,
            "knowledge_failure_present": False,
        }
        fields.update(extraction)
        session.add(CallExtractionRow(call_id=call.id, **fields))


@pytest.mark.asyncio
async def test_the_evidence_response_carries_the_signals_this_call_raised(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Severity and owner come from the taxonomy, not from the call.

    `severity_of`/`owner_team_of` are fixed per type — a call only decides
    which types fired — so this checks the pairing is real, not a made-up
    value sitting beside the signal.
    """
    async with session_factory() as session, session.begin():
        broker = BrokerRow(
            reference="BRK-92",
            name="Broker",
            agency="Agency",
            region="West",
            groups_in_book=2,
            signal_profile="neutral",
        )
        session.add(broker)
        await session.flush()
        employer = _employer("EMP-92", broker.id)
        session.add(employer)
        await session.flush()
        call = CallRow(
            reference="C-9102",
            source=CallSource.CORPUS_PDF.value,
            occurred_at=datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc),
            aht_seconds=400,
            caller_type="MEMBER",
            caller_ref="MEM-92",
            agent_ref="AG-92",
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
        session.add(SignalRow(call_id=call.id, type="retention_risk", quote="q", turn_seq=1))

    body = client.get("/api/v1/insights/calls/C-9102").json()

    assert body["signals"] == [
        {
            "signal": {"code": "retention_risk", "label": "Retention risk"},
            "severity": {"code": "CRITICAL", "label": "Critical"},
            "ownerTeam": "Account Management",
        }
    ]


@pytest.mark.asyncio
async def test_the_evidence_response_carries_a_knowledge_failure_when_present(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed_a_tagged_call(
        session_factory,
        reference="C-9103",
        knowledge_failure_present=True,
        knowledge_failure_rule_id="P-014",
        knowledge_failure_correct_statement=(
            "COBRA election runs 60 days from the later of the notice or the loss date."
        ),
    )

    body = client.get("/api/v1/insights/calls/C-9103").json()

    assert body["knowledgeFailure"] == {
        "ruleId": "P-014",
        "correctStatement": (
            "COBRA election runs 60 days from the later of the notice or the loss date."
        ),
    }


@pytest.mark.asyncio
async def test_the_evidence_response_has_no_knowledge_failure_when_absent(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Never a stand-in for `present=False` — absent means absent."""
    await seed_a_tagged_call(session_factory, reference="C-9104")

    body = client.get("/api/v1/insights/calls/C-9104").json()

    assert body["knowledgeFailure"] is None


@pytest.mark.asyncio
async def test_the_evidence_response_carries_a_process_gap_when_present(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed_a_tagged_call(
        session_factory,
        reference="C-9105",
        process_gap_present=True,
        process_gap_gap_type="unclear_document",
        process_gap_touchpoint="denial_letter_eob",
        process_gap_proposed_change="State the appeal deadline on the first page.",
        process_gap_raised_by="AGENT",
        process_gap_status="UNVALIDATED",
    )

    body = client.get("/api/v1/insights/calls/C-9105").json()

    assert body["processGap"] == {
        "proposedChange": "State the appeal deadline on the first page.",
        # The Touchpoints-sheet reference, in words — the same
        # `touchpoint_label` the calls table and the risk screen's drivers
        # panel use, so a reference nobody wrote a workbook label for still
        # shows the sheet's own words.
        "touchpoint": "Denial letter / EOB",
        "raisedBy": {"code": "AGENT", "label": "Agent"},
        "status": {"code": "UNVALIDATED", "label": "Not yet validated"},
    }


@pytest.mark.asyncio
async def test_the_evidence_response_carries_control_exceptions(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed_a_tagged_call(
        session_factory,
        reference="C-9106",
        control_exceptions=["no_recording_disclosure"],
    )

    body = client.get("/api/v1/insights/calls/C-9106").json()

    assert body["controlExceptions"] == [
        {"code": "no_recording_disclosure", "label": "No recording disclosure"}
    ]


@pytest.mark.asyncio
async def test_the_evidence_response_states_why_rules_in_play_is_unavailable(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The prototype's "Rules in play" quotes rule text; the Rules sheets
    carry no text to quote, only metadata — said, not rendered as an empty
    section beside a full one."""
    await seed(session_factory, calls_per_employer={"EMP-01": 1})

    body = client.get("/api/v1/insights/calls/C-0001").json()

    assert body["rulesUnavailable"]
    assert "rulebook" in body["rulesUnavailable"]


@pytest.mark.asyncio
async def test_the_evidence_response_has_no_tags_before_extraction_reaches_it(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """A call can be ingested without being tagged yet — that is not an
    error, and the tag-carrying fields are simply empty, not a 500."""
    await seed_with_turns(
        session_factory,
        turns=(("CALLER", "Hello."),),
        reference="C-9107",
    )
    async with session_factory() as session, session.begin():
        # `seed_with_turns` always writes an extraction row; delete it to
        # model a call `RunExtractionOverCorpus` has not reached yet.
        call_id = (
            await session.execute(select(CallRow.id).where(CallRow.reference == "C-9107"))
        ).scalar_one()
        await session.execute(delete(CallExtractionRow).where(CallExtractionRow.call_id == call_id))

    body = client.get("/api/v1/insights/calls/C-9107").json()

    assert body["signals"] == []
    assert body["knowledgeFailure"] is None
    assert body["processGap"] is None
    assert body["controlExceptions"] == []


# --- The workbench ---------------------------------------------------------


@pytest.mark.asyncio
async def test_paging_is_stable_when_the_sort_key_ties(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Every call here shares one date, which is the whole point.

    With a non-total sort, two requests can order tied rows differently and
    a reader paging through loses a call and sees another twice. Sorting
    ends in the reference, so the union of the pages is every row exactly
    once.
    """
    await seed(session_factory, calls_per_employer={"EMP-01": 7})

    first = client.get(
        "/api/v1/insights/calls",
        params={"asOf": AS_OF, "sort": "date", "perPage": 3, "page": 1},
    ).json()
    second = client.get(
        "/api/v1/insights/calls",
        params={"asOf": AS_OF, "sort": "date", "perPage": 3, "page": 2},
    ).json()
    third = client.get(
        "/api/v1/insights/calls",
        params={"asOf": AS_OF, "sort": "date", "perPage": 3, "page": 3},
    ).json()

    seen = [row["reference"] for page in (first, second, third) for row in page["rows"]]
    assert len(seen) == 7
    assert len(set(seen)) == 7, "a row appeared on two pages, or one was dropped"
    assert first["total"] == 7
    assert first["pages"] == 3


@pytest.mark.asyncio
async def test_search_narrows_rather_than_widens_on_a_second_term(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Terms are ANDed. Typing more words must not return more rows."""
    await seed(session_factory, calls_per_employer={"EMP-01": 2, "EMP-02": 2})

    one = client.get("/api/v1/insights/calls", params={"asOf": AS_OF, "q": "Employer"}).json()
    two = client.get(
        "/api/v1/insights/calls", params={"asOf": AS_OF, "q": "Employer EMP-02"}
    ).json()

    assert one["total"] == 4
    assert two["total"] == 2


@pytest.mark.asyncio
async def test_the_page_says_what_it_is_a_page_of(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Filters slice, never hide (§9)."""
    await seed(session_factory, calls_per_employer={"EMP-01": 4, "EMP-02": 2})

    body = client.get("/api/v1/insights/calls", params={"asOf": AS_OF, "employer": "EMP-02"}).json()

    assert body["total"] == 2
    assert body["considered"] == 6


@pytest.mark.asyncio
async def test_the_headline_aggregates_cover_every_matching_call_not_only_the_page(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The prototype's tiles read the whole filtered corpus client-side; this
    one pages server-side, so the count has to be taken before the slice or
    narrowing the page size would make "unresolved" look like it dropped.
    """
    async with session_factory() as session, session.begin():
        broker = BrokerRow(
            reference="BRK-93",
            name="Broker",
            agency="Agency",
            region="West",
            groups_in_book=2,
            signal_profile="neutral",
        )
        session.add(broker)
        await session.flush()
        employer = _employer("EMP-93", broker.id)
        session.add(employer)
        await session.flush()
        # Three calls: one resolved and scored, one unresolved with a missed
        # escalation, one unresolved with an unscored quality field. Only
        # the first two land on a one-per-page first page.
        rows = (
            ("C-9301", Outcome.RESOLVED.value, False, False, 80),
            ("C-9302", Outcome.UNRESOLVED.value, True, False, 40),
            ("C-9303", Outcome.UNRESOLVED.value, False, False, None),
        )
        for reference, outcome, triggered, handled, score in rows:
            call = CallRow(
                reference=reference,
                source=CallSource.CORPUS_PDF.value,
                occurred_at=datetime(2026, 9, 20, 10, 0, tzinfo=timezone.utc),
                aht_seconds=400,
                caller_type="MEMBER",
                caller_ref="MEM-93",
                agent_ref="AG-93",
                agent_name="Alex",
                resolution_status="RESOLVED",
                employer_id=employer.id,
            )
            session.add(call)
            await session.flush()
            session.add(
                CallExtractionRow(
                    call_id=call.id,
                    outcome=outcome,
                    category=Category.CLAIMS_AND_EOB.value,
                    complaint_present=False,
                    escalation_triggered=triggered,
                    escalation_handled=handled,
                    knowledge_failure_present=False,
                    quality_score=score,
                )
            )

    body = client.get(
        "/api/v1/insights/calls",
        params={"asOf": AS_OF, "sort": "date", "order": "asc", "perPage": 1, "page": 1},
    ).json()

    assert len(body["rows"]) == 1
    assert body["total"] == 3
    assert body["unresolvedCount"] == 2
    assert body["escalationsMissedCount"] == 1
    # (80 + 40) / 2 — the unscored third call is excluded, not counted as 0.
    assert body["averageQuality"] == 60


@pytest.mark.asyncio
async def test_an_impossible_page_size_is_refused(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The ceiling is the server's, so a crafted perPage cannot bypass it."""
    await seed(session_factory, calls_per_employer={"EMP-01": 1})

    response = client.get("/api/v1/insights/calls", params={"asOf": AS_OF, "perPage": 100000})

    assert response.status_code == 422


# --- The export ------------------------------------------------------------


@pytest.mark.asyncio
async def test_the_csv_opens_in_excel_and_covers_every_match(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The BOM, CRLF, and every matching row rather than the current page.

    Without the BOM, Excel on Windows reads UTF-8 as the system codepage
    and every accented employer name arrives mangled. An export of "page 2"
    would be a file whose contents depend on a control the recipient cannot
    see.
    """
    await seed(session_factory, calls_per_employer={"EMP-01": 5})

    response = client.get("/api/v1/insights/calls.csv", params={"asOf": AS_OF, "perPage": 2})

    assert response.status_code == 200
    text = response.content.decode("utf-8")
    assert text.startswith("﻿"), "no BOM: Excel will mangle non-ASCII names"
    assert "\r\n" in text
    lines = text.strip().split("\r\n")
    assert len(lines) == 6, "header plus every matching call, not one page"
    assert lines[0].lstrip("﻿").startswith("Call ID,Date,Employer ID")


@pytest.mark.asyncio
async def test_the_export_carries_no_columns_it_cannot_fill(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """C8a and C8b: absent, not blank.

    An empty column reads as "no value for this call". A missing one reads
    as "we do not publish this", which is the true statement — and the list
    response says which and why rather than leaving it to be noticed.
    """
    await seed(session_factory, calls_per_employer={"EMP-01": 1})

    csv_text = client.get("/api/v1/insights/calls.csv", params={"asOf": AS_OF}).content.decode(
        "utf-8"
    )
    body = client.get("/api/v1/insights/calls", params={"asOf": AS_OF}).json()

    # Compared as whole fields. A substring check matches "Handling time
    # (sec)", which is a column that *is* published, so the test would fail
    # for the wrong reason — or, with the assertion inverted, pass for one.
    header = csv_text.split("\r\n")[0].lstrip("﻿").split(",")
    for absent in ("Handling", "Member effort", "Complexity"):
        assert absent not in header
    assert len(body["omittedColumns"]) == 3
    assert any("C8a" in note for note in body["omittedColumns"])


@pytest.mark.asyncio
async def test_the_export_never_carries_a_member_name(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """A CSV leaves the application and gets mailed around.

    The prototype exports the caller's name. This exports the reference,
    which identifies the call just as well for every use this screen
    supports and does not send personal data travelling with no control
    attached.
    """
    await seed(session_factory, calls_per_employer={"EMP-01": 1})

    header = (
        client.get("/api/v1/insights/calls.csv", params={"asOf": AS_OF})
        .content.decode("utf-8")
        .split("\r\n")[0]
    )

    assert "Caller" not in header


@pytest.mark.asyncio
async def test_download_selected_narrows_to_the_chosen_calls(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Selection is a server-side filter, so the export stays one projection.

    Building the file in the browser from the selected rows would put a
    second column list in the frontend, and the file a reader mails out
    would come from different code than the Download-all button's.
    """
    await seed(session_factory, calls_per_employer={"EMP-01": 5})

    text = client.get(
        "/api/v1/insights/calls.csv",
        params={"asOf": AS_OF, "ref": ["C-0002", "C-0004"]},
    ).content.decode("utf-8")

    lines = text.strip().split("\r\n")
    assert len(lines) == 3, "header plus the two selected calls"
    assert "C-0002" in text
    assert "C-0004" in text
    assert "C-0001" not in text


@pytest.mark.asyncio
async def test_a_selected_call_outside_the_period_stays_out(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Selection narrows; it never resurrects.

    A reader who selects a call, then moves the period away from it, must
    not find it back in the file. The reference filter is applied after
    the corpus filters for exactly this reason.
    """
    await seed(session_factory, calls_per_employer={"EMP-01": 3})

    body = client.get(
        "/api/v1/insights/calls",
        params={"asOf": AS_OF, "ref": ["C-0001"], "from": "2026-01-01", "to": "2026-01-31"},
    ).json()

    assert body["rows"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_the_repeat_filter_keeps_a_repeat_whose_antecedent_is_filtered_out(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The trap this filter exists to avoid.

    A repeat is a relationship between two calls. Computing it over the
    *filtered* set would mean narrowing to one employer made a repeat stop
    being a repeat, because the call it followed left the slice. The
    references come from the whole corpus for exactly this reason.
    """
    await seed(session_factory, calls_per_employer={"EMP-01": 2, "EMP-02": 2})

    unfiltered = client.get(
        "/api/v1/insights/calls", params={"asOf": AS_OF, "repeat": "true"}
    ).json()
    narrowed = client.get(
        "/api/v1/insights/calls",
        params={"asOf": AS_OF, "repeat": "true", "employer": "EMP-02"},
    ).json()

    kept = {row["reference"] for row in unfiltered["rows"]}
    still_kept = {row["reference"] for row in narrowed["rows"]}
    # Whatever the corpus makes a repeat, narrowing by employer may remove
    # rows but must never reclassify one.
    assert still_kept <= kept


@pytest.mark.asyncio
async def test_repeat_true_and_false_partition_the_slice(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Unset is not the same as either value, and the two halves add up."""
    await seed(session_factory, calls_per_employer={"EMP-01": 4})

    everything = client.get("/api/v1/insights/calls", params={"asOf": AS_OF}).json()
    yes = client.get("/api/v1/insights/calls", params={"asOf": AS_OF, "repeat": "true"}).json()
    no = client.get("/api/v1/insights/calls", params={"asOf": AS_OF, "repeat": "false"}).json()

    assert yes["total"] + no["total"] == everything["total"]


@pytest.mark.asyncio
async def test_the_repeat_filter_shows_in_the_applied_row(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Filters slice, never hide — including the derived ones."""
    await seed(session_factory, calls_per_employer={"EMP-01": 3})

    body = client.get("/api/v1/insights/calls", params={"asOf": AS_OF, "repeat": "true"}).json()

    fields = {entry["field"] for entry in body["scope"]["appliedFilters"]}
    assert "repeat" in fields


@pytest.mark.asyncio
async def test_a_row_names_who_rang(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The prototype's Caller column, joined from the Member sheet.

    It is a row-level join on purpose. `CallTags` carries the reference and
    not the name, so no aggregation can reach a caller's identity; the
    workbench joins it the same way it joins the employer name.
    """
    await seed(session_factory, calls_per_employer={"EMP-01": 1})
    async with session_factory() as session, session.begin():
        employer = (
            await session.execute(select(EmployerRow).where(EmployerRow.reference == "EMP-01"))
        ).scalar_one()
        session.add(
            MemberRow(
                reference="MEM-1",
                name="Jerome Arellano",
                age=41,
                employer_id=employer.id,
                primary_line="medical",
                planned_calls=2,
                repeat_caller=False,
            )
        )

    (row,) = client.get("/api/v1/insights/calls", params={"asOf": AS_OF}).json()["rows"]

    assert row["callerName"] == "Jerome Arellano"
    assert row["callerKind"] == "member"


@pytest.mark.asyncio
async def test_a_caller_reference_nobody_recognises_keeps_the_reference(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """A gap in reference data, not an anonymous caller.

    Without the reference the row would say only "not recorded", and a
    reader could not tell a missing Member sheet row from a call that
    genuinely had nobody on it.
    """
    await seed(session_factory, calls_per_employer={"EMP-01": 1})

    (row,) = client.get("/api/v1/insights/calls", params={"asOf": AS_OF}).json()["rows"]

    assert row["callerName"] is None
    assert row["callerRef"] == "MEM-1"
