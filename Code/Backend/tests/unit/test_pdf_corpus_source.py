"""`PdfCorpusSource` — the legitimate half of each call, and nothing else.

`extract_call_blocks` is monkeypatched to return fixture blocks directly,
so these tests need no real PDF file on disk.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import infrastructure.corpus.pdf_corpus_source as pdf_corpus_source
from domain.value_objects.call_source import CallSource
from domain.value_objects.caller_type import CallerType
from domain.value_objects.speaker_role import SpeakerRole
from infrastructure.corpus.pdf_corpus_source import PdfCorpusSource
from tests.fixtures.transcript_snippets import C0001_RAW_BLOCK


def _source_with_blocks(monkeypatch: pytest.MonkeyPatch, *blocks: str) -> PdfCorpusSource:
    monkeypatch.setattr(pdf_corpus_source, "extract_call_blocks", lambda _path: blocks)
    return PdfCorpusSource(Path("unused"))


def test_reads_every_legitimate_field_from_c0001(monkeypatch: pytest.MonkeyPatch) -> None:
    (record,) = _source_with_blocks(monkeypatch, C0001_RAW_BLOCK).read()

    assert record.reference == "C-0001"
    assert record.source is CallSource.CORPUS_PDF
    assert record.occurred_at is not None
    assert record.occurred_at.year == 2026
    assert record.occurred_at.month == 7
    assert record.occurred_at.day == 6
    assert record.aht_seconds == 380  # "6m 20s"
    assert record.caller_type is CallerType.MEMBER
    assert record.caller_ref == "CB-7700205"
    assert record.agent_ref == "AGT-01"
    assert record.agent_name == "Sarah Whitlock"


def test_resolves_c0001s_turns_with_leon_as_the_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    (record,) = _source_with_blocks(monkeypatch, C0001_RAW_BLOCK).read()

    assert record.unresolved_reason is None
    assert record.turns is not None
    assert record.turns[0].role is SpeakerRole.AGENT
    assert "Choice Administrators" in record.turns[0].text
    assert record.turns[1].role is SpeakerRole.CALLER
    assert record.turns[1].text == "Leon Castellano. CB-7700205."


def test_multiline_turns_are_joined_into_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sarah's opening turn spans two PDF lines ("...your name and" /
    "member ID?") with no label on the continuation line.
    """
    (record,) = _source_with_blocks(monkeypatch, C0001_RAW_BLOCK).read()

    assert record.turns is not None
    assert record.turns[0].text == (
        "Choice Administrators, Sarah speaking. This call may be recorded for quality "
        "and training. Can I take your name and member ID?"
    )


def test_never_captures_answer_key_text_into_any_field(monkeypatch: pytest.MonkeyPatch) -> None:
    """The record has no field that could hold category/archetype/rules/
    outcome/score even if the regex matched more than intended — this
    asserts on the actual dataclass fields available, not just their values.
    """
    (record,) = _source_with_blocks(monkeypatch, C0001_RAW_BLOCK).read()

    field_names = set(record.__dataclass_fields__)
    assert field_names == {
        "reference",
        "source",
        "occurred_at",
        "aht_seconds",
        "caller_type",
        "caller_ref",
        "agent_ref",
        "agent_name",
        "turns",
        "unresolved_reason",
    }


def test_unresolvable_header_is_reported_not_guessed(monkeypatch: pytest.MonkeyPatch) -> None:
    malformed = (
        "C-0002 — Something\n"
        "Mon 06 Jul 2026 09:14 · AHT 1m 00s · X · rules —\n"
        "not a valid header line\n"
        "Sarah: hi\n"
        " Leon: hi"
    )

    (record,) = _source_with_blocks(monkeypatch, malformed).read()

    assert record.turns is None
    assert record.unresolved_reason is not None
    assert "header line 3" in record.unresolved_reason
