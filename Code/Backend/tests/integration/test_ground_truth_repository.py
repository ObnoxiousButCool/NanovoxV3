"""`SqlGroundTruthRepository` against a real (temporary) SQLite database:
idempotent upsert keyed by call reference, JSON-valued lists round-tripping,
and a tracker row whose call has not been ingested reported rather than
written.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from domain.entities.ground_truth import GroundTruth, GroundTruthSignal
from domain.entities.ingested_call import IngestedCall
from domain.entities.transcript import Transcript
from domain.entities.turn import Turn
from domain.value_objects.call_resolution_status import CallResolutionStatus
from domain.value_objects.call_source import CallSource
from domain.value_objects.caller_type import CallerType
from domain.value_objects.category import Category
from domain.value_objects.outcome import Outcome
from domain.value_objects.speaker_role import SpeakerRole
from infrastructure.persistence.repositories.call_repository import SqlCallRepository
from infrastructure.persistence.repositories.ground_truth_repository import (
    SqlGroundTruthRepository,
)
from infrastructure.persistence.tables import GroundTruthRow
from infrastructure.system_clock import SystemClock

_TRUTH = GroundTruth(
    reference="C-0001",
    category=Category.CLAIMS_AND_EOB,
    archetype="Competent and resolved",
    rule_refs=("C-12", "P-14"),
    outcome=Outcome.RESOLVED,
    score=91,
    product_line="dental",
    touchpoint="denial_letter_eob",
    aht_seconds=380,
    complaint_present=True,
    complaint_attributed_to="CHOICE",
    signals=(
        GroundTruthSignal(
            code="member_communication_gap",
            severity="MEDIUM",
            owner_team="Member Communications",
        ),
    ),
    control_exceptions=("no_recording_disclosure",),
    escalation_triggered=True,
    escalation_type="authority_limit",
    escalation_requested_by_caller=True,
    escalation_handled=True,
    knowledge_failure_present=True,
    knowledge_failure_rule_ref="C-12",
    knowledge_failure_statement="major-service waiting periods do not apply",
    intent_type="expansion",
    intent_evidence="verbatim, turn 14",
    process_gap_present=True,
    process_gap_description="denial letter should name the waiting period",
    broker_named_present=True,
    broker_named_broker_ref="BRK-01",
    broker_named_sentiment="ADVERSE",
    repeat_of_reference="C-0002",
    repeat_of_note="06 Jul | closed unresolved",
)


async def _ingest_call(session_factory: async_sessionmaker[AsyncSession], reference: str) -> None:
    """A call for the answer key to hang off — `ground_truth.call_id` is a
    foreign key, so there is nothing to write without one.
    """
    await SqlCallRepository(session_factory, SystemClock()).upsert_all(
        (
            IngestedCall(
                reference=reference,
                caller_type=CallerType.MEMBER,
                caller_ref="CB-7700205",
                agent_ref="AGT-01",
                transcript=Transcript(
                    reference=reference,
                    source=CallSource.CORPUS_PDF,
                    occurred_at=datetime(2026, 7, 6, 9, 14, tzinfo=UTC),
                    aht_seconds=380,
                    caller_type=CallerType.MEMBER,
                    caller_ref="CB-7700205",
                    agent_ref="AGT-01",
                    agent_name="Sarah Whitlock",
                    turns=(Turn(role=SpeakerRole.AGENT, text="Hello."),),
                ),
                resolution_status=CallResolutionStatus.RESOLVED,
                resolution_reason=None,
                member_ref=None,
                employer_contact_ref=None,
                employer_ref=None,
            ),
        )
    )


async def test_writes_one_row_per_call(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _ingest_call(session_factory, "C-0001")

    counts = await SqlGroundTruthRepository(session_factory, SystemClock()).upsert((_TRUTH,))

    assert counts.written == 1
    assert counts.unmatched == ()


async def test_every_field_round_trips(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _ingest_call(session_factory, "C-0001")
    await SqlGroundTruthRepository(session_factory, SystemClock()).upsert((_TRUTH,))

    async with session_factory() as session:
        row = (await session.execute(select(GroundTruthRow))).scalar_one()

    assert row.category == "Claims & EOB"
    assert row.outcome == "RESOLVED"
    assert row.score == 91
    assert row.rule_refs == ["C-12", "P-14"]
    assert row.signals == [
        {
            "code": "member_communication_gap",
            "severity": "MEDIUM",
            "owner_team": "Member Communications",
        }
    ]
    assert row.control_exceptions == ["no_recording_disclosure"]
    assert row.escalation_handled is True
    assert row.knowledge_failure_rule_ref == "C-12"
    assert row.repeat_of_reference == "C-0002"
    assert row.repeat_of_note == "06 Jul | closed unresolved"


async def test_enum_fields_are_stored_by_value_not_by_name(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """`call_extractions` stores `Outcome.value`; Phase 5 compares the two
    columns directly, so this one has to match.
    """
    await _ingest_call(session_factory, "C-0001")
    await SqlGroundTruthRepository(session_factory, SystemClock()).upsert(
        (GroundTruth(reference="C-0001", outcome=Outcome.PARTIALLY_RESOLVED),)
    )

    async with session_factory() as session:
        row = (await session.execute(select(GroundTruthRow))).scalar_one()

    assert row.outcome == "PARTIALLY_RESOLVED"


async def test_re_importing_updates_in_place_rather_than_duplicating(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await _ingest_call(session_factory, "C-0001")
    repository = SqlGroundTruthRepository(session_factory, SystemClock())

    await repository.upsert((_TRUTH,))
    counts = await repository.upsert(
        (GroundTruth(reference="C-0001", outcome=Outcome.UNRESOLVED, score=44),)
    )

    async with session_factory() as session:
        total = (
            await session.execute(select(func.count()).select_from(GroundTruthRow))
        ).scalar_one()
        row = (await session.execute(select(GroundTruthRow))).scalar_one()

    assert counts.written == 1
    assert total == 1
    assert (row.outcome, row.score) == ("UNRESOLVED", 44)
    # Re-import replaces the whole answer, it does not merge: the revised
    # row cites no rules, so the stored row must not still carry the old two.
    assert row.rule_refs == []


async def test_a_tracker_row_with_no_ingested_call_is_reported_not_written(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """There is nowhere to hang it, and inventing a call to hold an answer
    would put a fabricated row in the fact table.
    """
    await _ingest_call(session_factory, "C-0001")

    counts = await SqlGroundTruthRepository(session_factory, SystemClock()).upsert(
        (_TRUTH, GroundTruth(reference="C-9999"))
    )

    async with session_factory() as session:
        total = (
            await session.execute(select(func.count()).select_from(GroundTruthRow))
        ).scalar_one()

    assert counts.written == 1
    assert counts.unmatched == ("C-9999",)
    assert total == 1


async def test_an_empty_import_writes_nothing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    counts = await SqlGroundTruthRepository(session_factory, SystemClock()).upsert(())

    assert counts == type(counts)(written=0, unmatched=())
