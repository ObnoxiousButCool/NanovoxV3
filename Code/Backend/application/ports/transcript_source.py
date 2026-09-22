"""Port for reading clean transcripts — extraction's only way to reach a call.

No implementation of this port may expose anything from the answer key
(category, archetype, rule references, outcome, score, the `CALL TAGS`
block) — that's `AnswerKeySource`, a separate port. This one and
`PdfCorpusSource`, the adapter behind it, are named in the import-linter
contract "Extraction cannot read the answer key" in `pyproject.toml`, which
forbids them from importing it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from domain.entities.turn import Turn
from domain.value_objects.call_source import CallSource
from domain.value_objects.caller_type import CallerType


@dataclass(frozen=True)
class RawCallRecord:
    """One call's header, always parsed, plus its turns if speaker roles
    resolved.

    `turns` is `None` exactly when they didn't — the header (call
    reference, timing, caller type/ref, agent ref/name) is legitimate input
    independent of dialogue (plan §6.3) and always available; only the
    dialogue can fail to resolve.
    """

    reference: str
    source: CallSource
    occurred_at: datetime | None
    aht_seconds: int | None
    caller_type: CallerType
    caller_ref: str
    agent_ref: str
    agent_name: str
    turns: tuple[Turn, ...] | None
    unresolved_reason: str | None


class TranscriptSource(ABC):
    """Reads every call as a `RawCallRecord` — never as anything carrying
    answer-key data.
    """

    @abstractmethod
    def read(self) -> tuple[RawCallRecord, ...]:
        """Parse every call. Synchronous — see `ReferenceSource.read` for why."""
