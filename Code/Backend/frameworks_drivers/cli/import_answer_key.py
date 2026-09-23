"""Import the answer key from the command line, and report the reconciliation.

Run from ``Code/Backend``, after ``import_reference`` and ``ingest_transcripts``::

    python -m frameworks_drivers.cli.import_answer_key

Order matters: `ground_truth` hangs off `calls.id`, so a call that has not
been ingested has nowhere to put its answer and is reported as unmatched.

Idempotent — safe to run again after the workbook is re-issued.

**A disagreement is not a warning to skim past.** The tracker and the corpus
PDF state the same five fields about the same calls, and at batch 1 they
should agree on every one of them. Any disagreement, and any call present in
one source but not the other, most likely means the workbook and the PDF are
different revisions — plan §11's trap, where both pairings are internally
consistent and nothing else gives it away. This command exits non-zero when
that happens, so a pipeline that runs it does not sail past the one check
that would have caught it.
"""

from __future__ import annotations

import asyncio
import sys

from application.use_cases.import_answer_key import AnswerKeyImportResult
from domain.errors import NanoVoxInsightsError
from frameworks_drivers.container import build_container, dispose_container
from infrastructure.config.settings import get_settings

EXIT_OK = 0
EXIT_FAILED = 1
#: Distinct from EXIT_FAILED: the import itself worked, the two sources do
#: not agree. Worth its own code so a caller can tell "could not read the
#: workbook" from "the workbook and the PDF disagree".
EXIT_NOT_RECONCILED = 2

_MAX_LISTED = 20


def _out(line: str) -> None:
    sys.stdout.write(f"{line}\n")


def _report(result: AnswerKeyImportResult) -> None:
    counts = result.counts
    _out(f"Imported {counts.written} answer-key rows.")

    for warning in result.warnings:
        _out(f"warning: {warning}")

    if counts.unmatched:
        _out(
            f"unmatched: {len(counts.unmatched)} tracker row(s) name a call that has not "
            f"been ingested — run ingest_transcripts first: "
            f"{', '.join(counts.unmatched[:_MAX_LISTED])}"
        )

    if result.missing_from_tracker:
        _out(
            f"in the PDF but not the tracker: "
            f"{', '.join(result.missing_from_tracker[:_MAX_LISTED])}"
        )
    if result.missing_from_pdf:
        _out(f"in the tracker but not the PDF: {', '.join(result.missing_from_pdf[:_MAX_LISTED])}")

    if result.disagreements:
        _out(f"{len(result.disagreements)} disagreement(s) between the tracker and the PDF:")
        for disagreement in result.disagreements[:_MAX_LISTED]:
            _out(f"  {disagreement.describe()}")
        remaining = len(result.disagreements) - _MAX_LISTED
        if remaining > 0:
            _out(f"  ... and {remaining} more")

    if result.reconciled:
        _out("Reconciled: the tracker and the PDF agree on every shared field.")
    else:
        _out(
            "NOT RECONCILED — most likely the workbook and the transcripts PDF are "
            "different revisions. Check the pair before trusting any figure built on "
            "this corpus (plan §11)."
        )


async def _run() -> int:
    settings = get_settings()
    container = build_container(settings)
    try:
        result = await container.import_answer_key().execute()
    except NanoVoxInsightsError as exc:
        _out(f"FAILED: {exc.message}")
        return EXIT_FAILED
    finally:
        await dispose_container(container)

    _report(result)
    return EXIT_OK if result.reconciled else EXIT_NOT_RECONCILED


def main() -> int:
    return asyncio.run(_run())


if __name__ == "__main__":
    raise SystemExit(main())
