"""`SqlRunRepository` against a real (temporary) SQLite database."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from domain.errors import NotFoundError
from domain.value_objects.run_status import RunItemStatus, RunStatus
from domain.value_objects.token_usage import TokenUsage
from infrastructure.persistence.repositories.diagnostics_source import (
    SqlDiagnosticsSource,
)
from infrastructure.persistence.repositories.run_repository import SqlRunRepository

_CREATED_AT = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)
_STARTED_AT = datetime(2026, 9, 23, 12, 1, tzinfo=UTC)


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
        assert record.started_at.replace(tzinfo=UTC) == _STARTED_AT
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
        assert record.finished_at.replace(tzinfo=UTC) == _STARTED_AT

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

    async def test_an_items_token_cost_round_trips(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Plan §8 Phase 5 asks the diagnostics for "token cost of the last
        run", so the numbers have to survive the database, not just the
        pipeline.
        """
        repository = SqlRunRepository(session_factory)
        run_id = await repository.create(
            ("C-0001",), provider="p", model="m", created_at=_CREATED_AT
        )

        await repository.set_item_status(
            run_id,
            "C-0001",
            RunItemStatus.COMPLETED,
            usage=TokenUsage(input_tokens=1_200, output_tokens=340),
            duration_ms=812.5,
        )
        item = (await repository.items(run_id))[0]

        assert item.usage.total_tokens == 1_540
        assert item.usage.reported is True
        assert item.duration_ms == pytest.approx(812.5)

    async def test_an_unreported_usage_round_trips_as_unreported(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Zero tokens and "the provider did not say" are different states,
        and the difference has to survive storage or every total above it
        silently becomes a cost rather than a floor.
        """
        repository = SqlRunRepository(session_factory)
        run_id = await repository.create(
            ("C-0001",), provider="p", model="m", created_at=_CREATED_AT
        )

        await repository.set_item_status(
            run_id, "C-0001", RunItemStatus.COMPLETED, usage=TokenUsage.unreported()
        )
        item = (await repository.items(run_id))[0]

        assert item.usage.total_tokens == 0
        assert item.usage.reported is False

    async def test_starting_an_item_does_not_wipe_a_previous_attempts_cost(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """A resumed run moves its items back to RUNNING without a usage.
        Writing a zero there would erase what the first attempt spent, and
        the tokens were still spent.
        """
        repository = SqlRunRepository(session_factory)
        run_id = await repository.create(
            ("C-0001",), provider="p", model="m", created_at=_CREATED_AT
        )
        await repository.set_item_status(
            run_id,
            "C-0001",
            RunItemStatus.FAILED,
            usage=TokenUsage(input_tokens=900, output_tokens=100),
        )

        await repository.set_item_status(run_id, "C-0001", RunItemStatus.RUNNING)
        item = (await repository.items(run_id))[0]

        assert item.usage.total_tokens == 1_000

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


class TestDiagnosticsCost:
    """`SqlDiagnosticsSource` reading the last run's cost back out."""

    async def test_the_last_run_is_the_most_recently_created_one(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """Ordered by created_at then id: two runs made in the same second
        would otherwise come back in whatever order the database chose, and
        "the last run" has to mean one particular run.
        """
        runs = SqlRunRepository(session_factory)
        older = await runs.create(("C-0001",), provider="p", model="m", created_at=_CREATED_AT)
        newer = await runs.create(("C-0002",), provider="p", model="m", created_at=_CREATED_AT)
        await runs.set_item_status(
            older, "C-0001", RunItemStatus.COMPLETED, usage=TokenUsage(input_tokens=999)
        )
        await runs.set_item_status(
            newer, "C-0002", RunItemStatus.COMPLETED, usage=TokenUsage(input_tokens=10)
        )

        cost = (await SqlDiagnosticsSource(session_factory).read()).last_run_cost

        assert cost is not None
        assert cost.usage.input_tokens == 10, "the newer run, not the larger one"

    async def test_items_that_never_ran_do_not_dilute_the_cost(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        """A pending item has no usage to add, and counting it would drag
        the per-call figures down for a run that simply has not finished.
        """
        runs = SqlRunRepository(session_factory)
        run_id = await runs.create(
            ("C-0001", "C-0002"), provider="p", model="m", created_at=_CREATED_AT
        )
        await runs.set_item_status(
            run_id,
            "C-0001",
            RunItemStatus.COMPLETED,
            usage=TokenUsage(input_tokens=100, output_tokens=20),
            duration_ms=500.0,
        )

        cost = (await SqlDiagnosticsSource(session_factory).read()).last_run_cost

        assert cost is not None
        assert cost.items == 1, "the pending item contributed nothing"
        assert cost.usage.total_tokens == 120
        assert cost.complete is True

    async def test_one_unreported_item_makes_the_whole_run_a_floor(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        runs = SqlRunRepository(session_factory)
        run_id = await runs.create(
            ("C-0001", "C-0002"), provider="p", model="m", created_at=_CREATED_AT
        )
        await runs.set_item_status(
            run_id, "C-0001", RunItemStatus.COMPLETED, usage=TokenUsage(input_tokens=100)
        )
        await runs.set_item_status(
            run_id,
            "C-0002",
            RunItemStatus.COMPLETED,
            usage=TokenUsage.unreported(),
            duration_ms=1.0,
        )

        cost = (await SqlDiagnosticsSource(session_factory).read()).last_run_cost

        assert cost is not None
        assert cost.complete is False
        assert cost.summary.startswith("At least")
