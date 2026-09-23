"""`AnswerKeySource` adapter reading the v9 corpus PDF's answer sheet.

Reads exactly the fields `PdfCorpusSource` never touches: category,
archetype, cited rules, outcome, score, and the `CALL TAGS` block. Used
only by the evaluation harness (Phase 5); no extraction code may import
this module — enforced by the import-linter contract "Extraction cannot
read the answer key" in `pyproject.toml`.
"""

from __future__ import annotations

import re
from pathlib import Path

from application.ports.answer_key_source import AnswerKeySource
from domain.entities.answer_key import AnswerKey
from infrastructure.corpus.pdf_text import call_reference, extract_call_blocks, split_call_block

# Header line 1 reads e.g. "C-0001 — Claims & EOB"; captures the category.
_LINE_1 = re.compile(r"^C-\d{4} — (?P<category>.+)$")
# Header line 2 reads e.g. "Mon 06 Jul 2026 09:14 · AHT 6m 20s · Competent
# and resolved · rules C-12, P-14"; captures the archetype and cited rules.
# Anchored on "AHT ...s ·" so a bare `.search` doesn't span backwards across
# the date/time's own "·" separator and swallow "AHT 6m 20s" into the
# archetype group.
_LINE_2 = re.compile(r"AHT \d+m \d+s · (?P<archetype>.+?) · rules (?P<rules>.+)$")
# Header line 3 reads e.g. "MEMBER · CB-7700205 | RESOLVED | score 91/100 |
# agent AGT-01|Sarah Whitlock"; captures the outcome and score.
_LINE_3 = re.compile(r"\| (?P<outcome>[A-Z ]+) \| score (?P<score>\d+)/100 \|")

_NO_RULES = "—"


def _parse_rule_refs(raw: str) -> tuple[str, ...]:
    if raw.strip() == _NO_RULES:
        return ()
    return tuple(ref.strip() for ref in raw.split(",") if ref.strip())


class PdfAnswerKeySource(AnswerKeySource):
    def __init__(self, path: Path) -> None:
        self._path = path

    def read(self) -> tuple[AnswerKey, ...]:
        keys = []
        for block in extract_call_blocks(self._path):
            reference = call_reference(block)
            (line1, line2, line3), _dialogue_text, call_tags_text = split_call_block(block)
            keys.append(self._parse_call(reference, line1, line2, line3, call_tags_text))
        return tuple(keys)

    def _parse_call(
        self, reference: str, line1: str, line2: str, line3: str, call_tags_text: str
    ) -> AnswerKey:
        category_match = _LINE_1.match(line1)
        archetype_match = _LINE_2.search(line2)
        outcome_match = _LINE_3.search(line3)

        return AnswerKey(
            reference=reference,
            category=category_match.group("category").strip() if category_match else "",
            archetype=archetype_match.group("archetype").strip() if archetype_match else "",
            rule_refs=(_parse_rule_refs(archetype_match.group("rules")) if archetype_match else ()),
            outcome=outcome_match.group("outcome").strip() if outcome_match else "",
            score=int(outcome_match.group("score")) if outcome_match else None,
            call_tags_text=call_tags_text.strip(),
        )
