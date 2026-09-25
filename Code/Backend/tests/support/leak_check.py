"""Shared assertion for the label-leak tests (fixture-based and real-corpus).

Checks are pattern-based where a bare substring would false-positive on
ordinary English — real dialogue in the corpus says things like "I'll send
you the product rules in writing" (call C-0064), which contains "rules "
without leaking anything. The rule-citation and score checks match the
header's actual format instead of the bare word.
"""

from __future__ import annotations

import re

from application.ports.transcript_source import RawCallRecord

_RULE_CITATION = re.compile(r"rules (—|[A-Z]-\d+(,\s*[A-Z]-\d+)*)")
_SCORE = re.compile(r"score \d+/100")
_OUTCOME_WORDS = ("RESOLVED", "UNRESOLVED", "PARTIALLY RESOLVED", "ESCALATED")
_ARCHETYPES = (
    "Competent and resolved",
    "Competent but constrained",
    "Brush-off",
    "Circular",
)


def assert_no_answer_key_leak(record: RawCallRecord) -> None:
    """The ingest-time check: what was parsed out of the corpus PDF."""
    assert record.turns is not None
    assert_text_carries_no_answer_key(
        "\n".join(turn.text for turn in record.turns), record.reference
    )


def assert_text_carries_no_answer_key(rendered: str, where: str) -> None:
    """The same assertion, over any text on its way to a reader.

    Split out for the evidence endpoint. Ingestion being correct is
    necessary and not sufficient: the stored turns are what
    `GET /insights/calls/{reference}` returns, and a stripping bug, a
    re-ingest from another source, or a fixture loaded straight into the
    database would each pass an ingestion-only check and still put the
    answer key on a screen. `plan.md` §6.3 calls this "the single most
    important safety property", so it is asserted where the text leaves
    the application, not only where it enters.
    """
    assert "CALL TAGS" not in rendered, f"leaked 'CALL TAGS' into {where}"
    assert not _SCORE.search(rendered), f"leaked a score into {where}"
    assert not _RULE_CITATION.search(rendered), f"leaked a rule citation into {where}"
    for word in _OUTCOME_WORDS:
        assert word not in rendered, f"leaked outcome {word!r} into {where}"
    for archetype in _ARCHETYPES:
        assert archetype not in rendered, f"leaked archetype {archetype!r} into {where}"
