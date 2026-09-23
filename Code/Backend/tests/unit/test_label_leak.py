"""The leak test: nothing the answer key knows survives into a Transcript.

Runs in the gates (plan §6.3) against committed fixtures, so it's exercised
in CI without the real 100-call PDF (git-ignored). A second, deeper version
runs the same check against every call in the real corpus when it's
present — see `tests/integration/test_real_ingest.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import infrastructure.corpus.pdf_corpus_source as pdf_corpus_source
from infrastructure.corpus.pdf_corpus_source import PdfCorpusSource
from tests.fixtures.transcript_snippets import (
    C0001_RAW_BLOCK,
    C0999_RAW_BLOCK_WITH_BLANK_HEADER_LINE,
)
from tests.support.leak_check import assert_no_answer_key_leak


@pytest.mark.parametrize(
    "block", [C0001_RAW_BLOCK, C0999_RAW_BLOCK_WITH_BLANK_HEADER_LINE], ids=["C-0001", "C-0999"]
)
def test_no_answer_key_text_survives_stripping(monkeypatch: pytest.MonkeyPatch, block: str) -> None:
    monkeypatch.setattr(pdf_corpus_source, "extract_call_blocks", lambda _path: (block,))
    (record,) = PdfCorpusSource(Path("unused")).read()

    assert_no_answer_key_leak(record)
