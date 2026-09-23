"""`config/dashboard.yaml` against the workbook it was transcribed from.

§3.0: the workbook wins on definitions. That principle is only worth
anything if something enforces it, because a threshold does not fail when it
drifts — it publishes. A `min_n` typed as 3 instead of 30 produces a figure
that looks exactly like a figure, from ten calls, and the first person to
notice is whoever has to defend it in front of a client.

So this reads the real Metrics, Call Quality Framework and Questions Worth
Asking sheets and fails if any shipped threshold has moved away from them.
Two things it catches that a human reviewer will not: a revision of the
workbook that retunes a number, and a metric added to the sheet that nobody
added to the config — the second being the failure mode that leaves a
published figure with no gate at all.

The corpus lives in `Documents/` and is tracked, so this runs by default
everywhere. It is guarded rather than unguarded only so a deployment that
points `WORKBOOK_PATH` elsewhere does not fail on a file it never had; if it
skips in this checkout, treat that as red, not as green.
"""

from __future__ import annotations

import re

import pytest

from domain.dashboard_config import DashboardConfig
from infrastructure.config.dashboard_config import load_dashboard_config
from infrastructure.config.paths import DEFAULT_CONFIG_DIR, DEFAULT_WORKBOOK_PATH
from infrastructure.reference.workbook_xml import Sheets, read_workbook_sheets

pytestmark = pytest.mark.skipif(
    not DEFAULT_WORKBOOK_PATH.exists(),
    reason="corpus not found — expected it under Documents/ (see infrastructure/config/paths.py)",
)

_MIN_N = re.compile(r"^(\d+)\s*(.*)$")
_WINDOW = re.compile(r"^(\d+)wk$")
#: The sheet writes "n/a" for a per-call row and an em dash for a base
#: measure with no gate. Both mean the same thing here: never withheld.
_NO_THRESHOLD = {"", "n/a", "—", "-"}


@pytest.fixture(scope="module")
def sheets() -> Sheets:
    return read_workbook_sheets(DEFAULT_WORKBOOK_PATH)


@pytest.fixture(scope="module")
def shipped() -> DashboardConfig:
    return load_dashboard_config(DEFAULT_CONFIG_DIR / "dashboard.yaml")


def _header_row(rows: list[list[str]], first_cell: str) -> int:
    """The header's index, found by its own first-column heading.

    Same idiom as the reference and ground-truth sources: a fixed row index
    would misread a revision that adds a line of preamble, and misread it
    silently.
    """
    for index, row in enumerate(rows):
        if row and row[0].strip() == first_cell:
            return index
    raise AssertionError(f"No header row starting {first_cell!r} — the sheet's shape has changed.")


def _parse_min_n(cell: str) -> tuple[int | None, str]:
    """ "30" -> (30, "calls"); "30 triggers" -> (30, "triggers"); "n/a" -> (None, "calls").

    A bare number counts calls: the sheet qualifies exactly three of its
    fourteen rows and leaves the rest bare.
    """
    text = cell.strip()
    if text.lower() in _NO_THRESHOLD:
        return None, "calls"
    match = _MIN_N.match(text)
    assert match is not None, f"Unparsed Min n cell {cell!r} — the sheet has a new form."
    return int(match.group(1)), match.group(2).strip() or "calls"


def _parse_window(cell: str) -> int | None:
    """ "12wk" -> 12. "per call" and "any" have no window of their own."""
    text = cell.strip()
    if text.lower() in {"per call", "any", ""}:
        return None
    match = _WINDOW.match(text)
    assert match is not None, f"Unparsed Window cell {cell!r} — the sheet has a new form."
    return int(match.group(1))


def _metrics_sheet(sheets: Sheets) -> dict[str, tuple[int | None, int | None, str]]:
    """{sheet row label: (window_weeks, min_n, counts)} straight from the sheet."""
    rows = sheets["Metrics"]
    header = rows[_header_row(rows, "#")]
    number, window, min_n = (header.index(name) for name in ("#", "Window", "Min n"))

    parsed: dict[str, tuple[int | None, int | None, str]] = {}
    for row in rows[_header_row(rows, "#") + 1 :]:
        label = row[number].strip() if len(row) > number else ""
        # The sheet ends with a "Dropped" note in the first column and nothing
        # in the Min n column; a real metric row always has both.
        if not label or len(row) <= min_n or label == "Dropped":
            continue
        count, counts = _parse_min_n(row[min_n])
        parsed[label] = (_parse_window(row[window]), count, counts)
    return parsed


def test_the_config_covers_every_metric_the_sheet_publishes(
    sheets: Sheets, shipped: DashboardConfig
) -> None:
    """The important half of this file.

    A drifted number is caught below; a metric present on the sheet and
    absent from the config is caught here, and it is the worse failure —
    `metric()` raises on an unknown key, so the gap only surfaces when an
    aggregation for that metric is written, which may be months later.
    """
    assert {metric.sheet_row for metric in shipped.metrics} == set(_metrics_sheet(sheets))


def test_every_min_n_and_window_matches_the_metrics_sheet(
    sheets: Sheets, shipped: DashboardConfig
) -> None:
    from_sheet = _metrics_sheet(sheets)

    mismatched = [
        f"{metric.sheet_row} {metric.name}: config says "
        f"(window={metric.window_weeks}, min_n={metric.min_n}, counts={metric.counts!r}), "
        f"sheet says {from_sheet[metric.sheet_row]}"
        for metric in shipped.metrics
        if (metric.window_weeks, metric.min_n, metric.counts) != from_sheet[metric.sheet_row]
    ]

    assert mismatched == []


def test_there_is_no_global_min_n(shipped: DashboardConfig) -> None:
    """Min n is per metric. The sheet gives four distinct values across
    fourteen rows, so any single global number is wrong for most of them —
    which is why the early `min_n: 5` was removed on 2026-09-22.
    """
    distinct = {metric.min_n for metric in shipped.metrics if metric.min_n is not None}

    assert len(distinct) > 1


def test_the_quality_bands_match_the_call_quality_framework(
    sheets: Sheets, shipped: DashboardConfig
) -> None:
    """Stage 4: "GOOD at 86 and above, AVERAGE at 60 and above, POOR below 60.\""""
    banding = next(
        cell
        for row in sheets["Call Quality Framework"]
        for cell in row
        if "GOOD at" in cell and "AVERAGE at" in cell
    )
    good, average, poor = (int(n) for n in re.findall(r"\b(\d+)\b", banding))

    assert shipped.quality_bands.good_min == good
    assert shipped.quality_bands.average_min == average
    assert poor == average, "the sheet's POOR boundary should be the AVERAGE floor"


def test_the_broker_pattern_test_matches_trigger_rule_two(
    sheets: Sheets, shipped: DashboardConfig
) -> None:
    """Questions Worth Asking, rule 2: ">=3 calls name the same broker
    adversely within a rolling 12 weeks, from >=2 different employers".

    All three numbers, from the one sentence that states them together. The
    prototype attributes this threshold to the workbook in its own copy
    ("the workbook's own pattern threshold of three adverse mentions from
    two employers"); this is that attribution checked rather than trusted.
    """
    rule = next(
        cell
        for row in sheets["Questions Worth Asking"]
        for cell in row
        if "name the same broker adversely" in cell
    )
    mentions, weeks, employers = (int(n) for n in re.findall(r"\b(\d+)\b", rule))
    test = shipped.broker_pattern_test

    assert test.min_adverse_mentions == mentions
    assert test.min_distinct_employers == employers
    assert test.window_weeks == weeks


def test_the_peer_size_bands_are_not_the_fee_bands(
    sheets: Sheets, shipped: DashboardConfig
) -> None:
    """Rule P-33's fee bands (2-8, 9-20, 21-199, 200+ eligible employees) are
    in the workbook. The peer size bands are not — they are our own, over
    enrolled lives. Asserting the two differ keeps a later editor from
    "correcting" one into the other, which would compare every group under
    25 lives against the wrong median.
    """
    fee_rule = next(
        cell
        for row in sheets["Rules — Program"]
        for cell in row
        if "Monthly administration fee banded by headcount" in cell
    )
    ceilings = [int(top) for top in re.findall(r"\(\d+[^\d)]+(\d+)\)", fee_rule)]
    assert ceilings == [8, 20, 199], f"rule P-33's fee bands have changed: {fee_rule}"

    boundaries = [band.max_lives for band in shipped.peer_size_bands]
    assert boundaries == [24, 74, 199, None]
    assert boundaries[: len(ceilings)] != ceilings, "the peer bands are not the fee bands"
