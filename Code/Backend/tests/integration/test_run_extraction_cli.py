"""The run CLI's write-lock guard, against a real (temporary) database.

`Documents/notes/Corpus-v10-Schema-Update.md`'s finding: an extraction run once left the
database failing `PRAGMA integrity_check`. This checks the one mitigation
that has to work through the real CLI entry point rather than in isolation
— refusing to start a second run while another's lock is still fresh. The
backup and post-run integrity check are `backup_before_run`'s and
`check_integrity`'s own unit tests; wiring a full successful run through
here would need a live model provider, which this suite never calls out to.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from frameworks_drivers.cli.run_extraction import EXIT_FAILED, _parse_args, _run
from infrastructure.config.settings import get_settings
from infrastructure.persistence.models import Base


@pytest.fixture(autouse=True)
def _isolated_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


async def test_a_fresh_lock_refuses_a_second_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = tmp_path / "run_extraction.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("LOG_ENABLED", "false")
    monkeypatch.setenv("FRONTEND_DIST_PATH", str(tmp_path / "no-frontend"))

    from sqlalchemy import create_engine

    from infrastructure.persistence import tables as _tables  # noqa: F401

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()

    # Another process's lock, refreshed a moment ago.
    lock_path = db_path.with_name(f"{db_path.name}.write-lock")
    lock_path.write_text("12345", encoding="utf-8")

    exit_code = await _run(_parse_args([]))

    output = capsys.readouterr().out
    assert exit_code == EXIT_FAILED
    assert "FAILED: Another process appears to be writing to this database" in output
    # Refused before anything else ran: the lock file is untouched, not
    # overwritten with this process's own pid.
    assert lock_path.read_text(encoding="utf-8") == "12345"
