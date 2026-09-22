"""The reference-import CLI, against a real temporary database and a real
small xlsx fixture (`tests/fixtures/reference_workbook.xlsx` — the same
content as `REFERENCE_SHEETS`, built to a real file so this exercises the
whole stack: XML parsing, row mapping, derivations, upsert, and the CLI's
own output and exit code).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from frameworks_drivers.cli.import_reference import EXIT_FAILED, EXIT_OK, main
from infrastructure.config.settings import get_settings
from infrastructure.persistence.models import Base

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "reference_workbook.xlsx"
BROKEN_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample_workbook.xlsx"


@pytest.fixture(autouse=True)
def _isolated_settings_cache() -> Iterator[None]:
    """`get_settings()` is process-wide-cached; clear it around each test so
    one test's env vars can't leak into the next.
    """
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_imports_the_fixture_workbook_and_prints_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    db_path = tmp_path / "cli_import_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("WORKBOOK_PATH", str(FIXTURE))
    monkeypatch.setenv("LOG_ENABLED", "false")
    monkeypatch.setenv("FRONTEND_DIST_PATH", str(tmp_path / "no-frontend"))

    _create_schema(db_path)

    exit_code = main()

    assert exit_code == EXIT_OK
    output = capsys.readouterr().out
    assert "2 brokers" in output
    assert "2 employers" in output


def test_reports_a_missing_header_as_a_clean_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The broken fixture has no master-data sheets at all — this must
    print a clean FAILED message and return EXIT_FAILED, not crash.
    """
    db_path = tmp_path / "cli_import_broken.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("WORKBOOK_PATH", str(BROKEN_FIXTURE))
    monkeypatch.setenv("LOG_ENABLED", "false")
    monkeypatch.setenv("FRONTEND_DIST_PATH", str(tmp_path / "no-frontend"))

    _create_schema(db_path)

    exit_code = main()

    assert exit_code == EXIT_FAILED
    assert "FAILED" in capsys.readouterr().out


def _create_schema(db_path: Path) -> None:
    from sqlalchemy import create_engine

    from infrastructure.persistence import tables as _tables  # noqa: F401

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()
