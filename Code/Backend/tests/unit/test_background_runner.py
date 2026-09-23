"""The in-process task runner: task references are held, failures are logged.

Exercised directly, not through a corpus run — Phase 3 ships this as
generic machinery ahead of the pipeline (Phase 4) that will actually use
it (plan §8 Phase 3, "run orchestration").
"""

from __future__ import annotations

import asyncio
import logging

import pytest

from infrastructure.runner.background_runner import BackgroundRunner


async def _wait_for(condition: object, timeout: float = 1.0) -> None:
    """Poll a zero-arg callable until it's true, or fail after `timeout`."""
    assert callable(condition)
    deadline = asyncio.get_running_loop().time() + timeout
    while not condition():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition never became true")
        await asyncio.sleep(0.01)


class TestStarting:
    async def test_starting_work_marks_the_run_as_working(self) -> None:
        runner = BackgroundRunner()
        started = asyncio.Event()

        async def work() -> None:
            started.set()
            await asyncio.sleep(10)

        assert runner.start(1, work())
        await started.wait()

        assert runner.is_working(1)
        assert runner.active_run_ids == (1,)

        await runner.shutdown()

    async def test_a_second_start_for_the_same_id_is_refused(self) -> None:
        runner = BackgroundRunner()
        started = asyncio.Event()

        async def work() -> None:
            started.set()
            await asyncio.sleep(10)

        runner.start(1, work())
        await started.wait()

        async def second() -> None:  # pragma: no cover - never runs
            raise AssertionError("the second coroutine must never be awaited")

        assert not runner.start(1, second())

        await runner.shutdown()

    async def test_a_refused_coroutine_is_closed_not_leaked(self) -> None:
        runner = BackgroundRunner()
        started = asyncio.Event()

        async def work() -> None:
            started.set()
            await asyncio.sleep(10)

        runner.start(1, work())
        await started.wait()

        second = _never_runs()
        assert not runner.start(1, second)
        # A closed coroutine raises on being awaited; there's no direct way
        # to assert closure other than that it's now unusable.
        with pytest.raises(RuntimeError, match=r"cannot reuse already awaited coroutine|closed"):
            await second

        await runner.shutdown()

    async def test_a_different_id_starts_independently(self) -> None:
        runner = BackgroundRunner()
        first_started = asyncio.Event()
        second_started = asyncio.Event()

        async def first() -> None:
            first_started.set()
            await asyncio.sleep(10)

        async def second() -> None:
            second_started.set()
            await asyncio.sleep(10)

        assert runner.start(1, first())
        assert runner.start(2, second())
        await first_started.wait()
        await second_started.wait()

        assert set(runner.active_run_ids) == {1, 2}

        await runner.shutdown()


async def _never_runs() -> None:  # pragma: no cover - closed before it starts
    raise AssertionError("must be closed before ever running")


class TestCompletion:
    async def test_a_finished_task_is_no_longer_working(self) -> None:
        runner = BackgroundRunner()

        async def quick() -> None:
            return None

        runner.start(1, quick())
        await _wait_for(lambda: not runner.is_working(1))

        assert not runner.is_working(1)
        assert runner.active_run_ids == ()

    async def test_a_failed_task_is_logged_rather_than_raised(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        runner = BackgroundRunner()

        async def boom() -> None:
            raise ValueError("something went wrong")

        with caplog.at_level(logging.ERROR):
            runner.start(1, boom())
            await _wait_for(lambda: not runner.is_working(1))

        assert any("stopped with an error" in message for message in caplog.messages)


class TestShutdown:
    async def test_shutdown_cancels_every_running_task(self) -> None:
        runner = BackgroundRunner()
        started = asyncio.Event()

        async def work() -> None:
            started.set()
            await asyncio.sleep(10)

        runner.start(1, work())
        await started.wait()

        await runner.shutdown()

        assert runner.active_run_ids == ()

    async def test_shutdown_with_nothing_running_is_harmless(self) -> None:
        await BackgroundRunner().shutdown()
