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
    assert record.turns is not None
    rendered = "\n".join(turn.text for turn in record.turns)

    assert "CALL TAGS" not in rendered, f"leaked 'CALL TAGS' into {record.reference}"
    assert not _SCORE.search(rendered), f"leaked a score into {record.reference}"
    assert not _RULE_CITATION.search(rendered), f"leaked a rule citation into {record.reference}"
    for word in _OUTCOME_WORDS:
        assert word not in rendered, f"leaked outcome {word!r} into {record.reference}"
    for archetype in _ARCHETYPES:
        assert archetype not in rendered, f"leaked archetype {archetype!r} into {record.reference}"
