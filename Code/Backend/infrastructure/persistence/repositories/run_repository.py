"""SQLAlchemy implementation of `RunRepository`."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports.run_repository import RunItemRecord, RunRecord, RunRepository
from domain.errors import NotFoundError
from domain.value_objects.run_status import RunItemStatus, RunStatus
from infrastructure.persistence.tables import RunItemRow, RunRow


class SqlRunRepository(RunRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(
        self, call_references: Sequence[str], *, provider: str, model: str, created_at: datetime
    ) -> int:
        async with self._session_factory() as session, session.begin():
            run = RunRow(
                status=RunStatus.PENDING.value,
                provider=provider,
                model=model,
                created_at=created_at,
                started_at=None,
                finished_at=None,
            )
            session.add(run)
            await session.flush()  # need run.id before writing items

            session.add_all(
                RunItemRow(
                    run_id=run.id,
                    call_reference=reference,
                    status=RunItemStatus.PENDING.value,
                    error=None,
                )
                for reference in call_references
            )
            await session.flush()
            return run.id

    async def get(self, run_id: int) -> RunRecord | None:
        async with self._session_factory() as session:
            row = (
                await session.execute(select(RunRow).where(RunRow.id == run_id))
            ).scalar_one_or_none()
            if row is None:
                return None
            return _to_record(row)

    async def items(self, run_id: int) -> tuple[RunItemRecord, ...]:
        async with self._session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(RunItemRow)
                        .where(RunItemRow.run_id == run_id)
                        .order_by(RunItemRow.id)
                    )
                )
                .scalars()
                .all()
            )
            return tuple(
                RunItemRecord(
                    call_reference=row.call_reference,
                    status=RunItemStatus(row.status),
                    error=row.error,
                )
                for row in rows
            )

    async def set_status(
        self, run_id: int, status: RunStatus, *, at: datetime | None = None
    ) -> None:
        async with self._session_factory() as session, session.begin():
            row = (
                await session.execute(select(RunRow).where(RunRow.id == run_id))
            ).scalar_one_or_none()
            if row is None:
                raise NotFoundError(f"There is no run {run_id}.")
            row.status = status.value
            if at is not None and status is RunStatus.RUNNING and row.started_at is None:
                row.started_at = at
            if at is not None and status.is_terminal:
                row.finished_at = at

    async def set_item_status(
        self, run_id: int, call_reference: str, status: RunItemStatus, *, error: str | None = None
    ) -> None:
        async with self._session_factory() as session, session.begin():
            row = (
                await session.execute(
                    select(RunItemRow).where(
                        RunItemRow.run_id == run_id, RunItemRow.call_reference == call_reference
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                raise NotFoundError(f"Run {run_id} has no item for call {call_reference!r}.")
            row.status = status.value
            row.error = error

    async def active_run_ids(self) -> tuple[int, ...]:
        async with self._session_factory() as session:
            result = await session.execute(select(RunRow.id, RunRow.status))
            return tuple(run_id for run_id, status in result.all() if RunStatus(status).is_active)


def _to_record(row: RunRow) -> RunRecord:
    return RunRecord(
        id=row.id,
        status=RunStatus(row.status),
        provider=row.provider,
        model=row.model,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
    )
