"""Raw PDF text extraction and structural splitting — no interpretation.

Shared by `PdfCorpusSource` and `PdfAnswerKeySource`. Deliberately does not
decide which lines mean what: it splits the PDF into one block per call,
and each block into three raw regions (header lines, dialogue text, the
`CALL TAGS` block). Which fields inside those regions are legitimate input
versus answer key is decided separately by each adapter, not here — so
this module carries no answer-key-shaped data at all, and there is nothing
in it for the import-linter contract in `pyproject.toml` to need to forbid.
"""

from __future__ import annotations

import re
from pathlib import Path

from pypdf import PdfReader

_CALL_HEADER = re.compile(r"C-\d{4} — ")
# The running header/footer repeated on every page. Removed globally before
# splitting into calls, since it can land mid-block at a page break (see
# calls C-0033, C-0046, C-0064 in batch 1, where it falls between the
# dialogue and the CALL TAGS block rather than at a block boundary).
_PAGE_FURNITURE = re.compile(r"NanoVox — Corpus v9 · transcripts batch 1\n\d+\n?")


def extract_call_blocks(path: Path) -> tuple[str, ...]:
    """Every call's raw text, in order, with page furniture removed."""
    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return split_into_call_blocks(text)


def split_into_call_blocks(text: str) -> tuple[str, ...]:
    """The pure half of `extract_call_blocks` — no PDF reading, just string
    splitting, so it's testable against plain-text fixtures.
    """
    text = _PAGE_FURNITURE.sub("", text)
    parts = re.split(r"\n(?=C-\d{4} — )", text)
    return tuple(part for part in parts if _CALL_HEADER.match(part))


def split_call_block(block: str) -> tuple[tuple[str, str, str], str, str]:
    """`(header_lines, dialogue_text, call_tags_text)` — a structural split only.

    The header is the first three *non-blank* lines: a page break can leave
    a stray blank line inside the header region (batch 1 has three such
    calls), so header lines are collected by skipping blanks rather than by
    a fixed line index. `dialogue_text` is everything between the header
    and the `CALL TAGS` marker; `call_tags_text` is everything from that
    marker to the end of the block, verbatim.
    """
    lines = block.split("\n")
    header: list[str] = []
    index = 0
    while len(header) < 3 and index < len(lines):
        if lines[index].strip():
            header.append(lines[index])
        index += 1

    rest = "\n".join(lines[index:])
    dialogue_text, marker, after_marker = rest.partition("CALL TAGS")
    call_tags_text = marker + after_marker  # keep the "CALL TAGS" line itself
    return (header[0], header[1], header[2]), dialogue_text, call_tags_text


def call_reference(block: str) -> str:
    """The call id a block starts with, e.g. ``C-0001``."""
    match = _CALL_HEADER.match(block)
    if match is None:  # pragma: no cover - guarded by extract_call_blocks's filter
        raise ValueError("block does not start with a call header")
    return block[: match.end() - 3]
