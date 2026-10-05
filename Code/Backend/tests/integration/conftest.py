"""Fixtures shared by the integration tests that read the real corpus.

Three tests across two files each began by importing the reference sheets
and ingesting every transcript, which is the expensive part and produces
the same database every time. Ingesting once and copying the result keeps
each test's database its own -- they go on to import the answer key, or
not, and must not see each other's work -- while paying for the ingest
once instead of three times.

`test_real_ingest.py` deliberately does not use this: it is the test *of*
ingestion, so it has to run its own.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from infrastructure.config.paths import DEFAULT_TRANSCRIPTS_DIR, DEFAULT_WORKBOOK_PATH
from infrastructure.config.settings import get_settings
from infrastructure.persistence import tables as _tables  # noqa: F401
from infrastructure.persistence.models import Base


@pytest.fixture(scope="session")
def ingested_corpus_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """The real corpus, reference-imported and ingested, built once.

    Returns the database file to copy. Skips rather than fails when the
    corpus is absent, matching the guard the tests themselves carry: the
    files are tracked under `Documents/`, so a skip means a deployment has
    pointed the paths somewhere else rather than that anything is wrong.
    """
    if not (DEFAULT_WORKBOOK_PATH.exists() and DEFAULT_TRANSCRIPTS_DIR.exists()):
        pytest.skip("corpus not found — expected it under Documents/ (see config/paths.py)")

    from frameworks_drivers.cli.import_reference import main as import_reference
    from frameworks_drivers.cli.ingest_transcripts import main as ingest

    root = tmp_path_factory.mktemp("corpus")
    template = root / "ingested.db"
    engine = create_engine(f"sqlite:///{template.as_posix()}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()

    # `MonkeyPatch.context()` rather than the `monkeypatch` fixture, which
    # is function-scoped and cannot be requested from a session one. The
    # settings cache is cleared on both sides so neither this fixture nor
    # the test that follows reads the other's environment.
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{template.as_posix()}")
        patch.setenv("WORKBOOK_PATH", str(DEFAULT_WORKBOOK_PATH))
        patch.setenv("TRANSCRIPTS_DIR", str(DEFAULT_TRANSCRIPTS_DIR))
        patch.setenv("LOG_ENABLED", "false")
        patch.setenv("FRONTEND_DIST_PATH", str(root / "no-frontend"))
        get_settings.cache_clear()
        try:
            assert import_reference() == 0, "the reference sheets did not import"
            assert ingest() == 0, "the corpus did not ingest"
        finally:
            get_settings.cache_clear()

    return template


@pytest.fixture
def ingested_corpus(ingested_corpus_template: Path, tmp_path: Path) -> Path:
    """This test's own copy of the ingested corpus, and its database path."""
    database = tmp_path / "corpus.db"
    shutil.copyfile(ingested_corpus_template, database)
    return database
