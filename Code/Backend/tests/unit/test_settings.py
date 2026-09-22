"""Settings validation: fails fast, with a message naming the field."""

from __future__ import annotations

import pytest

from domain.errors import ConfigurationError
from infrastructure.config.settings import get_settings
from tests.support.settings import make_settings


def test_get_settings_wraps_a_bad_environment_in_a_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_settings.cache_clear()
    monkeypatch.setenv("API_PREFIX", "no-leading-slash")

    try:
        with pytest.raises(ConfigurationError) as excinfo:
            get_settings()
        assert "api_prefix" in (excinfo.value.detail or "")
    finally:
        get_settings.cache_clear()


def test_cors_origin_list_splits_and_trims() -> None:
    settings = make_settings(cors_origins=" http://a.test , http://b.test ,,")

    assert settings.cors_origin_list == ["http://a.test", "http://b.test"]


def test_database_file_is_none_for_an_in_memory_database() -> None:
    settings = make_settings(database_url="sqlite+aiosqlite:///:memory:")

    assert settings.database_file is None


def test_database_file_is_none_for_postgres() -> None:
    settings = make_settings(
        database_url="postgresql+asyncpg://user:pw@host/db",
    )

    assert settings.database_file is None


def test_is_production_only_when_app_env_is_prod() -> None:
    assert make_settings(app_env="prod").is_production
    assert not make_settings(app_env="local").is_production
