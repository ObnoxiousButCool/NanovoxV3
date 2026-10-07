"""Deeper checks against the real corpus: the full-corpus leak test, and
an end-to-end ingest — the two things plan §8 Phase 2 explicitly asks be
checked against every call in the corpus, not just fixtures.

The corpus is tracked under Documents/, so these run on any checkout. The
skip guard stays for a deployment that points WORKBOOK_PATH and
TRANSCRIPTS_DIR somewhere the files are genuinely absent — but it should no
longer fire here, and a skip is now a signal that something is wrong rather
than the normal state.

The corpus arrives in batches short of a 600-call target
(Documents/notes/Corpus-v10-Schema-Update.md), so nothing here hardcodes a call count —
only a floor, so a corpus that silently lost calls (a batch file removed, a
glob that stopped matching) still fails loudly rather than passing quietly
on fewer calls than last time.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

from application.use_cases.ingest_transcripts import IngestTranscripts
from infrastructure.config.paths import DEFAULT_TRANSCRIPTS_DIR, DEFAULT_WORKBOOK_PATH
from infrastructure.corpus.pdf_corpus_source import PdfCorpusSource
from infrastructure.persistence import tables as _tables  # noqa: F401
from infrastructure.persistence.engine import create_session_factory
from infrastructure.persistence.models import Base
from infrastructure.persistence.repositories.call_repository import SqlCallRepository
from infrastructure.persistence.repositories.reference_lookup import SqlReferenceLookup
from infrastructure.persistence.repositories.reference_repository import SqlReferenceRepository
from infrastructure.reference.xlsx_reference_source import XlsxReferenceSource
from infrastructure.system_clock import SystemClock
from tests.support.leak_check import assert_no_answer_key_leak

# Batch 1 alone was 100 calls; the corpus only grows toward its 600-call
# target from here, so this is a floor, never an exact count.
_MINIMUM_CALLS = 100

pytestmark = pytest.mark.skipif(
    not (DEFAULT_WORKBOOK_PATH.exists() and DEFAULT_TRANSCRIPTS_DIR.exists()),
    reason="corpus not found — expected it under Documents/ (see infrastructure/config/paths.py)",
)


def test_no_answer_key_text_survives_stripping_across_the_whole_corpus() -> None:
    records = PdfCorpusSource(DEFAULT_TRANSCRIPTS_DIR).read()

    assert len(records) >= _MINIMUM_CALLS
    for record in records:
        if record.turns is None:
            continue  # nothing rendered; speaker-unresolved calls carry no leak risk
        assert_no_answer_key_leak(record)


async def test_ingests_the_real_corpus_end_to_end(tmp_path: Path) -> None:
    db_path = tmp_path / "real_ingest.db"
    database_url = f"sqlite+aiosqlite:///{db_path.as_posix()}"

    sync_engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    try:
        Base.metadata.create_all(sync_engine)
    finally:
        sync_engine.dispose()

    engine = create_async_engine(database_url)
    try:
        session_factory = create_session_factory(engine)

        reference_result = await SqlReferenceRepository(session_factory).upsert(
            XlsxReferenceSource(DEFAULT_WORKBOOK_PATH).read()
        )
        assert reference_result.employers == 95
        assert reference_result.agents == 20

        use_case = IngestTranscripts(
            source=PdfCorpusSource(DEFAULT_TRANSCRIPTS_DIR),
            lookup=SqlReferenceLookup(session_factory),
            repository=SqlCallRepository(session_factory, SystemClock()),
        )
        counts = await use_case.execute()

        assert counts.total >= _MINIMUM_CALLS
        assert counts.speaker_unresolved == 0
        assert counts.agent_unknown == 0
        assert counts.resolved + counts.caller_unresolved == counts.total
        # This is the number to actually look at: every unresolved caller,
        # with why. See the CLI/check-in output for the human-readable form.
    finally:
        await engine.dispose()
