"""`DatabaseWriteLock` — the heartbeat guard against two processes writing
to the same SQLite file at once."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from domain.errors import ConflictError
from infrastructure.runner.database_write_lock import STALE_AFTER_SECONDS, DatabaseWriteLock


def test_a_none_database_file_is_a_no_op() -> None:
    """Postgres has no file to lock, and its own concurrency control."""
    lock = DatabaseWriteLock(None)

    lock.acquire()  # must not raise
    lock.heartbeat()
    lock.release()

    assert lock.path is None


def test_acquiring_creates_a_lock_file_naming_this_process(tmp_path: Path) -> None:
    database_file = tmp_path / "nanovox_insights.db"
    lock = DatabaseWriteLock(database_file)

    lock.acquire()

    assert lock.path is not None
    assert lock.path.read_text(encoding="utf-8") == str(os.getpid())


def test_releasing_removes_the_lock_file(tmp_path: Path) -> None:
    lock = DatabaseWriteLock(tmp_path / "nanovox_insights.db")
    lock.acquire()

    lock.release()

    assert lock.path is not None
    assert not lock.path.exists()


def test_releasing_a_lock_never_acquired_does_not_raise(tmp_path: Path) -> None:
    DatabaseWriteLock(tmp_path / "nanovox_insights.db").release()


def test_a_fresh_lock_refuses_a_second_acquire(tmp_path: Path) -> None:
    database_file = tmp_path / "nanovox_insights.db"
    first = DatabaseWriteLock(database_file)
    first.acquire()

    second = DatabaseWriteLock(database_file)
    with pytest.raises(ConflictError, match="Another process appears to be writing"):
        second.acquire()


def test_releasing_a_lock_this_instance_never_held_leaves_the_real_owners_alone(
    tmp_path: Path,
) -> None:
    """A failed acquire must not be able to delete the lock that beat it —
    a caller's `finally: lock.release()` runs whether acquire succeeded or
    not, and a real owner's lock disappearing there would let a third
    process see nothing to refuse it."""
    database_file = tmp_path / "nanovox_insights.db"
    winner = DatabaseWriteLock(database_file)
    winner.acquire()

    loser = DatabaseWriteLock(database_file)
    with pytest.raises(ConflictError):
        loser.acquire()
    loser.release()  # as a caller's finally block would call it regardless

    assert winner.path is not None
    assert winner.path.exists()


def test_a_stale_lock_is_taken_over_rather_than_blocking(tmp_path: Path) -> None:
    database_file = tmp_path / "nanovox_insights.db"
    first = DatabaseWriteLock(database_file)
    first.acquire()
    assert first.path is not None
    stale_mtime = time.time() - STALE_AFTER_SECONDS - 1
    os.utime(first.path, (stale_mtime, stale_mtime))

    second = DatabaseWriteLock(database_file)
    second.acquire()  # must not raise — the first process is presumed dead

    assert second.path is not None
    assert second.path.read_text(encoding="utf-8") == str(os.getpid())


def test_heartbeat_refreshes_the_lock_so_it_does_not_go_stale(tmp_path: Path) -> None:
    database_file = tmp_path / "nanovox_insights.db"
    lock = DatabaseWriteLock(database_file)
    lock.acquire()
    assert lock.path is not None
    old_mtime = time.time() - STALE_AFTER_SECONDS - 1
    os.utime(lock.path, (old_mtime, old_mtime))

    lock.heartbeat()

    age = time.time() - lock.path.stat().st_mtime
    assert age < STALE_AFTER_SECONDS
