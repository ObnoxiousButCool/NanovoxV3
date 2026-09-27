"""Run the extraction pipeline over the corpus, from the command line.

Run from ``Code/Backend``::

    python -m frameworks_drivers.cli.run_extraction
    python -m frameworks_drivers.cli.run_extraction --resume 3
    python -m frameworks_drivers.cli.run_extraction --provider anthropic

Ingest and import_reference must have already run: this works whichever
calls are already in the database. Progress is printed as the run
proceeds; interrupting the process (a crash, a kill) leaves the run
resumable — run again with ``--resume <id>``.

Three safety measures wrap the run itself (``Corpus-v10-Schema-Update.md``'s
finding: a run once left the database failing ``PRAGMA integrity_check``,
with tables reading back each other's rows). A write lock refuses to start
if another invocation's heartbeat is still fresh; the database is backed up
before anything writes; and it is checked again once the run finishes,
whichever way. None of the three explain what caused that corruption — they
bound its cost, so the next occurrence is a restore and a clear signal
rather than a rebuild from nothing.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from domain.errors import NanoVoxInsightsError
from domain.run_progress import RunProgress
from frameworks_drivers.container import build_container, dispose_container
from infrastructure.config.settings import get_settings
from infrastructure.persistence.backup import backup_before_run
from infrastructure.persistence.integrity import OK, check_integrity
from infrastructure.runner.database_write_lock import DatabaseWriteLock

EXIT_OK = 0
EXIT_FAILED = 1
#: The run finished — nothing about the orchestration broke — but more
#: items failed than completed. Distinct from EXIT_FAILED: the process
#: succeeded and the extraction did not, which is a different fact from
#: "could not run this at all" and needs its own code so a caller
#: automating this (CI, a schedule) can tell the two apart rather than
#: reading a quiet EXIT_OK off a run that mostly failed.
EXIT_MOSTLY_FAILED = 2
#: The database failed its post-run integrity check. Takes priority over
#: every other code: whatever else happened, this is the one fact that
#: makes every other result unreliable.
EXIT_DATABASE_CORRUPT = 3

_POLL_SECONDS = 2.0


def _out(line: str) -> None:
    # Flushed per line: a run takes minutes, and redirected to a file an
    # unflushed stdout shows nothing until the process exits.
    sys.stdout.write(f"{line}\n")
    sys.stdout.flush()


def _progress_line(progress: RunProgress) -> str:
    return (
        f"{progress.percent_complete:5.1f}% — "
        f"{progress.completed} completed, {progress.failed} failed, "
        f"{progress.skipped} skipped, {progress.cancelled} cancelled, "
        f"{progress.remaining} remaining"
    )


def _exit_code_for(progress: RunProgress) -> int:
    """The process exit code for a run that finished without the
    orchestration itself breaking.

    More failures than successes is treated as "not worth trusting" rather
    than as the normal cost of resumability: an occasional item failing
    among mostly-completed ones is expected and does not fail the run
    (`RunExtractionOverCorpus`'s own design), but a run that is mostly
    failure is a different fact from a run that mostly worked, and a
    caller automating this needs the exit code to say which.
    """
    if progress.failed > progress.completed:
        return EXIT_MOSTLY_FAILED
    return EXIT_OK


async def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    container = build_container(settings)
    lock = DatabaseWriteLock(settings.database_file)
    exit_code = EXIT_OK
    try:
        lock.acquire()
        backup_path = await backup_before_run(settings.database_file)
        if backup_path is not None:
            _out(f"Backed up the database to {backup_path} before starting.")

        use_case = container.run_extraction_over_corpus()
        reconciled = await use_case.reconcile_interrupted()
        if reconciled:
            _out(f"Marked interrupted from a previous process: {list(reconciled)}")

        if args.resume is not None:
            run_id = args.resume
            await use_case.resume(run_id)
        else:
            run_id = await use_case.start(provider_name=args.provider, model=args.model)
        _out(f"Run {run_id} started.")

        while True:
            await asyncio.sleep(_POLL_SECONDS)
            lock.heartbeat()
            view = await use_case.status(run_id)
            if view is None:  # pragma: no cover - the run this process just created
                raise NanoVoxInsightsError(f"Run {run_id} disappeared mid-run.")
            _out(_progress_line(view.progress))
            if view.progress.is_exhausted:
                _out(f"Run {run_id} finished: {view.record.status.value}.")
                break

        exit_code = _exit_code_for(view.progress)
        if exit_code == EXIT_MOSTLY_FAILED:
            _out(
                f"MOSTLY FAILED: {view.progress.failed} of {view.progress.total} call(s) failed, "
                f"only {view.progress.completed} completed. The run finished; the extraction "
                "did not — check the failure reasons before trusting anything built on this run."
            )
    except NanoVoxInsightsError as exc:
        _out(f"FAILED: {exc.message}")
        exit_code = EXIT_FAILED
    finally:
        integrity = await check_integrity(container.engine)
        if integrity != OK:
            _out(f"DATABASE CORRUPT: {integrity}")
            exit_code = EXIT_DATABASE_CORRUPT
        lock.release()
        await container.background_runner.shutdown()
        await dispose_container(container)

    return exit_code


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", type=int, default=None, help="Resume an existing run by id.")
    parser.add_argument(
        "--provider", default=None, help="Model provider name (default: the configured one)."
    )
    parser.add_argument("--model", default=None, help="Model override for the chosen provider.")
    return parser.parse_args(argv)


def main() -> int:
    return asyncio.run(_run(_parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
