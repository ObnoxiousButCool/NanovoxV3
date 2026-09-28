"""Seed the action board from the corpus's own findings, from the command
line (Revised plan Phase 4, porting `add_action` from `04_build_app_data.py`).

Run from ``Code/Backend``, after ingestion, reference import and at least one
extraction run::

    python -m frameworks_drivers.cli.seed_actions

One action is raised per signal type actually raised anywhere in the corpus
(`domain.aggregation.actions.action_items` — the same grouping
`GET /insights/actions` already shows), through `CreateAction`, exactly as a
human raising a card from a playbook link would. Nothing about who owns a
seeded action, when it is due or what was done is invented (D6) — a seeded
card carries a title, evidence, owner team, calls and playbook steps, and
nothing else, until someone edits it.

**This reports what it did. It does not judge.** Every issue key seeded is
named; every key already present is named too, and left alone rather than
duplicated — running this twice against an unchanged corpus produces the
same board, not a doubled one.

The one thing this exits non-zero for without it being a failure is having
nothing to seed from at all — every dated call in the corpus has not been
analysed yet, so no signal exists anywhere to raise a card from. That is not
a broken run; it is the absence of one, exactly as `evaluate_extraction`'s
`EXIT_NOTHING_COMPARED` is not a bad score.
"""

from __future__ import annotations

import asyncio
import sys

from application.use_cases.seed_actions import SeedActionsReport
from domain.errors import NanoVoxInsightsError
from frameworks_drivers.container import build_container, dispose_container
from infrastructure.config.settings import get_settings

EXIT_OK = 0
EXIT_FAILED = 1
#: Distinct from EXIT_FAILED: the corpus has no signal raised anywhere in
#: it — nothing has been analysed yet, or analysis found nothing to act on
#: at all. A caller can tell "seeding broke" from "there is nothing here
#: yet", which are fixed in entirely different places (run the extraction,
#: versus read this report).
EXIT_NOTHING_TO_SEED = 2

_MAX_LISTED = 25


def _out(line: str) -> None:
    sys.stdout.write(f"{line}\n")
    sys.stdout.flush()


def _keys(issue_keys: tuple[str, ...]) -> str:
    listed = ", ".join(issue_keys[:_MAX_LISTED])
    more = f" ... and {len(issue_keys) - _MAX_LISTED} more" if len(issue_keys) > _MAX_LISTED else ""
    return f"{listed}{more}"


def _report(report: SeedActionsReport) -> None:
    if report.found == 0:
        _out("")
        _out("NOTHING TO SEED. No call in the corpus has raised a signal yet —")
        _out("either nothing has been ingested, or nothing has been analysed.")
        _out("Run reference import, ingestion and the extraction pipeline first.")
        return

    _out(f"Found {report.found} action item(s) across the whole corpus.")

    if report.created:
        created_keys = tuple(a.issue_key or "" for a in report.created)
        _out(f"Seeded {len(report.created)}: {_keys(created_keys)}")
    else:
        _out("Seeded 0 — every item found was already seeded.")

    if report.skipped:
        _out(f"Skipped {len(report.skipped)} already seeded: {_keys(report.skipped)}")
    else:
        _out("Skipped 0 — nothing was already seeded.")


def main() -> int:
    settings = get_settings()
    container = build_container(settings)
    try:
        report = asyncio.run(container.seed_actions().execute())
    except NanoVoxInsightsError as error:
        _out(f"Seeding failed: {error.message}")
        if error.detail:
            _out(f"  {error.detail}")
        return EXIT_FAILED
    finally:
        asyncio.run(dispose_container(container))

    _report(report)
    return EXIT_OK if report.found else EXIT_NOTHING_TO_SEED


if __name__ == "__main__":
    raise SystemExit(main())
