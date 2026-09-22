"""Engine construction: SQLite pragmas, the Postgres statement-cache workaround,
and a clear failure when the database directory can't be created.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.errors import ConfigurationError
from infrastructure.persistence.engine import (
    _connect_args_for,
    create_database_engine,
    create_session_factory,
)
from tests.support.settings import make_settings


def test_postgres_disables_the_asyncpg_statement_cache() -> None:
    args = _connect_args_for("postgresql+asyncpg://user:pw@host/db")

    assert args == {"statement_cache_size": 0}


def test_sqlite_needs_no_extra_connect_args() -> None:
    assert _connect_args_for("sqlite+aiosqlite:///C:/data/db.sqlite") == {}


def test_raises_a_configuration_error_when_the_directory_cannot_be_created(
    tmp_path: Path,
) -> None:
    # The parent segment is a file, so mkdir(parents=True) on the database's
    # directory fails — the same technique tests/support/settings.py uses for
    # its "unreachable" database URL.
    blocking_file = tmp_path / "not-a-directory"
    blocking_file.write_text("", encoding="utf-8")
    settings = make_settings(
        database_url=f"sqlite+aiosqlite:///{(blocking_file / 'db.sqlite').as_posix()}"
    )

    with pytest.raises(ConfigurationError) as excinfo:
        create_database_engine(settings)

    assert "cannot be created" in excinfo.value.message


async def test_session_factory_opens_a_working_session(tmp_path: Path) -> None:
    settings = make_settings(
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'sessions.db').as_posix()}"
    )
    engine = create_database_engine(settings)
    try:
        factory = create_session_factory(engine)
        assert isinstance(factory, async_sessionmaker)
        async with factory() as session:
            assert session.is_active
    finally:
        await engine.dispose()
