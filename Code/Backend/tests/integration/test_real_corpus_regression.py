"""Regression guard against the real corpus: confirms `Documents/` holds
the matched pair the plan requires — workbook `_2` (the 17 Sep 2026
re-issue) with transcripts PDF `_1` — not an earlier, internally-consistent
but silently mismatched revision (plan §11's known trap).

The workbook is tracked under Documents/, so this runs on any checkout
rather than only on a machine that happens to hold the corpus.
"""

from __future__ import annotations

import pytest

from infrastructure.config.paths import DEFAULT_WORKBOOK_PATH
from infrastructure.reference.xlsx_reference_source import XlsxReferenceSource

pytestmark = pytest.mark.skipif(
    not DEFAULT_WORKBOOK_PATH.exists(),
    reason="workbook not found — expected it under Documents/ (see infrastructure/config/paths.py)",
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
