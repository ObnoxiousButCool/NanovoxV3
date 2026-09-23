"""`SqlRunRepository` against a real (temporary) SQLite database."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from domain.errors import NotFoundError
from domain.value_objects.run_status import RunItemStatus, RunStatus
from infrastructure.persistence.repositories.run_repository import SqlRunRepository

_CREATED_AT = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)
_STARTED_AT = datetime(2026, 9, 23, 12, 1, tzinfo=timezone.utc)


async def test_a_new_run_has_one_pending_item_per_reference(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    repository = SqlRunRepository(session_factory)

    run_id = await repository.create(
        ("C-0001", "C-0002"), provider="ollama", model="m", created_at=_CREATED_AT
    )
    record = await repository.get(run_id)
    items = await repository.items(run_id)

    assert record is not None
    assert record.status is RunStatus.PENDING
    assert record.provider == "ollama"
    assert record.started_at is None
    assert {item.call_reference for item in items} == {"C-0001", "C-0002"}
    assert all(item.status is RunItemStatus.PENDING for item in items)


async def test_an_unknown_run_returns_none(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    repository = SqlRunRepository(session_factory)

    assert await repository.get(999) is None
    assert await repository.items(999) == ()


class TestSetStatus:
    async def test_moving_to_running_records_started_at_once(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        repository = SqlRunRepository(session_factory)
        run_id = await repository.create(
            ("C-0001",), provider="p", model="m", created_at=_CREATED_AT
        )

        await repository.set_status(run_id, RunStatus.RUNNING, at=_STARTED_AT)
        record = await repository.get(run_id)

        assert record is not None
        assert record.status is RunStatus.RUNNING
        # SQLite drops tzinfo on round trip; every timestamp in this stack
        # is UTC by convention (`Clock.now()`'s own contract).
        assert record.started_at is not None
        assert record.started_at.replace(tzinfo=timezone.utc) == _STARTED_AT
        assert record.finished_at is None

    async def test_a_terminal_status_records_finished_at(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        repository = SqlRunRepository(session_factory)
        run_id = await repository.create(
            ("C-0001",), provider="p", model="m", created_at=_CREATED_AT
        )

        await repository.set_status(run_id, RunStatus.COMPLETED, at=_STARTED_AT)
        record = await repository.get(run_id)

        assert record is not None
        assert record.finished_at is not None
        assert record.finished_at.replace(tzinfo=timezone.utc) == _STARTED_AT

    async def test_setting_status_on_an_unknown_run_is_refused(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        repository = SqlRunRepository(session_factory)

        with pytest.raises(NotFoundError, match="999"):
            await repository.set_status(999, RunStatus.RUNNING)


class TestSetItemStatus:
    async def test_an_items_status_and_error_round_trip(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        repository = SqlRunRepository(session_factory)
        run_id = await repository.create(
            ("C-0001",), provider="p", model="m", created_at=_CREATED_AT
        )

        await repository.set_item_status(run_id, "C-0001", RunItemStatus.FAILED, error="boom")
        items = await repository.items(run_id)

        assert len(items) == 1
        assert items[0].status is RunItemStatus.FAILED
        assert items[0].error == "boom"

    async def test_setting_an_unknown_items_status_is_refused(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        repository = SqlRunRepository(session_factory)
        run_id = await repository.create(
            ("C-0001",), provider="p", model="m", created_at=_CREATED_AT
        )

        with pytest.raises(NotFoundError):
            await repository.set_item_status(run_id, "C-9999", RunItemStatus.COMPLETED)


class TestActiveRunIds:
    async def test_only_active_runs_are_returned(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        repository = SqlRunRepository(session_factory)
        active = await repository.create(
            ("C-0001",), provider="p", model="m", created_at=_CREATED_AT
        )
        finished = await repository.create(
            ("C-0002",), provider="p", model="m", created_at=_CREATED_AT
        )
        await repository.set_status(active, RunStatus.RUNNING)
        await repository.set_status(finished, RunStatus.COMPLETED)

        assert await repository.active_run_ids() == (active,)
