"""`SqlCallRepository` against a real (temporary) SQLite database: idempotent
upsert, turns persisted in order, and every resolution outcome writes a
call — nothing dropped.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from domain.entities.ingested_call import IngestedCall
from domain.entities.transcript import Transcript
from domain.entities.turn import Turn
from domain.value_objects.call_resolution_status import CallResolutionStatus
from domain.value_objects.call_source import CallSource
from domain.value_objects.caller_type import CallerType
from domain.value_objects.speaker_role import SpeakerRole
from infrastructure.persistence.repositories.call_repository import SqlCallRepository
from infrastructure.persistence.tables import CallRow, CallTurnRow, IngestJobRow
from infrastructure.system_clock import SystemClock

_TRANSCRIPT = Transcript(
    reference="C-0001",
    source=CallSource.CORPUS_PDF,
    occurred_at=datetime(2026, 7, 6, 9, 14, tzinfo=timezone.utc),
    aht_seconds=380,
    caller_type=CallerType.MEMBER,
    caller_ref="CB-7700205",
    agent_ref="AGT-01",
    agent_name="Sarah Whitlock",
    turns=(
        Turn(role=SpeakerRole.AGENT, text="Hello."),
        Turn(role=SpeakerRole.CALLER, text="Hi."),
    ),
)

_RESOLVED_CALL = IngestedCall(
    reference="C-0001",
    caller_type=CallerType.MEMBER,
    caller_ref="CB-7700205",
    agent_ref="AGT-01",
    transcript=_TRANSCRIPT,
    resolution_status=CallResolutionStatus.RESOLVED,
    resolution_reason=None,
    member_ref=None,  # no reference data seeded in this test — FKs stay null
    employer_contact_ref=None,
    employer_ref=None,
)

_UNRESOLVED_CALL = IngestedCall(
    reference="C-0002",
    caller_type=CallerType.MEMBER,
    caller_ref="CB-1",
    agent_ref="AGT-99",
    transcript=None,
    resolution_status=CallResolutionStatus.SPEAKER_UNRESOLVED,
    resolution_reason="expected exactly two speakers, found 1: ['Sarah']",
    member_ref=None,
    employer_contact_ref=None,
    employer_ref=None,
)


async def test_persists_every_call_regardless_of_resolution(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    repository = SqlCallRepository(session_factory, SystemClock())

    counts = await repository.upsert_all((_RESOLVED_CALL, _UNRESOLVED_CALL))

    assert counts.total == 2
    assert counts.resolved == 1
    assert counts.speaker_unresolved == 1

    async with session_factory() as session:
        total = (await session.execute(select(func.count()).select_from(CallRow))).scalar_one()
        assert total == 2


async def test_unresolved_call_is_persisted_with_no_transcript_but_a_reason(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    repository = SqlCallRepository(session_factory, SystemClock())
    await repository.upsert_all((_UNRESOLVED_CALL,))

    async with session_factory() as session:
        row = (
            await session.execute(select(CallRow).where(CallRow.reference == "C-0002"))
        ).scalar_one()
        assert row.resolution_status == CallResolutionStatus.SPEAKER_UNRESOLVED.value
        assert row.resolution_reason == _UNRESOLVED_CALL.resolution_reason
        assert row.occurred_at is None
        assert row.turns == []


async def test_turns_are_persisted_in_order(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    repository = SqlCallRepository(session_factory, SystemClock())
    await repository.upsert_all((_RESOLVED_CALL,))

    async with session_factory() as session:
        turns = (
            (
                await session.execute(
                    select(CallTurnRow)
                    .join(CallRow, CallTurnRow.call_id == CallRow.id)
                    .where(CallRow.reference == "C-0001")
                    .order_by(CallTurnRow.sequence)
                )
            )
            .scalars()
            .all()
        )
        assert [t.role for t in turns] == [SpeakerRole.AGENT.value, SpeakerRole.CALLER.value]
        assert [t.text for t in turns] == ["Hello.", "Hi."]


async def test_re_ingesting_replaces_turns_without_duplicating_the_call(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    repository = SqlCallRepository(session_factory, SystemClock())
    await repository.upsert_all((_RESOLVED_CALL,))
    await repository.upsert_all((_RESOLVED_CALL,))

    async with session_factory() as session:
        call_count = (await session.execute(select(func.count()).select_from(CallRow))).scalar_one()
        turn_count = (
            await session.execute(select(func.count()).select_from(CallTurnRow))
        ).scalar_one()
        assert call_count == 1
        assert turn_count == 2  # not 4 — turns were replaced, not appended


async def test_writes_one_ingest_job_per_run(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    repository = SqlCallRepository(session_factory, SystemClock())
    await repository.upsert_all((_RESOLVED_CALL, _UNRESOLVED_CALL))

    async with session_factory() as session:
        job = (await session.execute(select(IngestJobRow))).scalar_one()
        assert job.kind == "corpus_pdf"
        assert job.status == "COMPLETED"
        assert job.finished_at is not None
        assert "1 resolved" in (job.message or "")
