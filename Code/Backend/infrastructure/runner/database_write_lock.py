"""Guards a SQLite database file against two processes writing to it at
once (`Documents/notes/Corpus-v10-Schema-Update.md`'s DB-corruption finding: an extraction
run left the database failing `PRAGMA integrity_check`, tables reading
back each other's rows).

WAL mode, `synchronous=NORMAL` and a busy timeout are already on
(`infrastructure/persistence/engine.py`) — SQLite's own documented
recipe for one writer and many readers. The corruption happened despite
that, which means something above SQLite's own locking needed to stop two
writers existing in the first place, not tune it further.

## A heartbeat, not a PID check

The lock file's age is what decides whether it is still held, not whether
its owning process is still alive. A cross-platform PID-liveness check
(`os.kill(pid, 0)` behaves differently enough between POSIX and Windows to
be its own source of bugs) buys nothing a heartbeat does not already give
more simply: a process that is still working keeps refreshing the file's
mtime, and one that died — however it died — stops, and the lock goes
stale on its own within one poll interval.

## Scope: the run CLI, not every writer

This guards `run_extraction.py`, the one entry point that writes enough,
for long enough, to be the plausible cause of what was found — not every
path that touches the database. If the API's own run-start endpoint
becomes a second concurrent way to begin a run, the same guard belongs
inside `RunExtractionOverCorpus` itself rather than duplicated here.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from domain.errors import ConflictError

#: Generous next to the run CLI's own 2-second poll cadence — long enough
#: that a live process's heartbeat never goes stale by accident under a
#: slow provider call, short enough that a crashed process's lock does not
#: block the next run for long.
STALE_AFTER_SECONDS = 60.0

_SUFFIX = ".write-lock"


class DatabaseWriteLock:
    """Held for the lifetime of one CLI invocation. A no-op for anything
    that is not a SQLite file (`database_file` is `None` for Postgres) —
    a real database server already handles concurrent writers itself."""

    def __init__(self, database_file: Path | None) -> None:
        self._path = None if database_file is None else Path(f"{database_file}{_SUFFIX}")
        #: Whether *this instance* is the one that created the lock file.
        #: Without tracking this, a failed acquire — another process's
        #: lock is still fresh — followed by an unconditional release in a
        #: caller's `finally` block would delete the winning process's
        #: lock, which is worse than not having one at all: a third
        #: process would then see nothing to refuse it.
        self._held = False

    @property
    def path(self) -> Path | None:
        return self._path

    def acquire(self) -> None:
        """Refuses if another process's heartbeat is still fresh; takes
        over a stale lock rather than waiting on it, since nothing here
        can tell "stale" from "will never be refreshed again" except that
        distinction not mattering — a lock nobody is refreshing is not
        protecting anything either way."""
        if self._path is None:
            return
        if self._path.exists():
            age = time.time() - self._path.stat().st_mtime
            if age < STALE_AFTER_SECONDS:
                raise ConflictError(
                    f"Another process appears to be writing to this database right now "
                    f"(its lock was refreshed {age:.0f}s ago).",
                    detail=(
                        f"If nothing else is actually running, delete {self._path} and retry. "
                        f"A lock older than {STALE_AFTER_SECONDS:.0f}s is treated as abandoned "
                        "automatically."
                    ),
                )
            self._path.unlink(missing_ok=True)
        try:
            with self._path.open("x", encoding="utf-8") as handle:
                handle.write(str(os.getpid()))
        except FileExistsError as exc:
            raise ConflictError(
                "Another process started writing to this database a moment ago.",
                detail="Retry — this is the same race a slightly later attempt would not hit.",
            ) from exc
        self._held = True

    def heartbeat(self) -> None:
        """Called once per poll iteration so the lock's age reflects
        whether this process is still actually working, not just whether
        it once started."""
        if self._held and self._path is not None:
            self._path.touch()

    def release(self) -> None:
        """Safe to call unconditionally from a `finally` block, whether or
        not `acquire` ever succeeded: only a lock this instance actually
        holds is removed."""
        if self._held and self._path is not None:
            self._path.unlink(missing_ok=True)
            self._held = False
