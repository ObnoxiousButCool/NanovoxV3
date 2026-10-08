"""The allowlist-management CLI end to end, against a real (temporary) database."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from frameworks_drivers.cli.manage_approved_emails import EXIT_NOT_FOUND, EXIT_OK, main
from infrastructure.config.settings import get_settings
from infrastructure.persistence.models import Base


@pytest.fixture(autouse=True)
def _isolated_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _prepare_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("LOG_ENABLED", "false")
    monkeypatch.setenv("FRONTEND_DIST_PATH", str(tmp_path / "no-frontend"))

    from infrastructure.persistence import tables as _tables  # noqa: F401

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    try:
        Base.metadata.create_all(engine)
    finally:
        engine.dispose()


def test_listing_an_empty_allowlist_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _prepare_db(tmp_path, monkeypatch)

    exit_code = main(["list"])

    assert exit_code == EXIT_OK
    assert "No approved addresses yet." in capsys.readouterr().out


def test_an_added_address_shows_up_in_the_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _prepare_db(tmp_path, monkeypatch)

    add_exit = main(["add", "reader@example.com"])
    capsys.readouterr()
    list_exit = main(["list"])

    assert add_exit == EXIT_OK
    assert list_exit == EXIT_OK
    assert "reader@example.com" in capsys.readouterr().out


def test_adding_the_same_address_twice_is_not_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _prepare_db(tmp_path, monkeypatch)

    first = main(["add", "reader@example.com"])
    second = main(["add", "reader@example.com"])

    assert first == EXIT_OK
    assert second == EXIT_OK


def test_removing_an_added_address_takes_it_off_the_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _prepare_db(tmp_path, monkeypatch)
    main(["add", "reader@example.com"])
    capsys.readouterr()

    exit_code = main(["remove", "reader@example.com"])

    assert exit_code == EXIT_OK
    assert "Removed" in capsys.readouterr().out
    capsys.readouterr()
    main(["list"])
    assert "reader@example.com" not in capsys.readouterr().out


def test_removing_an_address_never_added_reports_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _prepare_db(tmp_path, monkeypatch)

    exit_code = main(["remove", "stranger@example.com"])

    assert exit_code == EXIT_NOT_FOUND
    assert "Not on the list" in capsys.readouterr().out
