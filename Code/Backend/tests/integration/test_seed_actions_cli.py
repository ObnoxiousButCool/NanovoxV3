"""The seeding CLI end to end, against a real (temporary) database.

Seeds from directly-inserted calls, extractions and signals rather than a
live model provider — same approach as `test_insights_demand_actions.py`'s
`seed_signals`, reused here. Two things worth proving against the real
stack rather than fakes: running the CLI twice produces the same board, not
a doubled one, and a seeded action's workflow fields really do read back
unset over the wire (`GET /insights/actions/board`), not merely in the
domain object.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from application.ports.session_issuer import Session
from domain.value_objects.signal_type import SignalType
from frameworks_drivers.api.dependencies import require_session
from frameworks_drivers.cli.seed_actions import EXIT_NOTHING_TO_SEED, EXIT_OK, main
from frameworks_drivers.main import create_app
from infrastructure.config.settings import get_settings
from infrastructure.persistence.engine import create_database_engine, create_session_factory
from infrastructure.persistence.models import Base
from tests.integration.test_insights_demand_actions import seed_signals

BOARD_URL = "/api/v1/insights/actions/board"


@pytest.fixture(autouse=True)
def _isolated_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _prepare_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str) -> Path:
    db_path = tmp_path / name
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("LOG_ENABLED", "false")
    monkeypatch.setenv("FRONTEND_DIST_PATH", str(tmp_path / "no-frontend"))

    from infrastructure.persistence import tables as _tables  # noqa: F401

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()
    return db_path


def test_an_empty_corpus_has_nothing_to_seed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _prepare_db(tmp_path, monkeypatch, "empty.db")

    exit_code = main()

    output = capsys.readouterr().out
    assert exit_code == EXIT_NOTHING_TO_SEED
    assert "NOTHING TO SEED" in output


def test_seeding_twice_produces_the_same_board_not_a_doubled_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _prepare_db(tmp_path, monkeypatch, "seed.db")
    settings = get_settings()
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)

    asyncio.run(
        seed_signals(
            session_factory,
            signals_per_call=[
                [SignalType.BILLING_DEFECT],
                [SignalType.BILLING_DEFECT],
                [SignalType.NETWORK_ADEQUACY],
            ],
        )
    )
    asyncio.run(engine.dispose())

    first_exit = main()
    first_output = capsys.readouterr().out
    second_exit = main()
    second_output = capsys.readouterr().out

    assert first_exit == EXIT_OK
    assert "Found 2 action item(s)" in first_output
    assert "Seeded 2: sig_billing_defect, sig_network_adequacy" in first_output
    assert "Skipped 0" in first_output

    assert second_exit == EXIT_OK
    assert "Seeded 0 — every item found was already seeded." in second_output
    assert "Skipped 2 already seeded: sig_billing_defect, sig_network_adequacy" in second_output

    app = create_app(settings)
    # Built via `create_app` directly rather than the `app`/`client` fixtures
    # in `tests/conftest.py`, so it does not inherit their pre-authenticated
    # override — add it here too, since this test is about seeding, not auth.
    app.dependency_overrides[require_session] = lambda: Session(email="test@example.com")
    with TestClient(app) as client:
        board = client.get(BOARD_URL).json()

    assert len(board["actions"]) == 2, "the second run must not have doubled the board"
    billing = next(a for a in board["actions"] if a["issueKey"] == "sig_billing_defect")
    assert billing["owner"] is None
    assert billing["due"] is None
    assert billing["actionTaken"] is None
    assert billing["outcome"] is None
    assert billing["measurementWindow"] is None
    assert billing["ownerTeam"] == "Operations / Finance"
    assert set(billing["callIds"]) == {"C-0001", "C-0002"}
