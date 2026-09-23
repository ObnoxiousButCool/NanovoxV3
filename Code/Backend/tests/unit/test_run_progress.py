"""Run state and the progress derived from it.

The rules here decide what a progress bar claims, so each one is a
statement about honesty rather than arithmetic: a skipped item is not an
analysed one, and an empty run must not read as stalled.
"""

from __future__ import annotations

import pytest

from domain.run_progress import summarise
from domain.value_objects.run_status import RunItemStatus, RunStatus

COMPLETED = RunItemStatus.COMPLETED
FAILED = RunItemStatus.FAILED
SKIPPED = RunItemStatus.SKIPPED
PENDING = RunItemStatus.PENDING
RUNNING = RunItemStatus.RUNNING
CANCELLED = RunItemStatus.CANCELLED


class TestProgress:
    def test_the_four_outcomes_are_counted_separately(self) -> None:
        # A run that skipped ninety and analysed ten is not the same event
        # as one that analysed a hundred.
        progress = summarise([COMPLETED, COMPLETED, SKIPPED, FAILED, PENDING])

        assert progress.total == 5
        assert (progress.completed, progress.skipped, progress.failed) == (2, 1, 1)
        assert progress.remaining == 1

    def test_percent_counts_every_resting_item_not_only_successes(self) -> None:
        progress = summarise([COMPLETED, SKIPPED, FAILED, PENDING])

        assert progress.percent_complete == 75.0

    def test_an_empty_run_is_finished_rather_than_stalled_at_zero(self) -> None:
        # There is nothing left to do; showing 0% would report a problem.
        progress = summarise([])

        assert progress.percent_complete == 100.0
        assert progress.is_exhausted

    def test_a_running_item_is_not_yet_finished(self) -> None:
        progress = summarise([COMPLETED, RUNNING])

        assert progress.finished == 1
        assert not progress.is_exhausted

    def test_a_cancelled_item_counts_as_finished(self) -> None:
        progress = summarise([CANCELLED])

        assert progress.finished == 1
        assert progress.is_exhausted


class TestRunStatus:
    @pytest.mark.parametrize(
        "status",
        [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.INTERRUPTED],
    )
    def test_terminal_states_are_not_active(self, status: RunStatus) -> None:
        assert status.is_terminal
        assert not status.is_active

    @pytest.mark.parametrize("status", [RunStatus.PENDING, RunStatus.RUNNING, RunStatus.CANCELLING])
    def test_a_cancelling_run_still_counts_as_working(self, status: RunStatus) -> None:
        # It has an item in flight, so a second run must still be refused.
        assert status.is_active
        assert not status.is_terminal

    def test_a_completed_run_is_not_resumable(self) -> None:
        assert not RunStatus.COMPLETED.is_resumable

    @pytest.mark.parametrize(
        "status", [RunStatus.CANCELLED, RunStatus.FAILED, RunStatus.INTERRUPTED]
    )
    def test_a_stopped_run_can_be_picked_up_again(self, status: RunStatus) -> None:
        # Cancelling is a pause the operator chose; refusing to continue it
        # would make cancel a destructive act.
        assert status.is_resumable


class TestItemStatus:
    def test_a_failed_item_is_retried_and_a_skipped_one_is_not(self) -> None:
        # Skipping was a decision about the item; failing was an accident.
        assert RunItemStatus.FAILED.needs_work
        assert not RunItemStatus.SKIPPED.needs_work

    def test_an_item_left_running_by_a_dead_process_is_retried(self) -> None:
        assert RunItemStatus.RUNNING.needs_work

    @pytest.mark.parametrize(
        "status",
        [
            RunItemStatus.COMPLETED,
            RunItemStatus.FAILED,
            RunItemStatus.SKIPPED,
            RunItemStatus.CANCELLED,
        ],
    )
    def test_a_resting_status_is_finished(self, status: RunItemStatus) -> None:
        assert status.is_finished

    @pytest.mark.parametrize("status", [RunItemStatus.PENDING, RunItemStatus.RUNNING])
    def test_a_working_status_is_not_finished(self, status: RunItemStatus) -> None:
        assert not status.is_finished
