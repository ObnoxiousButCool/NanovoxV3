"""SQLAlchemy implementation of `StageCache`.

Upsert by key, like the other repositories: select for the existing row,
then update it in place or insert a new one — dialect-neutral so the same
code runs on SQLite and Postgres (decision D9), rather than a dialect-
specific ``ON CONFLICT``.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports.clock import Clock
from application.ports.stage_cache import StageCache, StageCacheKey
from infrastructure.persistence.tables import StageCacheEntryRow


class SqlStageCache(StageCache):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], clock: Clock) -> None:
        self._session_factory = session_factory
        self._clock = clock

    async def get(self, key: StageCacheKey) -> str | None:
        async with self._session_factory() as session:
            row = await self._find(session, key)
            return row.output_text if row is not None else None

    async def put(self, key: StageCacheKey, value: str) -> None:
        async with self._session_factory() as session, session.begin():
            row = await self._find(session, key)
            if row is None:
                row = StageCacheEntryRow(
                    transcript_hash=key.transcript_hash,
                    layer=key.layer.value,
                    prompt_version=key.prompt_version,
                    model=key.model,
                    output_text=value,
                    cached_at=self._clock.now(),
                )
                session.add(row)
            else:
                row.output_text = value
                row.cached_at = self._clock.now()

    async def _find(self, session: AsyncSession, key: StageCacheKey) -> StageCacheEntryRow | None:
        result = await session.execute(
            select(StageCacheEntryRow).where(
                StageCacheEntryRow.transcript_hash == key.transcript_hash,
                StageCacheEntryRow.layer == key.layer.value,
                StageCacheEntryRow.prompt_version == key.prompt_version,
                StageCacheEntryRow.model == key.model,
            )
        )
        return result.scalar_one_or_none()
