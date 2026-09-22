"""SQLAlchemy implementation of `CallRepository`.

Upsert by reference, like `SqlReferenceRepository`; one `IngestJobRow` per
run, so a batch's own outcome (how many resolved, and why the rest didn't)
is itself a queryable record, not just console output.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports.call_repository import CallRepository, IngestCounts
from application.ports.clock import Clock
from domain.entities.ingested_call import IngestedCall
from domain.value_objects.call_resolution_status import CallResolutionStatus
from infrastructure.persistence.tables import (
    CallRow,
    CallTurnRow,
    EmployerContactRow,
    EmployerRow,
    IngestJobRow,
    MemberRow,
)

_JOB_KIND = "corpus_pdf"


class SqlCallRepository(CallRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], clock: Clock) -> None:
        self._session_factory = session_factory
        self._clock = clock

    async def upsert_all(self, calls: tuple[IngestedCall, ...]) -> IngestCounts:
        counts = _tally(calls)

        async with self._session_factory() as session, session.begin():
            job = IngestJobRow(
                kind=_JOB_KIND,
                status="RUNNING",
                message=None,
                started_at=self._clock.now(),
                finished_at=None,
                result_call_reference=None,
            )
            session.add(job)

            for call in calls:
                await self._upsert_call(session, call)

            job.status = "COMPLETED"
            job.finished_at = self._clock.now()
            job.message = (
                f"{counts.total} calls: {counts.resolved} resolved, "
                f"{counts.caller_unresolved} caller-unresolved, "
                f"{counts.agent_unknown} agent-unknown, "
                f"{counts.speaker_unresolved} speaker-unresolved"
            )

        return counts

    async def _upsert_call(self, session: AsyncSession, call: IngestedCall) -> None:
        row = (
            await session.execute(select(CallRow).where(CallRow.reference == call.reference))
        ).scalar_one_or_none()
        if row is None:
            row = CallRow(reference=call.reference)
            session.add(row)

        transcript = call.transcript
        row.source = transcript.source.value if transcript else ""
        row.occurred_at = transcript.occurred_at if transcript else None
        row.aht_seconds = transcript.aht_seconds if transcript else None
        row.caller_type = call.caller_type.value
        row.caller_ref = call.caller_ref
        row.agent_ref = call.agent_ref
        row.resolution_status = call.resolution_status.value
        row.resolution_reason = call.resolution_reason
        row.member_id = await self._id_by_reference(session, MemberRow, call.member_ref)
        row.employer_contact_id = await self._id_by_reference(
            session, EmployerContactRow, call.employer_contact_ref
        )
        row.employer_id = await self._id_by_reference(session, EmployerRow, call.employer_ref)

        await session.flush()  # need row.id before writing turns

        # Deleted and re-inserted via plain statements rather than through
        # the `turns` relationship collection: touching that collection on
        # a row that came from a query would lazy-load it, which raises
        # MissingGreenlet under an async session outside the query's own
        # await scope.
        await session.execute(delete(CallTurnRow).where(CallTurnRow.call_id == row.id))
        if transcript is not None:
            session.add_all(
                CallTurnRow(call_id=row.id, sequence=sequence, role=turn.role.value, text=turn.text)
                for sequence, turn in enumerate(transcript.turns)
            )

    async def _id_by_reference(
        self, session: AsyncSession, row_type: type, reference: str | None
    ) -> int | None:
        if reference is None:
            return None
        result = await session.execute(
            select(row_type.id).where(row_type.reference == reference)  # type: ignore[attr-defined]
        )
        return result.scalar_one_or_none()


def _tally(calls: tuple[IngestedCall, ...]) -> IngestCounts:
    def count(status: CallResolutionStatus) -> int:
        return sum(1 for c in calls if c.resolution_status is status)

    return IngestCounts(
        total=len(calls),
        resolved=count(CallResolutionStatus.RESOLVED),
        caller_unresolved=count(CallResolutionStatus.CALLER_UNRESOLVED),
        agent_unknown=count(CallResolutionStatus.AGENT_UNKNOWN),
        speaker_unresolved=count(CallResolutionStatus.SPEAKER_UNRESOLVED),
    )
