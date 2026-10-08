"""SQLAlchemy implementation of `ApprovedEmailsRepository`.

Normalises on every read and write — `_normalise` is the one place that
defines "the same address", rather than leaving case- and
whitespace-sensitivity to whatever a caller happened to pass in.
"""

from __future__ import annotations

import contextlib
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports.approved_emails_repository import ApprovedEmailsRepository
from infrastructure.persistence.tables import ApprovedEmailRow


def _normalise(email: str) -> str:
    return email.strip().lower()


class SqlApprovedEmailsRepository(ApprovedEmailsRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def is_approved(self, email: str) -> bool:
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(ApprovedEmailRow.id).where(ApprovedEmailRow.email == _normalise(email))
                )
            ).scalar_one_or_none()
            return row is not None

    async def add(self, email: str, *, at: datetime) -> None:
        normalised = _normalise(email)
        async with self._session_factory() as session, session.begin():
            existing = (
                await session.execute(
                    select(ApprovedEmailRow.id).where(ApprovedEmailRow.email == normalised)
                )
            ).scalar_one_or_none()
            if existing is not None:
                return
            session.add(ApprovedEmailRow(email=normalised, created_at=at))
            # Lost a race with another `add` for the same address between the
            # check above and this flush — the row exists either way, which
            # is the outcome this method promises.
            with contextlib.suppress(IntegrityError):
                await session.flush()

    async def remove(self, email: str) -> bool:
        async with self._session_factory() as session, session.begin():
            row = (
                await session.execute(
                    select(ApprovedEmailRow).where(ApprovedEmailRow.email == _normalise(email))
                )
            ).scalar_one_or_none()
            if row is None:
                return False
            await session.delete(row)
            return True

    async def list_all(self) -> tuple[str, ...]:
        async with self._session_factory() as session:
            rows = (
                (
                    await session.execute(
                        select(ApprovedEmailRow.email).order_by(ApprovedEmailRow.created_at)
                    )
                )
                .scalars()
                .all()
            )
            return tuple(rows)
