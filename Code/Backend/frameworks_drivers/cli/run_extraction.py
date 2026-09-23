"""Run the extraction pipeline over the corpus, from the command line.

Run from ``Code/Backend``::

    python -m frameworks_drivers.cli.run_extraction
    python -m frameworks_drivers.cli.run_extraction --resume 3
    python -m frameworks_drivers.cli.run_extraction --provider anthropic

Ingest and import_reference must have already run: this works whichever
calls are already in the database. Progress is printed as the run
proceeds; interrupting the process (a crash, a kill) leaves the run
resumable — run again with ``--resume <id>``.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from domain.errors import NanoVoxInsightsError
from domain.run_progress import RunProgress
from frameworks_drivers.container import build_container, dispose_container
from infrastructure.config.settings import get_settings

EXIT_OK = 0
EXIT_FAILED = 1

_POLL_SECONDS = 2.0


def _out(line: str) -> None:
    sys.stdout.write(f"{line}\n")


def _progress_line(progress: RunProgress) -> str:
    return (
        f"{progress.percent_complete:5.1f}% — "
        f"{progress.completed} completed, {progress.failed} failed, "
        f"{progress.skipped} skipped, {progress.cancelled} cancelled, "
        f"{progress.remaining} remaining"
    )


async def _run(args: argparse.Namespace) -> int:
    settings = get_settings()
    container = build_container(settings)
    try:
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
            view = await use_case.status(run_id)
            if view is None:  # pragma: no cover - the run this process just created
                raise NanoVoxInsightsError(f"Run {run_id} disappeared mid-run.")
            _out(_progress_line(view.progress))
            if view.progress.is_exhausted:
                _out(f"Run {run_id} finished: {view.record.status.value}.")
                break
    except NanoVoxInsightsError as exc:
        _out(f"FAILED: {exc.message}")
        return EXIT_FAILED
    finally:
        await container.background_runner.shutdown()
        await dispose_container(container)

    return EXIT_OK


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
