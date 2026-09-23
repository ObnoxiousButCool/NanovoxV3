"""The answer-key CLI: its exit codes and its operator-facing report.

The exit code carries a decision, so it is worth pinning down. A failed
import and an unreconciled one are different conditions and get different
codes — a caller that runs this in a pipeline needs to tell "could not read
the workbook" from "the workbook and the PDF disagree", because only the
second one means the corpus pair is wrong.

The end-to-end case runs against the real corpus, which is tracked under
`Documents/`, through the same three commands an operator runs in order.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from application.ports.ground_truth_repository import GroundTruthCounts
from application.use_cases.import_answer_key import AnswerKeyImportResult, Disagreement
from frameworks_drivers.cli.import_answer_key import (
    EXIT_NOT_RECONCILED,
    EXIT_OK,
    _report,
    main,
)
from infrastructure.config.paths import DEFAULT_TRANSCRIPTS_PATH, DEFAULT_WORKBOOK_PATH
from infrastructure.config.settings import get_settings
from infrastructure.persistence.models import Base


@pytest.fixture(autouse=True)
def _isolated_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _result(
    *,
    written: int = 100,
    unmatched: tuple[str, ...] = (),
    warnings: tuple[str, ...] = (),
    disagreements: tuple[Disagreement, ...] = (),
    missing_from_tracker: tuple[str, ...] = (),
    missing_from_pdf: tuple[str, ...] = (),
) -> AnswerKeyImportResult:
    return AnswerKeyImportResult(
        counts=GroundTruthCounts(written=written, unmatched=unmatched),
        warnings=warnings,
        disagreements=disagreements,
        missing_from_tracker=missing_from_tracker,
        missing_from_pdf=missing_from_pdf,
    )


def test_a_clean_import_reports_reconciled(capsys: pytest.CaptureFixture[str]) -> None:
    _report(_result())

    output = capsys.readouterr().out
    assert "Imported 100 answer-key rows." in output
    assert "Reconciled" in output
    assert "NOT RECONCILED" not in output


def test_a_disagreement_is_printed_in_full_and_names_both_sources(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _report(
        _result(
            disagreements=(Disagreement(reference="C-0001", field="score", tracker="44", pdf="91"),)
        )
    )

    output = capsys.readouterr().out
    assert "1 disagreement(s)" in output
    assert "C-0001: score — tracker says '44', PDF says '91'" in output
    assert "NOT RECONCILED" in output
    assert "different revisions" in output


def test_unmatched_rows_say_what_to_run_first(capsys: pytest.CaptureFixture[str]) -> None:
    _report(_result(written=99, unmatched=("C-0100",)))

    output = capsys.readouterr().out
    assert "1 tracker row(s) name a call that has not been ingested" in output
    assert "ingest_transcripts" in output


def test_calls_present_in_only_one_source_are_named(
    capsys: pytest.CaptureFixture[str],
) -> None:
    _report(_result(missing_from_tracker=("C-0101",), missing_from_pdf=("C-0102",)))

    output = capsys.readouterr().out
    assert "in the PDF but not the tracker: C-0101" in output
    assert "in the tracker but not the PDF: C-0102" in output


def test_source_warnings_are_printed(capsys: pytest.CaptureFixture[str]) -> None:
    _report(_result(warnings=("C-0007: Signals value 'oops' is not ...",)))

    assert "warning: C-0007" in capsys.readouterr().out


def test_a_long_disagreement_list_is_truncated_with_a_count(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An operator needs the shape of the problem, not 500 lines of it."""
    many = tuple(
        Disagreement(reference=f"C-{i:04d}", field="score", tracker="1", pdf="2")
        for i in range(1, 26)
    )
    _report(_result(disagreements=many))

    output = capsys.readouterr().out
    assert "25 disagreement(s)" in output
    assert "... and 5 more" in output


@pytest.mark.skipif(
    not (DEFAULT_WORKBOOK_PATH.exists() and DEFAULT_TRANSCRIPTS_PATH.exists()),
    reason="corpus not found — expected it under Documents/ (see infrastructure/config/paths.py)",
)
def test_the_real_corpus_imports_and_reconciles_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Reference data, then ingestion, then the answer key — the order an
    operator runs them in, and the order `ground_truth`'s foreign key
    requires.
    """
    from frameworks_drivers.cli.import_reference import main as import_reference
    from frameworks_drivers.cli.ingest_transcripts import main as ingest

    db_path = tmp_path / "answer_key_cli.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("WORKBOOK_PATH", str(DEFAULT_WORKBOOK_PATH))
    monkeypatch.setenv("TRANSCRIPTS_PATH", str(DEFAULT_TRANSCRIPTS_PATH))
    monkeypatch.setenv("LOG_ENABLED", "false")
    monkeypatch.setenv("FRONTEND_DIST_PATH", str(tmp_path / "no-frontend"))

    from sqlalchemy import create_engine

    from infrastructure.persistence import tables as _tables  # noqa: F401

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()

    assert import_reference() == 0
    assert ingest() == 0
    capsys.readouterr()

    assert main() == EXIT_OK

    output = capsys.readouterr().out
    assert "Imported 100 answer-key rows." in output
    assert "Reconciled: the tracker and the PDF agree on every shared field." in output
    assert "warning:" not in output
    assert "unmatched" not in output


def test_the_two_failure_modes_have_different_exit_codes() -> None:
    """Not a tautology: these two constants are the CLI's contract with
    whatever runs it, and collapsing them would hide the corpus-pair
    problem behind a generic failure.
    """
    assert EXIT_OK != EXIT_NOT_RECONCILED
    assert _result().reconciled is True
    assert _result(missing_from_pdf=("C-0001",)).reconciled is False
