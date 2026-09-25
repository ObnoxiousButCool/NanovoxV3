"""`check_integrity` against real SQLite databases — clean and corrupted."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine

from infrastructure.persistence.integrity import OK, check_integrity


async def test_a_clean_database_reports_ok(tmp_path: Path) -> None:
    database_file = tmp_path / "clean.db"
    connection = sqlite3.connect(str(database_file))
    try:
        connection.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
        connection.execute("INSERT INTO t VALUES (1)")
        connection.commit()
    finally:
        connection.close()

    engine = create_async_engine(f"sqlite+aiosqlite:///{database_file.as_posix()}")
    try:
        assert await check_integrity(engine) == OK
    finally:
        await engine.dispose()


async def test_a_corrupted_database_is_reported_not_silently_passed(tmp_path: Path) -> None:
    """The exact failure mode this exists for: a corrupted file must be
    named, not read back as clean."""
    database_file = tmp_path / "corrupt.db"
    connection = sqlite3.connect(str(database_file))
    try:
        connection.execute("CREATE TABLE t (id INTEGER PRIMARY KEY, payload TEXT)")
        for i in range(200):
            connection.execute("INSERT INTO t VALUES (?, ?)", (i, "x" * 500))
        connection.commit()
    finally:
        connection.close()

    # Overwrite a chunk well past the header with garbage — real page data,
    # not the header pragma SQLite trusts without reading, so this reaches
    # integrity_check rather than failing to open at all.
    with database_file.open("r+b") as handle:
        handle.seek(4096)
        handle.write(b"\xff" * 2048)

    engine = create_async_engine(f"sqlite+aiosqlite:///{database_file.as_posix()}")
    try:
        result = await check_integrity(engine)
    finally:
        await engine.dispose()

    assert result != OK


async def test_a_non_sqlite_dialect_is_skipped_as_ok() -> None:
    """Postgres has its own integrity guarantees and no equivalent pragma —
    this must not claim to have checked something it did not. Dialect
    resolution from the URL is immediate; no real Postgres is contacted."""
    engine = create_async_engine("postgresql+asyncpg://user:pass@localhost/dummy")
    try:
        assert engine.dialect.name != "sqlite"
        assert await check_integrity(engine) == OK
    finally:
        await engine.dispose()
