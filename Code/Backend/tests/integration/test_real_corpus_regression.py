"""Regression guard against the real corpus: confirms `data/source/` holds
the matched pair the plan requires — workbook `_2` (the 17 Sep 2026
re-issue) with transcripts PDF `_1` — not an earlier, internally-consistent
but silently mismatched revision (plan §11's known trap).

Skipped when the workbook isn't present: it's git-ignored client material
(plan §3.2, decision D8), so CI has nothing to read. This runs where it
matters — locally, on the machine that actually has the corpus.
"""

from __future__ import annotations

import pytest

from infrastructure.config.paths import DEFAULT_WORKBOOK_PATH
from infrastructure.reference.xlsx_reference_source import XlsxReferenceSource

pytestmark = pytest.mark.skipif(
    not DEFAULT_WORKBOOK_PATH.exists(),
    reason="data/source/ workbook not present locally (git-ignored, decision D8)",
)


def test_c0001s_caller_is_the_17_sep_reissue_not_the_original() -> None:
    """The 17 Sep re-issue reassigned C-0001's caller from CB-7700001
    (Rowan Hollis, the original revision) to CB-7700205 (Leon Castellano).
    Both member references exist in bible_2 — CB-7700001 didn't disappear,
    it was simply reassigned to an unrelated member — so this checks both
    directions: the new caller is who it should be, and the old reference
    isn't still holding the old name.
    """
    dataset = XlsxReferenceSource(DEFAULT_WORKBOOK_PATH).read()
    members = {m.reference: m.name for m in dataset.members}

    assert members.get("CB-7700205") == "Leon Castellano"
    assert members.get("CB-7700001") == "Omar Liu"
    assert members.get("CB-7700001") != "Rowan Hollis"
