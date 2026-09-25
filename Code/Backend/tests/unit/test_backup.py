"""`backup_before_run` — a consistent snapshot taken through SQLite's own
backup API, including data still sitting in the WAL file."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from infrastructure.persistence.backup import backup_before_run


def _seeded(path: Path, *, wal: bool = False) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path))
    if wal:
        connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("CREATE TABLE t (id INTEGER PRIMARY KEY)")
    connection.execute("INSERT INTO t VALUES (1)")
    connection.commit()
    return connection


async def test_a_missing_database_has_nothing_to_back_up(tmp_path: Path) -> None:
    assert await backup_before_run(tmp_path / "does-not-exist.db") is None


async def test_none_is_a_no_op() -> None:
    """Postgres has no file of its own to snapshot."""
    assert await backup_before_run(None) is None


async def test_the_backup_is_a_working_copy_in_a_backups_subdirectory(tmp_path: Path) -> None:
    database_file = tmp_path / "nanovox_insights.db"
    _seeded(database_file).close()

    backup_path = await backup_before_run(database_file)

    assert backup_path is not None
    assert backup_path.parent == tmp_path / "backups"
    copy = sqlite3.connect(str(backup_path))
    try:
        assert copy.execute("SELECT id FROM t").fetchall() == [(1,)]
    finally:
        copy.close()


async def test_a_wal_mode_write_not_yet_checkpointed_is_still_captured(tmp_path: Path) -> None:
    """The exact gap a plain file copy has: recent commits can still be
    sitting in the -wal file, not yet folded into the .db file itself."""
    database_file = tmp_path / "nanovox_insights.db"
    connection = _seeded(database_file, wal=True)
    try:
        connection.execute("INSERT INTO t VALUES (2)")
        connection.commit()  # in the WAL; not checkpointed into the .db file

        backup_path = await backup_before_run(database_file)
    finally:
        connection.close()

    assert backup_path is not None
    copy = sqlite3.connect(str(backup_path))
    try:
        assert copy.execute("SELECT id FROM t ORDER BY id").fetchall() == [(1,), (2,)]
    finally:
        copy.close()


async def test_old_backups_are_pruned_beyond_the_keep_limit(tmp_path: Path) -> None:
    database_file = tmp_path / "nanovox_insights.db"
    _seeded(database_file).close()

    for _ in range(4):
        await backup_before_run(database_file, keep=2)

    backups = sorted((tmp_path / "backups").glob("*.db"))
    assert len(backups) == 2


async def test_keep_zero_or_less_prunes_nothing(tmp_path: Path) -> None:
    """`keep` is a positive limit; zero or negative disables pruning rather
    than deleting every backup just taken."""
    database_file = tmp_path / "nanovox_insights.db"
    _seeded(database_file).close()

    for _ in range(3):
        await backup_before_run(database_file, keep=0)

    backups = list((tmp_path / "backups").glob("*.db"))
    assert len(backups) == 3
