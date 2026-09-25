"""The run CLI's progress output."""

from __future__ import annotations

import io

import pytest

from frameworks_drivers.cli import run_extraction


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
