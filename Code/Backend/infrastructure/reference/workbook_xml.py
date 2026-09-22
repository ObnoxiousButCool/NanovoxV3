"""Read an xlsx workbook's sheets into plain rows of strings.

Parses the xlsx container directly (zipfile + ElementTree) rather than
through a third-party library, so this needs nothing but the standard
library — ported from the prototype's `tools/01_read_workbook.py`, which
made the same choice for the same reason.

The workbook is written by a tool that never evaluates formulas, so a
formula cell with no cached value reads as an empty string here. Nothing in
this module tries to evaluate one; `domain/reference_derivations.py`
recomputes the handful that matter from real, non-formula cells.

Uses `xml.etree.ElementTree` rather than `defusedxml` (ruff's S314):
deliberate, not an oversight. The input is the operator-supplied build-bible
workbook (decision D8's "client material"), read from a local path this
process's own configuration names — never a file an untrusted party
uploaded or a URL fetched at request time. `defusedxml` guards against a
threat model (an attacker choosing the XML) that doesn't apply here.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

_COLUMN_LETTERS = re.compile(r"([A-Z]+)")

Sheets = dict[str, list[list[str]]]


def _column_index(cell_ref: str | None) -> int:
    """1-based column index from a cell reference like ``C7`` → 3."""
    match = _COLUMN_LETTERS.match(cell_ref or "A")
    letters = match.group(1) if match else "A"
    index = 0
    for letter in letters:
        index = index * 26 + (ord(letter) - 64)
    return index


def _cell_text(cell: ET.Element, shared: list[str]) -> str:
    kind = cell.get("t")
    value = cell.find(_NS + "v")
    if kind == "s" and value is not None and value.text is not None:
        return shared[int(value.text)]
    inline = cell.find(_NS + "is")
    if inline is not None:
        return "".join(t.text or "" for t in inline.iter(_NS + "t"))
    return (value.text or "") if value is not None else ""


def read_workbook_sheets(path: Path) -> Sheets:
    """Every sheet in the workbook, as rows of cell text, sparse-padded.

    A row shorter than its widest neighbour simply has fewer trailing
    columns — callers index by header name, not by a fixed row width.
    """
    with zipfile.ZipFile(path) as archive:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))  # noqa: S314 — see module docstring
            for item in root.findall(_NS + "si"):
                shared.append("".join(t.text or "" for t in item.iter(_NS + "t")))

        workbook = ET.fromstring(archive.read("xl/workbook.xml"))  # noqa: S314 — see module docstring
        rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))  # noqa: S314 — see module docstring
        target_by_id = {rel.get("Id"): rel.get("Target") for rel in rels}

        sheet_paths: list[tuple[str, str]] = []
        sheets_element = workbook.find(_NS + "sheets")
        if sheets_element is not None:
            for sheet in sheets_element:
                name = sheet.get("name") or ""
                target = target_by_id.get(sheet.get(_REL + "id")) or ""
                sheet_paths.append((name, "xl/" + target.lstrip("/").replace("xl/", "", 1)))

        sheets: Sheets = {}
        for name, sheet_path in sheet_paths:
            sheet_root = ET.fromstring(archive.read(sheet_path))  # noqa: S314 — see module docstring
            rows: list[list[str]] = []
            for row in sheet_root.iter(_NS + "row"):
                values: list[str] = []
                for cell in row.findall(_NS + "c"):
                    index = _column_index(cell.get("r"))
                    while len(values) < index - 1:
                        values.append("")
                    values.append(_cell_text(cell, shared))
                rows.append(values)
            sheets[name] = rows

    return sheets
