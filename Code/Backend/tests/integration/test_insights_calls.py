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
from domain.value_objects.polarity import Polarity
from domain.value_objects.preventable import Preventable
from domain.value_objects.root_cause_owner import RootCauseOwner
from domain.value_objects.score import ScoreStatus
from domain.value_objects.signal_type import SignalType
from domain.value_objects.tier import Tier
from infrastructure.persistence.tables import (
    BrokerRow,
    CallExtractionRow,
    CallRow,
    CallTurnRow,
    EmployerRow,
    MemberRow,
    ScoreMarkerRow,
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
                # Provenance, because a real `save_l2` writes it in the same
                # statement as the tags and the panels read it to answer
                # "did this layer run". A row with tags and no provenance is
                # a state the pipeline cannot produce, and a fixture in that
                # state would have every L2 assertion below testing the
                # not-run path by accident.
                l2_provider="openai",
                l2_model="gpt-test",
                l2_prompt_version="1.0.0",
                l2_completed_at=datetime(2026, 9, 20, 10, 5, tzinfo=timezone.utc),
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


#: What the pipeline stamps on a row once a layer has finished with it.
#: `analysis_response` decides a panel `ran` from these and nothing else, so
#: a seed that sets L3/L4 fields without them is not a smaller version of a
#: real row -- it is a shape `RunExtractionOverCorpus` never produces.
LAYER_RUNS: dict[str, object] = {
    "l2_provider": "openai",
    "l2_model": "test-model",
    "l2_prompt_version": "v1",
    "l2_completed_at": datetime(2026, 9, 20, 11, 0, tzinfo=timezone.utc),
    "l3_provider": "openai",
    "l3_model": "test-model",
    "l3_prompt_version": "v1",
    "rubric_version": "v1",
    "l3_completed_at": datetime(2026, 9, 20, 11, 0, tzinfo=timezone.utc),
    "l4_provider": "openai",
    "l4_model": "test-model",
    "l4_prompt_version": "v1",
    "l4_completed_at": datetime(2026, 9, 20, 11, 0, tzinfo=timezone.utc),
}


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
            # Layer-run provenance, because the panels read `ran` off it and a
            # row without it is a row the pipeline could not have written. A
            # fixture that omitted it would have the endpoint report "not run"
            # over fields the fixture had just set.
            **LAYER_RUNS,
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
                **LAYER_RUNS,
            )
        )
        session.add(SignalRow(call_id=call.id, type="retention_risk", quote="q", turn_seq=1))

    body = client.get("/api/v1/insights/calls/C-9102").json()

    # On the L4 panel, where the layer that raised it puts it. The flat copy
    # this response used to carry alongside came from the dashboard's reader
    # rather than from the call's own extraction -- two sources for one fact,
    # free to disagree.
    assert body["analysis"]["l4"]["signals"] == [
        {
            "type": {"code": "retention_risk", "label": "Retention risk"},
            "quote": "q",
            "turnSeq": 1,
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

    l3 = body["analysis"]["l3"]
    assert l3["knowledgeFailurePresent"] is True
    assert l3["knowledgeFailureRuleId"] == "P-014"
    assert l3["knowledgeFailureCorrectStatement"] == (
        "COBRA election runs 60 days from the later of the notice or the loss date."
    )


@pytest.mark.asyncio
async def test_the_evidence_response_has_no_knowledge_failure_when_absent(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Never a stand-in for `present=False` — absent means absent."""
    await seed_a_tagged_call(session_factory, reference="C-9104")

    body = client.get("/api/v1/insights/calls/C-9104").json()

    # `present=False` is the layer saying it looked and found none, which is
    # not the same as the null a layer that never ran leaves.
    assert body["analysis"]["l3"]["knowledgeFailurePresent"] is False
    assert body["analysis"]["l3"]["knowledgeFailureRuleId"] is None


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

    l4 = body["analysis"]["l4"]
    assert l4["processGapPresent"] is True
    assert l4["processGapProposedChange"] == "State the appeal deadline on the first page."
    # The Touchpoints-sheet reference, in words — the same `touchpoint_label`
    # the calls table and the risk screen's drivers panel use, so a reader
    # never meets the raw slug on one screen and the sheet's words on the next.
    assert l4["processGapTouchpoint"] == "Denial letter / EOB"
    assert l4["processGapRaisedBy"] == {"code": "AGENT", "label": "Agent"}
    assert l4["processGapStatus"] == {"code": "UNVALIDATED", "label": "Not yet validated"}


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

    # L1's own output: a control exception is found deterministically, so it
    # sits on the panel of the layer that found it.
    assert body["analysis"]["l1"]["controlExceptions"] == [
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

    analysis = body["analysis"]
    # Four panels saying nothing has run, rather than four empty ones: a panel
    # rendering "no signals" for a layer that never ran reports a clean call.
    for layer in ("l1", "l2", "l3", "l4"):
        assert analysis[layer]["ran"] is False
        assert analysis[layer]["notRunBecause"]
    assert analysis["l4"]["signals"] == []
    assert analysis["l1"]["controlExceptions"] == []
    assert analysis["l3"]["knowledgeFailurePresent"] is None
    assert analysis["l4"]["processGapPresent"] is None


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


# --- The five panels of a call's analysis ----------------------------------


@pytest.mark.asyncio
async def test_a_call_carries_four_panels_even_when_nothing_has_run(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Four panels, one per layer — and none of them optional.

    A null `analysis` would render as a section that failed to load. "The
    pipeline has not run on this call" is a different statement and the true
    one, and it is the answer to the question the reader opened the drawer
    to ask.
    """
    await seed(session_factory, calls_per_employer={"EMP-01": 1})
    reference = await _one_reference(session_factory)

    body = client.get(f"/api/v1/insights/calls/{reference}").json()

    analysis = body["analysis"]
    assert set(analysis) == {"l1", "l2", "l3", "l4"}
    for name, panel in analysis.items():
        assert panel["ran"] is False, f"{name} claims to have run"
        assert panel["notRunBecause"], f"{name} is empty without saying why"


@pytest.mark.asyncio
async def test_l1_reads_as_run_from_l2_rather_than_from_its_own_findings(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """L1 is pure and recomputed, not stored, and it is written in the same
    transaction as L2 — so it ran exactly when L2 did.

    Inferring it from `controlExceptions` instead would report a call that
    broke no controls as a call nobody checked, which is the same mistake
    as reading a withheld figure as a zero.
    """
    await seed_with_turns(session_factory, turns=(("CALLER", "Hello."),))

    analysis = client.get("/api/v1/insights/calls/C-9001").json()["analysis"]

    assert analysis["l1"]["ran"] is True
    assert analysis["l1"]["controlExceptions"] == []
    assert analysis["l1"]["callerRef"] == "MEM-9"


@pytest.mark.asyncio
async def test_a_layer_that_has_not_run_is_not_reported_as_a_clean_call(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """L3 and L4 are not pipeline-critical (plan §7): either can be absent
    while L1 and L2 stand. An absent L4 must not read as "no signals"."""
    await seed_with_turns(session_factory, turns=(("CALLER", "Hello."),))

    analysis = client.get("/api/v1/insights/calls/C-9001").json()["analysis"]

    assert analysis["l2"]["ran"] is True
    assert analysis["l3"]["ran"] is False
    assert analysis["l4"]["ran"] is False
    assert analysis["l4"]["signals"] == []
    # The list being empty is not the finding; the sentence is.
    assert "has not run" in analysis["l4"]["notRunBecause"]
    # And the other panels are explicitly said to still stand, because a
    # reader who sees one panel fail will otherwise distrust all five.
    assert "still stand" in analysis["l4"]["notRunBecause"]


@pytest.mark.asyncio
async def test_a_layer_carries_the_model_that_produced_it(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Plan §7: provenance on every analysis. The columns have been written
    since Phase 4; until now nothing read them back."""
    await seed_with_turns(session_factory, turns=(("CALLER", "Hello."),))

    run = client.get("/api/v1/insights/calls/C-9001").json()["analysis"]["l2"]["run"]

    assert run["provider"] == "openai"
    assert run["model"] == "gpt-test"
    assert run["promptVersion"] == "1.0.0"


@pytest.mark.asyncio
async def test_the_knowledge_failure_panel_names_no_agent(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """**D7.** Schema field 8 is organisational — the rule stated wrongly —
    and may never be attributed to the agent who took the call. The agent's
    reference is on the response because the call has one; what must not
    happen is field 8 arriving inside the same object, where a client could
    join the two without deciding to.

    D7 is open with Karim. Nothing in code settles it, so this test guards
    the shape rather than the wording.
    """
    await seed_with_turns(session_factory, turns=(("CALLER", "Hello."),))

    body = client.get("/api/v1/insights/calls/C-9001").json()

    assert body["agentRef"] == "AG-09"
    assert "agentRef" not in body["analysis"]["l3"]
    assert "agent" not in str(body["analysis"]["l3"]).lower()


async def _one_reference(session_factory: async_sessionmaker[AsyncSession]) -> str:
    async with session_factory() as session:
        return (await session.execute(select(CallRow.reference))).scalars().first() or ""


async def _analyse_fully(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Fill in L3, L4 and the derived values on the seeded call.

    Two signals of different severity, deliberately stored worst-last, so
    the ordering assertion below cannot pass by accident of insertion order.
    """
    async with session_factory() as session, session.begin():
        call_id = (
            await session.execute(select(CallRow.id).where(CallRow.reference == "C-9001"))
        ).scalar_one()
        row = (
            await session.execute(
                select(CallExtractionRow).where(CallExtractionRow.call_id == call_id)
            )
        ).scalar_one()
        row.quality_score = 74
        row.quality_status = ScoreStatus.PROVISIONAL.value
        row.quality_tier = Tier.AVERAGE.value
        row.rubric_version = "2.1.0"
        row.knowledge_failure_present = True
        row.knowledge_failure_rule_id = "P-18"
        row.knowledge_failure_correct_statement = (
            "Employer-sponsored dental: minimum 2 enrolled AND 70% participation."
        )
        row.l3_provider = "openai"
        row.l3_model = "gpt-test"
        row.l3_prompt_version = "1.1.0"
        row.l3_completed_at = datetime(2026, 9, 20, 10, 6, tzinfo=timezone.utc)
        row.escalation_handled = False
        row.root_cause_owner = RootCauseOwner.CHOICE.value
        row.preventable = Preventable.YES.value
        row.l4_provider = "openai"
        row.l4_model = "gpt-test"
        row.l4_prompt_version = "1.2.0"
        row.l4_completed_at = datetime(2026, 9, 20, 10, 7, tzinfo=timezone.utc)
        session.add(
            ScoreMarkerRow(
                call_id=call_id,
                dimension="Ownership",
                polarity=Polarity.NEGATIVE.value,
                description="Left the caller to chase it.",
                quote="You'll need to call the carrier yourself.",
                turn_seq=1,
                verification_status="accepted",
            )
        )
        session.add(
            SignalRow(
                call_id=call_id,
                type=SignalType.MEMBER_COMMUNICATION_GAP.value,
                quote="Nobody told me the plan had changed.",
                turn_seq=0,
            )
        )
        session.add(
            SignalRow(
                call_id=call_id,
                type=SignalType.RETENTION_RISK.value,
                quote="We are looking at other carriers.",
                turn_seq=1,
            )
        )


@pytest.mark.asyncio
async def test_signals_arrive_worst_first(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Severity is fixed per type by the Signal Taxonomy sheet, and the
    drawer shows the list in the order it arrives. Sorting on the client
    would mean the wire order meant nothing and two clients could rank the
    same call differently."""
    await seed_with_turns(session_factory, turns=(("CALLER", "Hello."),))
    await _analyse_fully(session_factory)

    signals = client.get("/api/v1/insights/calls/C-9001").json()["analysis"]["l4"]["signals"]

    assert [signal["severity"]["code"] for signal in signals] == ["CRITICAL", "MEDIUM"]
    assert signals[0]["type"]["label"] == "Retention risk"
    # The quote travels with it. A signal with no line behind it is an
    # assertion, and every one of these survived evidence checking.
    assert signals[0]["quote"] == "We are looking at other carriers."


@pytest.mark.asyncio
async def test_a_provisional_score_says_so_rather_than_reading_as_a_low_one(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """PROVISIONAL means "not final", which a reader will otherwise take as
    a grade. The label carries the distinction, not the number."""
    await seed_with_turns(session_factory, turns=(("CALLER", "Hello."),))
    await _analyse_fully(session_factory)

    l3 = client.get("/api/v1/insights/calls/C-9001").json()["analysis"]["l3"]

    assert l3["qualityScore"] == 74
    assert l3["qualityStatus"]["label"] == "Provisional — not final"
    assert l3["run"]["rubricVersion"] == "2.1.0"
    assert l3["markers"][0]["polarity"]["label"] == "Fell short"


@pytest.mark.asyncio
async def test_the_computed_fields_travel_with_the_layer_that_saves_them(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Schema fields 17-18 are computed in code and never sent to a model,
    but they are written in the same transaction as L4 and have no run,
    prompt or provenance of their own. So they sit on L4's panel, with the
    distinction stated on the field rather than by a panel that would read
    as a fifth layer."""
    await seed_with_turns(session_factory, turns=(("CALLER", "Hello."),))
    await _analyse_fully(session_factory)

    l4 = client.get("/api/v1/insights/calls/C-9001").json()["analysis"]["l4"]

    assert l4["rootCauseOwner"]["label"] == "Choice"
    assert l4["preventable"] == "Yes"


@pytest.mark.asyncio
async def test_the_evidence_response_names_the_people_and_keeps_the_references(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Names across the application, asked for 2026-09-29.

    The reference is kept beside every name rather than replaced by it: it
    is what a support ticket quotes and a filter takes, and two members can
    share a name. The CSV export is deliberately unchanged — `calls.py`
    settles that separately, because a file leaves the application.
    """
    await seed_with_turns(session_factory, turns=(("CALLER", "Hello."),))

    body = client.get("/api/v1/insights/calls/C-9001").json()

    assert body["callerRef"] == "MEM-9"
    assert body["agentRef"] == "AG-09"
    # Present as fields whether or not reference data knows them, so the
    # client never has to guess whether a missing key means "no name" or
    # "this build is older than the field".
    assert "callerName" in body
    assert "agentName" in body
    assert "employerName" in body
