"""`read_workbook_sheets` against a real, minimal xlsx fixture.

`tests/fixtures/sample_workbook.xlsx` holds exactly the parts the reader
touches (no sharedStrings.xml — inline strings only), built by
`build_xlsx_fixture.py`-equivalent logic to prove the zipfile/ElementTree
mechanics work end to end, independent of the row-mapping logic tested
against a plain dict in `test_xlsx_reference_source.py`.
"""

from __future__ import annotations

from pathlib import Path

from infrastructure.reference.workbook_xml import read_workbook_sheets

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "sample_workbook.xlsx"


def test_reads_every_sheet_by_name() -> None:
    sheets = read_workbook_sheets(FIXTURE)

    assert set(sheets) == {"Sheet One", "Sheet Two"}


def test_a_blank_row_is_preserved_as_an_empty_list() -> None:
    """Row 2 has no cells at all — the header search relies on this row
    still occupying a position in the list, not being skipped.
    """
    rows = read_workbook_sheets(FIXTURE)["Sheet One"]

    assert rows[1] == []


def test_header_and_data_rows_read_in_order() -> None:
    rows = read_workbook_sheets(FIXTURE)["Sheet One"]

    assert rows[2] == ["Widget ID", "Widget name", "Count"]
    assert rows[3] == ["WID-01", "Left-handed smoke shifter", "42"]


def test_a_row_missing_a_middle_cell_pads_with_an_empty_string() -> None:
    """WID-02 has no value in column B — a gap, not a shift."""
    rows = read_workbook_sheets(FIXTURE)["Sheet One"]

    assert rows[4] == ["WID-02", "", "7"]


def test_numeric_cells_read_as_their_string_value() -> None:
    rows = read_workbook_sheets(FIXTURE)["Sheet One"]

    assert rows[3][2] == "42"
