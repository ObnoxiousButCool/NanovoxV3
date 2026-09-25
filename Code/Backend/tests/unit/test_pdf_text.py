"""Structural PDF text splitting — no interpretation of what the lines mean."""

from __future__ import annotations

import pytest

from infrastructure.corpus.pdf_text import call_reference, split_call_block, split_into_call_blocks
from tests.fixtures.transcript_snippets import (
    C0001_RAW_BLOCK,
    C0999_RAW_BLOCK_WITH_BLANK_HEADER_LINE,
)


def test_call_reference_reads_the_leading_call_id() -> None:
    assert call_reference(C0001_RAW_BLOCK) == "C-0001"


def test_splits_two_calls_at_the_header_boundary() -> None:
    text = C0001_RAW_BLOCK + "\n" + C0999_RAW_BLOCK_WITH_BLANK_HEADER_LINE
    blocks = split_into_call_blocks(text)

    assert len(blocks) == 2
    assert call_reference(blocks[0]) == "C-0001"
    assert call_reference(blocks[1]) == "C-0999"


def _at_a_page_break(furniture: str) -> str:
    """`furniture` spliced in as its own line, between two existing lines of
    `C0001_RAW_BLOCK`.

    A page break in a real PDF never lands mid-word — `pypdf.extract_text()`
    always ends a visual line with a newline, so a footer is always a line
    of its own, never a substring of one. Splitting at an arbitrary
    character offset (as this test once did) can land mid-word, which no
    real extraction produces and which a line-anchored pattern correctly
    does not have to handle.
    """
    lines = C0001_RAW_BLOCK.split("\n")
    middle = len(lines) // 2
    return "\n".join([*lines[:middle], *furniture.splitlines(), *lines[middle:]])


def test_page_furniture_is_removed_wherever_it_falls() -> None:
    text = _at_a_page_break("NanoVox — Corpus v9 · transcripts batch 1\n5")

    (block,) = split_into_call_blocks(text)

    assert "NanoVox" not in block


@pytest.mark.parametrize(
    "furniture",
    [
        # batch 1, first issue — the original footer this pattern was
        # hardcoded to.
        "NanoVox — Corpus v9 · transcripts batch 1\n5",
        # batch 1 rev-2 — a revision suffix the hardcoded version missed
        # entirely, leaking furniture into 134 of ~1,700 turns.
        "NanoVox — Corpus v9 · transcripts batch 1 rev-2\n5",
        # batch 1 rev-2 again, but with the page number glued onto the same
        # line rather than a separate one — most pages in that PDF render
        # this way.
        "NanoVox — Corpus v9 · transcripts batch 1 rev-2 5",
        # batch 2a — a different batch label, no revision suffix.
        "NanoVox — Corpus v9 · transcripts batch 2a\n5",
        # batch 3 — a different footer shape again: no "transcripts", and a
        # parenthetical call range instead of a bare batch number.
        "NanoVox — Corpus v9 · batch 3 (C-0151 to C-0200 of 600)\n5",
    ],
    ids=["batch1", "batch1_rev2", "batch1_rev2_glued", "batch2a", "batch3"],
)
def test_page_furniture_is_removed_regardless_of_batch_label(furniture: str) -> None:
    """Every batch's PDF has printed a different footer. A version of this
    pattern hardcoded to one of them is exactly the bug that shipped once
    already — see this module's own history."""
    text = _at_a_page_break(furniture)

    (block,) = split_into_call_blocks(text)

    assert "NanoVox" not in block
    assert "\n5\n" not in block


def test_split_call_block_separates_header_dialogue_and_call_tags() -> None:
    header, dialogue, call_tags = split_call_block(C0001_RAW_BLOCK)

    assert header[0] == "C-0001 — Claims & EOB"
    assert header[1].startswith("Mon 06 Jul 2026 09:14")
    assert header[2].startswith("MEMBER · CB-7700205")
    assert "Sarah:" in dialogue
    assert "CALL TAGS" not in dialogue
    assert call_tags.startswith("CALL TAGS")
    assert "caller_ref   CB-7700205" in call_tags


def test_split_call_block_skips_a_blank_line_inside_the_header() -> None:
    """Calls C-0033/C-0046/C-0064 in batch 1 have this shape: a stray blank
    line between the title and the second header line.
    """
    header, dialogue, _call_tags = split_call_block(C0999_RAW_BLOCK_WITH_BLANK_HEADER_LINE)

    assert header[0] == "C-0999 — Provider Network"
    assert header[1].startswith("Mon 27 Jul 2026 11:25")
    assert header[2].startswith("EMPLOYER · CON-118")
    assert "Linda:" in dialogue
