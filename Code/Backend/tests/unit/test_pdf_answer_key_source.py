"""`PdfAnswerKeySource` — exactly the fields `PdfCorpusSource` never touches."""

from __future__ import annotations

from pathlib import Path

import pytest

import infrastructure.corpus.pdf_answer_key_source as pdf_answer_key_source
from infrastructure.corpus.pdf_answer_key_source import PdfAnswerKeySource
from tests.fixtures.transcript_snippets import C0001_RAW_BLOCK


def _source_with_blocks(monkeypatch: pytest.MonkeyPatch, *blocks: str) -> PdfAnswerKeySource:
    monkeypatch.setattr(pdf_answer_key_source, "extract_call_blocks", lambda _path: blocks)
    return PdfAnswerKeySource(Path("unused"))


def test_reads_c0001s_answer_key(monkeypatch: pytest.MonkeyPatch) -> None:
    (key,) = _source_with_blocks(monkeypatch, C0001_RAW_BLOCK).read()

    assert key.reference == "C-0001"
    assert key.category == "Claims & EOB"
    assert key.archetype == "Competent and resolved"
    assert key.rule_refs == ("C-12", "P-14")
    assert key.outcome == "RESOLVED"
    assert key.score == 91
    assert key.call_tags_text.startswith("CALL TAGS")
    assert "caller_ref   CB-7700205" in key.call_tags_text


def test_no_rules_reads_as_an_empty_tuple(monkeypatch: pytest.MonkeyPatch) -> None:
    block = (
        "C-0999 — Provider Network\n"
        "Mon 27 Jul 2026 11:25 · AHT 2m 00s · Competent and resolved · rules —\n"
        "EMPLOYER · CON-118 | RESOLVED | score 90/100 | agent AGT-07|Linda Braithwaite\n"
        "Linda: Hi.\n"
        " Priya: Hi.\n"
        "CALL TAGS\n"
        " outcome   RESOLVED"
    )

    (key,) = _source_with_blocks(monkeypatch, block).read()

    assert key.rule_refs == ()
