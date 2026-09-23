"""Import the workbook's reference (master-data) sheets from the command line.

Run from ``Code/Backend``::

    python -m frameworks_drivers.cli.import_reference

Talks to the real configured database and the real configured workbook path
— unlike the OpenAPI export, this one does connect. Idempotent: safe to
run again after the workbook is re-issued.
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
        result = await container.import_reference_data().execute()
    except NanoVoxInsightsError as exc:
        _out(f"FAILED: {exc.message}")
        return EXIT_FAILED
    finally:
        await dispose_container(container)

    counts = result.counts
    _out(
        "Imported "
        f"{counts.brokers} brokers, {counts.employers} employers, "
        f"{counts.members} members, {counts.employer_contacts} employer "
        f"contacts, {counts.agents} agents, {counts.rules} rules, "
        f"{counts.touchpoints} touchpoints."
    )
    for warning in result.warnings:
        _out(f"warning: {warning}")
    return EXIT_OK


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
