"""A pre-run snapshot of the SQLite database file.

Taken through SQLite's own backup API (`sqlite3.Connection.backup`) rather
than a plain file copy: a WAL-mode database's most recent writes can still
be sitting in the `-wal` file, not yet checkpointed into the `.db` file
itself, and copying only the `.db` file can silently miss them. The backup
API produces a consistent snapshot regardless of what is or is not
checkpointed — the same guarantee a live `.backup` command in the `sqlite3`
CLI gives.

Exists because of `Corpus-v10-Schema-Update.md`'s finding: a run left the
database failing `PRAGMA integrity_check`, and the only intact copy was one
someone happened to have taken by hand just before. Taking that
automatically, before anything writes, means a corruption is a restore
away rather than a rebuild of everything the extraction itself produced.
"""

from __future__ import annotations

import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

#: Microsecond precision, not just seconds: two backups taken in the same
#: second (a script running the CLI in a tight loop, or this module's own
#: tests) must still get distinct filenames rather than one overwriting
#: the other.
_TIMESTAMP_FORMAT = "%Y%m%dT%H%M%S.%fZ"

#: How many backups to keep. Not unbounded — a database backed up before
#: every run would otherwise grow the backups directory by one file per
#: invocation forever.
DEFAULT_KEEP = 5


def _unique_destination(backups_dir: Path, database_file: Path) -> Path:
    """A backup filename nothing at `backups_dir` already uses.

    The timestamp alone is not enough: Windows' wall clock resolution is
    coarser than a microsecond, so two backups taken close enough together
    — this module's own tests do, and a script running the CLI in a tight
    loop could too — can compute the identical string despite `%f`'s
    precision, and the second would silently back up onto the first rather
    than getting its own file. A numeric suffix, incremented until the
    path is free, is guaranteed unique regardless of clock resolution;
    the timestamp is kept because it is what makes the directory
    readable, not because it alone is trusted to be unique.
    """
    timestamp = datetime.now(timezone.utc).strftime(_TIMESTAMP_FORMAT)
    stem = f"{database_file.stem}.{timestamp}"
    destination = backups_dir / f"{stem}{database_file.suffix}"
    suffix = 1
    while destination.exists():
        destination = backups_dir / f"{stem}-{suffix}{database_file.suffix}"
        suffix += 1
    return destination


def _backup_sync(database_file: Path, *, keep: int) -> Path | None:
    """The synchronous half — every filesystem and `sqlite3` call, run
    together in one worker thread rather than a mix of blocking calls
    scattered through the async caller."""
    if not database_file.exists():
        return None

    backups_dir = database_file.parent / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    destination = _unique_destination(backups_dir, database_file)
    source = sqlite3.connect(str(database_file))
    try:
        dest = sqlite3.connect(str(destination))
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()

    _prune(backups_dir, database_file, keep)
    return destination


async def backup_before_run(database_file: Path | None, *, keep: int = DEFAULT_KEEP) -> Path | None:
    """A consistent snapshot of `database_file`, in `<its directory>/backups/`.

    `None` for anything that is not SQLite, or a database that does not
    exist yet — a fresh database has nothing worth a backup of. Prunes
    down to the newest `keep` backups afterwards.
    """
    if database_file is None:
        return None
    return await asyncio.to_thread(_backup_sync, database_file, keep=keep)


def _prune(backups_dir: Path, database_file: Path, keep: int) -> None:
    if keep <= 0:
        return
    pattern = f"{database_file.stem}.*{database_file.suffix}"
    backups = sorted(backups_dir.glob(pattern))  # the timestamp format sorts oldest first
    for stale in backups[:-keep]:
        stale.unlink(missing_ok=True)
