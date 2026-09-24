"""Score the pipeline against the answer key, from the command line.

Run from ``Code/Backend``, after the three imports and at least one
extraction run::

    python -m frameworks_drivers.cli.evaluate_extraction

Phase 5's gate. The numbers this prints go to Minnie before any screen is
built on the fields behind them, because a field with poor agreement means a
screen that shows poor data — confidently, with a call-id drawer behind it.

**This reports. It does not judge.** There is deliberately no pass mark: no
threshold is applied, nothing exits non-zero for a low agreement rate, and
no field is labelled good or bad. What counts as good enough is decided with
the numbers in hand, together, and a harness that graded its own subject
would be the last place to notice it had the bar wrong.

The one thing it *does* exit non-zero for is having nothing to compare —
which is not a bad score, it is the absence of one.

**Every figure is printed with its coverage.** An agreement of 100% over
four calls and one over ninety-eight are the same number and different
findings, and whichever a reader assumes is the one that will mislead them.
"""

from __future__ import annotations

import asyncio
import sys

from application.use_cases.evaluate_extraction import EvaluationReport
from domain.errors import NanoVoxInsightsError
from domain.evaluation.insight_dependencies import UNMAPPED_FIELDS, insights_resting_on
from frameworks_drivers.container import build_container, dispose_container
from infrastructure.config.settings import get_settings

EXIT_OK = 0
EXIT_FAILED = 1
#: Distinct from EXIT_FAILED: the harness ran, and there was nothing to
#: compare — no extraction stored for any call with an answer. A caller can
#: then tell "the evaluation broke" from "the pipeline has not run", which
#: are fixed in entirely different places.
EXIT_NOTHING_COMPARED = 2

_MAX_LISTED = 20


def _out(line: str) -> None:
    sys.stdout.write(f"{line}\n")


def _report(report: EvaluationReport) -> None:
    _out(
        f"Scored {report.scored} of {report.calls} call(s) with an answer key "
        f"({report.coverage:.0%} coverage)."
    )

    if report.unscored_calls:
        listed = ", ".join(report.unscored_calls[:_MAX_LISTED])
        more = (
            f" ... and {len(report.unscored_calls) - _MAX_LISTED} more"
            if len(report.unscored_calls) > _MAX_LISTED
            else ""
        )
        _out(f"  No pipeline output for {len(report.unscored_calls)} call(s): {listed}{more}")

    if not report.comparable:
        _out("")
        _out("NOTHING COMPARED. Every field is unscored — the pipeline has stored no")
        _out("output for any call that has an answer. Run the extraction first.")
        return

    _out("")
    _out("Agreement by layer (the layer is what you fix):")
    for layer in report.layers:
        rate = "no comparison" if layer.rate is None else f"{layer.rate:.0%}"
        weakest = layer.weakest
        trailing = f" — weakest: {weakest.field}" if weakest is not None else ""
        _out(f"  {layer.layer}: {rate} over {layer.comparable} comparison(s){trailing}")

    _out("")
    _out("Agreement by field, worst first — with what each one holds up (§9):")
    for field in sorted(report.fields, key=lambda f: (f.rate is not None, f.rate or 0.0, f.field)):
        _out(f"  {field.summary}")
        at_risk = insights_resting_on(field.field)
        if at_risk:
            named = ", ".join(f"{i.number} {i.name} ({i.screen})" for i in at_risk)
            _out(f"    holds up: {named}")
        elif field.field in UNMAPPED_FIELDS:
            _out("    holds up: nothing mapped — see UNMAPPED_FIELDS, a question for the check-in")

    _out("")
    _out("Not scored — the answer key records these and the pipeline does not produce them:")
    for entry in report.unscored_fields:
        _out(f"  {entry.field}: {entry.why}")

    _diagnostics(report)

    _out("")
    _out("No pass mark is applied. Which fields are good enough is decided with")
    _out("these numbers in hand, not here (plan §8 Phase 5).")


def _diagnostics(report: EvaluationReport) -> None:
    """How much to trust the figures above.

    Printed after the agreement numbers and before the closing note, because
    each of these is a way the numbers can be quietly weaker than they look
    — a score built on refused markers, an employer figure missing its
    unresolvable callers, a cost that is really a floor.
    """
    diagnostics = report.diagnostics
    if diagnostics is None:
        return

    _out("")
    _out("Diagnostics — how much to trust the above:")

    if diagnostics.markers_raised == 0:
        _out("  Evidence: no marker has been raised, so nothing has been verified.")
    else:
        rate = diagnostics.rejection_rate or 0.0
        _out(f"  Evidence: {diagnostics.markers_raised} marker(s) raised, {rate:.0%} refused.")
        for reason, count in diagnostics.rejected_evidence:
            _out(f"    {reason}: {count}")
        if not diagnostics.rejected_evidence:
            _out("    none refused")

    unresolved = diagnostics.unresolved_callers
    if unresolved:
        listed = ", ".join(unresolved[:_MAX_LISTED])
        more = (
            f" ... and {len(unresolved) - _MAX_LISTED} more"
            if len(unresolved) > _MAX_LISTED
            else ""
        )
        _out(
            f"  Unresolved callers: {len(unresolved)} call(s) — excluded from every "
            f"employer figure, and never linkable to a follow-up: {listed}{more}"
        )
    else:
        _out("  Unresolved callers: none.")

    cost = diagnostics.last_run_cost
    _out(f"  Last run: {cost.summary}" if cost is not None else "  Last run: none recorded.")


def main() -> int:
    settings = get_settings()
    container = build_container(settings)
    try:
        report = asyncio.run(container.evaluate_extraction().execute())
    except NanoVoxInsightsError as error:
        _out(f"Evaluation failed: {error.message}")
        if error.detail:
            _out(f"  {error.detail}")
        return EXIT_FAILED
    finally:
        asyncio.run(dispose_container(container))

    _report(report)
    return EXIT_OK if report.comparable else EXIT_NOTHING_COMPARED


if __name__ == "__main__":
    raise SystemExit(main())
