"""The database health probe against a real (temporary) SQLite database."""

from __future__ import annotations

from pathlib import Path

from domain.value_objects.health import ComponentStatus
from infrastructure.persistence.engine import create_database_engine
from infrastructure.persistence.health_probe import DatabaseHealthProbe
from tests.support.settings import make_settings


async def test_reports_up_for_a_reachable_database(tmp_path: Path) -> None:
    settings = make_settings(
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'probe.db').as_posix()}"
    )
    engine = create_database_engine(settings)
    try:
        probe = DatabaseHealthProbe(engine)
        result = await probe.check()
    finally:
        await engine.dispose()

    assert result.name == "database"
    assert result.status is ComponentStatus.UP


async def test_reports_down_for_an_unreachable_database(tmp_path: Path) -> None:
    settings = make_settings(
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'missing' / 'probe.db').as_posix()}"
    )
    engine = create_database_engine(settings)
    # The directory was created by create_database_engine; remove it again so
    # the connection genuinely fails, rather than relying on it never having
    # existed.
    (tmp_path / "missing").rmdir()
    try:
        probe = DatabaseHealthProbe(engine)
        result = await probe.check()
    finally:
        await engine.dispose()

    assert result.status is ComponentStatus.DOWN
    assert result.detail is not None
