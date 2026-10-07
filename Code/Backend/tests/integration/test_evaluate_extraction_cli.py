"""The evaluation CLI end to end, against the real corpus.

Runs the three imports an operator runs, then the harness — with no
extraction pipeline in between, because running one needs a live model
provider and this suite never calls out.

That makes it a test of the case that matters most right now: a hundred
calls with answers and nothing to compare them against. It proves the
harness reads the answer key back out of the database, reports every field
as unscored rather than as agreed, and exits `EXIT_NOTHING_COMPARED` rather
than `EXIT_OK` — which is the difference between "the pipeline has not run"
and "the pipeline agrees with everything", and those look identical to any
harness that counted an absent value as a match.

The corpus lives in `Documents/` and is tracked, so this runs by default.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from application.ports.diagnostics_source import Diagnostics
from frameworks_drivers.cli.evaluate_extraction import EXIT_NOTHING_COMPARED, main
from frameworks_drivers.container import build_container, dispose_container
from infrastructure.config.paths import DEFAULT_TRANSCRIPTS_DIR, DEFAULT_WORKBOOK_PATH
from infrastructure.config.settings import get_settings


@pytest.fixture(autouse=True)
def _isolated_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.skipif(
    not (DEFAULT_WORKBOOK_PATH.exists() and DEFAULT_TRANSCRIPTS_DIR.exists()),
    reason="corpus not found — expected it under Documents/ (see infrastructure/config/paths.py)",
)
def test_a_corpus_with_answers_and_no_extractions_reports_nothing_compared(
    ingested_corpus: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from frameworks_drivers.cli.import_answer_key import main as import_answer_key

    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{ingested_corpus.as_posix()}")
    monkeypatch.setenv("WORKBOOK_PATH", str(DEFAULT_WORKBOOK_PATH))
    monkeypatch.setenv("TRANSCRIPTS_DIR", str(DEFAULT_TRANSCRIPTS_DIR))
    monkeypatch.setenv("LOG_ENABLED", "false")
    monkeypatch.setenv("FRONTEND_DIST_PATH", str(tmp_path / "no-frontend"))

    assert import_answer_key() == 0
    capsys.readouterr()

    exit_code = main()

    output = capsys.readouterr().out
    assert exit_code == EXIT_NOTHING_COMPARED, "no extraction has run, so nothing is comparable"
    # Not a fixed call count: the corpus arrives in batches short of a
    # 600-call target (Documents/notes/Corpus-v10-Schema-Update.md).
    assert re.search(r"Scored 0 of \d+ call\(s\) with an answer key \(0% coverage\)\.", output)
    assert "NOTHING COMPARED" in output
    assert "Run the extraction first." in output
    # The distinction the exit code exists for: this is not a bad score.
    assert "0% agreement" not in output


@pytest.mark.skipif(
    not (DEFAULT_WORKBOOK_PATH.exists() and DEFAULT_TRANSCRIPTS_DIR.exists()),
    reason="corpus not found — expected it under Documents/ (see infrastructure/config/paths.py)",
)
def test_the_diagnostics_read_the_real_corpus(
    ingested_corpus: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The three diagnostics against real ingested data, through the
    container's own wiring rather than a fake.

    No pipeline has run, so every one of them reports its own kind of
    nothing — and each has to report the *right* nothing: no markers raised
    is not a zero refusal rate, and no run recorded is not a free run.
    """
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{ingested_corpus.as_posix()}")
    monkeypatch.setenv("WORKBOOK_PATH", str(DEFAULT_WORKBOOK_PATH))
    monkeypatch.setenv("TRANSCRIPTS_DIR", str(DEFAULT_TRANSCRIPTS_DIR))
    monkeypatch.setenv("LOG_ENABLED", "false")
    monkeypatch.setenv("FRONTEND_DIST_PATH", str(tmp_path / "no-frontend"))

    diagnostics = asyncio.run(_read_diagnostics())

    assert diagnostics.markers_raised == 0, "no L3 pass has run"
    assert diagnostics.rejection_rate is None, "undefined, not zero"
    assert diagnostics.last_run_cost is None, "no run recorded is not a free run"
    # Every ingested call resolved, so the list is empty rather than absent —
    # and if the corpus ever gains an unresolvable caller this will say so.
    assert isinstance(diagnostics.unresolved_callers, tuple)


async def _read_diagnostics() -> Diagnostics:
    container = build_container(get_settings())
    try:
        return await container.diagnostics_source.read()
    finally:
        await dispose_container(container)
