"""`TranscriptSource` adapter reading the v9 corpus PDF.

Reads only the legitimate half of each call's header — call id, date/time,
talk time, caller type, caller reference, agent id and name — and the
dialogue. Never touches category, archetype, cited rules, outcome, score or
the `CALL TAGS` block: the regexes below simply have no capture group for
them, so there is no code path here that ever holds that text in a
variable, let alone returns it. That's `PdfAnswerKeySource`'s job, and nothing
here imports it — the import-linter contract "Extraction cannot read the
answer key" in `pyproject.toml` forbids it structurally.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from application.ports.transcript_source import RawCallRecord, TranscriptSource
from domain.speaker_resolution import RawTurn, resolve_speaker_roles
from domain.value_objects.call_source import CallSource
from domain.value_objects.caller_type import CallerType
from infrastructure.corpus.pdf_text import call_reference, extract_call_blocks, split_call_block

# Header line 2 reads e.g. "Mon 06 Jul 2026 09:14 · AHT 6m 20s · Competent and
# resolved · rules C-12, P-14" — this captures only the date/time and talk
# time; the archetype and rules after the third separator are never
# captured into a group, so they're never held in a variable here.
_LINE_2 = re.compile(r"^(?P<when>.+?) · AHT (?P<minutes>\d+)m (?P<seconds>\d+)s ·")
_WHEN_FORMAT = "%a %d %b %Y %H:%M"

# Header line 3 reads e.g. "MEMBER · CB-7700205 | RESOLVED | score 91/100 |
# agent AGT-01|Sarah Whitlock" — captures caller type/ref and agent id/name
# only; the outcome and score between the pipes match `.*` and are discarded.
_LINE_3 = re.compile(
    r"^(?P<caller_type>MEMBER|EMPLOYER) · (?P<caller_ref>\S+) \|.*\| "
    r"agent (?P<agent_ref>AGT-\d+)\|(?P<agent_name>.+)$"
)

# A dialogue line reads e.g. "Sarah: Choice Administrators..." or " Leon:
# Leon Castellano..." — a leading space is PDF layout, not part of the label.
_SPEAKER_LINE = re.compile(r"^\s*([A-Z][A-Za-z'\-]{1,20}):\s?(.*)$")


def _parse_when(raw: str) -> datetime | None:
    """The corpus states no timezone; treated as UTC for a consistently
    aware datetime, matching this codebase's convention, not a claim about
    the real-world zone a call happened in.
    """
    try:
        return datetime.strptime(raw, _WHEN_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_raw_turns(dialogue_text: str) -> tuple[RawTurn, ...]:
    """Split dialogue into (label, text) pairs, folding continuation lines
    (no label of their own) into the preceding turn.
    """
    turns: list[RawTurn] = []
    label: str | None = None
    text_parts: list[str] = []

    def flush() -> None:
        if label is not None:
            turns.append(RawTurn(label=label, text=" ".join(text_parts).strip()))

    for line in dialogue_text.split("\n"):
        match = _SPEAKER_LINE.match(line)
        if match:
            flush()
            label = match.group(1)
            text_parts = [match.group(2)]
        elif line.strip():
            text_parts.append(line.strip())
    flush()

    return tuple(turns)


class PdfCorpusSource(TranscriptSource):
    def __init__(self, path: Path) -> None:
        self._path = path

    def read(self) -> tuple[RawCallRecord, ...]:
        records = []
        for block in extract_call_blocks(self._path):
            reference = call_reference(block)
            (_line1, line2, line3), dialogue_text, _call_tags_text = split_call_block(block)
            records.append(self._parse_call(reference, line2, line3, dialogue_text))
        return tuple(records)

    def _parse_call(
        self, reference: str, line2: str, line3: str, dialogue_text: str
    ) -> RawCallRecord:
        when_match = _LINE_2.match(line2)
        occurred_at = _parse_when(when_match.group("when")) if when_match else None
        aht_seconds = (
            int(when_match.group("minutes")) * 60 + int(when_match.group("seconds"))
            if when_match
            else None
        )

        header_match = _LINE_3.match(line3)
        if header_match is None:
            return RawCallRecord(
                reference=reference,
                source=CallSource.CORPUS_PDF,
                occurred_at=occurred_at,
                aht_seconds=aht_seconds,
                caller_type=CallerType.MEMBER,
                caller_ref="",
                agent_ref="",
                agent_name="",
                turns=None,
                unresolved_reason=f"header line 3 did not match the expected format: {line3!r}",
            )

        caller_type = CallerType(header_match.group("caller_type"))
        caller_ref = header_match.group("caller_ref")
        agent_ref = header_match.group("agent_ref")
        agent_name = header_match.group("agent_name").strip()

        raw_turns = _parse_raw_turns(dialogue_text)
        resolution = resolve_speaker_roles(agent_name.split()[0], raw_turns)

        return RawCallRecord(
            reference=reference,
            source=CallSource.CORPUS_PDF,
            occurred_at=occurred_at,
            aht_seconds=aht_seconds,
            caller_type=caller_type,
            caller_ref=caller_ref,
            agent_ref=agent_ref,
            agent_name=agent_name,
            turns=resolution.turns,
            unresolved_reason=resolution.unresolved_reason,
        )
