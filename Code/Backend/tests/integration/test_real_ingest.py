"""Deeper checks against the real corpus: the full 100-call leak test, and
an end-to-end ingest — the two things plan §8 Phase 2 explicitly asks be
checked against every call in the corpus, not just fixtures.

Skipped when the corpus isn't present (git-ignored, decision D8) — runs
locally, where the corpus actually is.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine

from application.use_cases.ingest_transcripts import IngestTranscripts
from infrastructure.config.paths import DEFAULT_TRANSCRIPTS_PATH, DEFAULT_WORKBOOK_PATH
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

pytestmark = pytest.mark.skipif(
    not (DEFAULT_WORKBOOK_PATH.exists() and DEFAULT_TRANSCRIPTS_PATH.exists()),
    reason="data/source/ corpus not present locally (git-ignored, decision D8)",
)


def test_no_answer_key_text_survives_stripping_across_all_100_calls() -> None:
    records = PdfCorpusSource(DEFAULT_TRANSCRIPTS_PATH).read()

    assert len(records) == 100
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
            source=PdfCorpusSource(DEFAULT_TRANSCRIPTS_PATH),
            lookup=SqlReferenceLookup(session_factory),
            repository=SqlCallRepository(session_factory, SystemClock()),
        )
        counts = await use_case.execute()

        assert counts.total == 100
        assert counts.speaker_unresolved == 0
        assert counts.agent_unknown == 0
        assert counts.resolved + counts.caller_unresolved == 100
        # This is the number to actually look at: every unresolved caller,
        # with why. See the CLI/check-in output for the human-readable form.
    finally:
        await engine.dispose()
