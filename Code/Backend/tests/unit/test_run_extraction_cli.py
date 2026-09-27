"""The run CLI's progress output and exit code."""

from __future__ import annotations

import io

import pytest

from domain.run_progress import RunProgress
from frameworks_drivers.cli import run_extraction
from frameworks_drivers.cli.run_extraction import EXIT_MOSTLY_FAILED, EXIT_OK, _exit_code_for


class _RecordingStream(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.flushed_at: list[int] = []

    def flush(self) -> None:
        self.flushed_at.append(len(self.getvalue()))
        super().flush()


def test_every_progress_line_is_flushed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A run takes minutes. Redirected to a file, an unflushed line would
    not appear until the process exited, which is exactly when nobody needs
    it any more."""
    stream = _RecordingStream()
    monkeypatch.setattr("sys.stdout", stream)

    run_extraction._out("Run 1 started.")
    run_extraction._out(" 50.0% — 50 completed")

    assert stream.getvalue() == "Run 1 started.\n 50.0% — 50 completed\n"
    assert stream.flushed_at == [len("Run 1 started.\n"), len(stream.getvalue())]


def _progress(
    *, completed: int = 0, failed: int = 0, skipped: int = 0, cancelled: int = 0
) -> RunProgress:
    return RunProgress(
        total=completed + failed + skipped + cancelled,
        completed=completed,
        failed=failed,
        skipped=skipped,
        cancelled=cancelled,
        running=0,
        pending=0,
    )


def test_a_run_that_mostly_failed_is_not_ok() -> None:
    """Ranjit's report: 6 completed, 94 failed, exit 0 — the run finished
    and the extraction did not, and the two looked identical on the wire."""
    progress = _progress(completed=6, failed=94)

    assert _exit_code_for(progress) == EXIT_MOSTLY_FAILED


def test_a_run_that_mostly_succeeded_is_ok_even_with_some_failures() -> None:
    """An occasional item failing among mostly-completed ones is the normal
    cost of resumability, not a run to distrust."""
    progress = _progress(completed=94, failed=6)

    assert _exit_code_for(progress) == EXIT_OK


def test_an_even_split_is_not_yet_mostly_failed() -> None:
    """The rule is strictly more failures than successes, not a tie."""
    progress = _progress(completed=50, failed=50)

    assert _exit_code_for(progress) == EXIT_OK


def test_an_empty_run_is_ok() -> None:
    assert _exit_code_for(_progress()) == EXIT_OK


def test_a_fully_cancelled_run_with_no_failures_is_ok() -> None:
    """Cancellation is a deliberate action, not a failure — it must not
    trip the same code a systemic problem does."""
    progress = _progress(cancelled=100)

    assert _exit_code_for(progress) == EXIT_OK
