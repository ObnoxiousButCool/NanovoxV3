"""Structural PDF text splitting — no interpretation of what the lines mean."""

from __future__ import annotations

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


def test_page_furniture_is_removed_wherever_it_falls() -> None:
    furniture = "NanoVox — Corpus v9 · transcripts batch 1\n5\n"
    text = C0001_RAW_BLOCK[:200] + furniture + C0001_RAW_BLOCK[200:]

    (block,) = split_into_call_blocks(text)

    assert "NanoVox" not in block


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
