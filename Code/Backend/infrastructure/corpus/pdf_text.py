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

from domain.errors import ValidationError

_CALL_HEADER = re.compile(r"C-\d{4} — ")
# The running header/footer repeated on every page. Removed globally before
# splitting into calls, since it can land mid-block at a page break (see
# calls C-0033, C-0046, C-0064 in batch 1, where it falls between the
# dialogue and the CALL TAGS block rather than at a block boundary).
#
# Line-anchored on the constant "NanoVox — Corpus v9 ·" prefix rather than
# the exact batch label that follows it: each batch's PDF has printed a
# different footer — "transcripts batch 1", "transcripts batch 1 rev-2",
# "transcripts batch 2a", "batch 3 (C-0151 to C-0200 of 600)" — and a version
# hardcoded to one of them silently leaves the others in the dialogue text.
# A previous version of this pattern did exactly that: it matched only
# "batch 1" and left page furniture glued onto 134 of batch 1 rev-2's ~1,700
# turns, undetected until that revision arrived. The optional trailing
# `\d+` line covers the page number when it renders on its own line; some
# pages instead render it glued onto the footer's own line (e.g. "...rev-2
# 2"), which the greedy `.*$` on the footer line already consumes.
_PAGE_FURNITURE = re.compile(r"^NanoVox — Corpus v9 ·.*$\n?(?:^\d+$\n?)?", re.MULTILINE)


def extract_call_blocks(path: Path) -> tuple[str, ...]:
    """Every call's raw text, in order, with page furniture removed."""
    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    return split_into_call_blocks(text)


def discover_batch_pdfs(directory: Path) -> tuple[Path, ...]:
    """Every current batch's PDF in `directory`, sorted by name.

    Non-recursive: a superseded revision kept in `directory/superseded/`
    (Documents/notes/Corpus-v10-Schema-Update.md) is deliberately not found by this glob,
    so it can sit in the tree as a regression fixture without ever being
    ingested alongside its replacement.
    """
    return tuple(sorted(directory.glob("*.pdf")))


def extract_call_blocks_across(paths: tuple[Path, ...]) -> tuple[str, ...]:
    """Every call's raw text across several PDFs, in file order.

    The corpus arrives in batches, each its own PDF with disjoint call
    references — C-0001 to C-0100 in one file, C-0101 to C-0150 in the
    next, and so on toward the 600-call target. A call reference appearing
    in more than one file is refused rather than silently taking whichever
    file happened to be read last: nothing here can tell which copy is
    current.
    """
    blocks: list[str] = []
    seen: dict[str, Path] = {}
    for path in paths:
        for block in extract_call_blocks(path):
            reference = call_reference(block)
            if reference in seen:
                raise ValidationError(
                    f"Call {reference} appears in more than one corpus PDF.",
                    detail=f"Found in both {seen[reference].name!r} and {path.name!r}.",
                )
            seen[reference] = path
            blocks.append(block)
    return tuple(blocks)


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
