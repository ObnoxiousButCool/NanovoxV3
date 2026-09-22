"""Ingest every call from the configured transcript source, from the command line.

Run from ``Code/Backend``::

    python -m frameworks_drivers.cli.ingest_transcripts

Run `import_reference` first: caller resolution reads the reference data it
imports. Idempotent: safe to run again after the corpus is re-issued.
"""

from __future__ import annotations

import asyncio
import sys

from domain.errors import NanoVoxInsightsError
from frameworks_drivers.container import build_container, dispose_container
from infrastructure.config.settings import get_settings

EXIT_OK = 0
EXIT_FAILED = 1


def _out(line: str) -> None:
    sys.stdout.write(f"{line}\n")


async def _run() -> int:
    settings = get_settings()
    container = build_container(settings)
    try:
        counts = await container.ingest_transcripts().execute()
    except NanoVoxInsightsError as exc:
        _out(f"FAILED: {exc.message}")
        return EXIT_FAILED
    finally:
        await dispose_container(container)

    _out(
        f"Ingested {counts.total} calls: {counts.resolved} resolved, "
        f"{counts.caller_unresolved} caller-unresolved, "
        f"{counts.agent_unknown} agent-unknown, "
        f"{counts.speaker_unresolved} speaker-unresolved."
    )
    return EXIT_OK


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
