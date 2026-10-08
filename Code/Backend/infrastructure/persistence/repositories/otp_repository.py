"""SQLAlchemy implementation of `OtpRepository`."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports.otp_repository import OtpRepository, OtpRequestRecord
from domain.errors import NotFoundError
from infrastructure.persistence.tables import OtpRequestRow


class SqlOtpRepository(OtpRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(
        self, *, email: str, code_hash: str, created_at: datetime, expires_at: datetime
    ) -> OtpRequestRecord:
        async with self._session_factory() as session, session.begin():
            row = OtpRequestRow(
                email=email,
                code_hash=code_hash,
                created_at=created_at,
                expires_at=expires_at,
                attempts=0,
                consumed_at=None,
            )
            session.add(row)
            await session.flush()
            return _to_record(row)

    async def latest_for(self, email: str) -> OtpRequestRecord | None:
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(OtpRequestRow)
                    .where(OtpRequestRow.email == email)
                    .order_by(OtpRequestRow.created_at.desc(), OtpRequestRow.id.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
            return None if row is None else _to_record(row)

    async def record_attempt(self, request_id: int) -> int:
        async with self._session_factory() as session, session.begin():
            row = (
                await session.execute(select(OtpRequestRow).where(OtpRequestRow.id == request_id))
            ).scalar_one_or_none()
            if row is None:
                raise NotFoundError(f"There is no OTP request {request_id}.")
            row.attempts += 1
            await session.flush()
            return row.attempts

    async def consume(self, request_id: int, *, at: datetime) -> None:
        async with self._session_factory() as session, session.begin():
            row = (
                await session.execute(select(OtpRequestRow).where(OtpRequestRow.id == request_id))
            ).scalar_one_or_none()
            if row is None:
                raise NotFoundError(f"There is no OTP request {request_id}.")
            row.consumed_at = at


def _to_record(row: OtpRequestRow) -> OtpRequestRecord:
    return OtpRequestRecord(
        id=row.id,
        email=row.email,
        code_hash=row.code_hash,
        created_at=_utc(row.created_at),
        expires_at=_utc(row.expires_at),
        attempts=row.attempts,
        consumed_at=None if row.consumed_at is None else _utc(row.consumed_at),
    )


def _utc(value: datetime) -> datetime:
    """SQLite stores no zone, and the clock only ever writes UTC. Read back
    as UTC so a stored timestamp compares correctly against a fresh one."""
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
