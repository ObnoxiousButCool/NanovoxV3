"""Typed application configuration.

Every tunable value in the system is read here, from the environment or a
``.env`` file, and validated once at import of the settings object. Nothing
else in the codebase reads ``os.environ``.

Configuration is validated eagerly so a bad value fails at startup with an
explicit message rather than surfacing as an obscure error on first use.

Scoped to what Phase 0 needs (application, database, logging). Later phases
add their own settings blocks here as they need them — LLM provider settings
in Phase 3, corpus/ingestion settings in Phase 2, dashboard/rubric config
paths in Phases 4 and 6 — rather than declaring fields nothing reads yet.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic import ValidationError as PydanticValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from domain.errors import ConfigurationError
from infrastructure.config.paths import (
    BACKEND_ROOT,
    DEFAULT_FRONTEND_DIST,
    DEFAULT_LOG_DIR,
    DEFAULT_TRANSCRIPTS_PATH,
    DEFAULT_WORKBOOK_PATH,
    default_database_url,
)

AppEnv = Literal["local", "dev", "prod"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LogFormat = Literal["json", "text"]

# SQLite is the default local/file-based store; Postgres (asyncpg) is what a
# real deployment points at instead, for storage that survives a redeploy
# (decision D9).
_ASYNC_DATABASE_PREFIXES = ("sqlite+aiosqlite:", "postgresql+asyncpg:")


class Settings(BaseSettings):
    """All backend configuration, sourced from the environment and ``.env``."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application -------------------------------------------------------
    app_env: AppEnv = "local"
    app_name: str = "NanoVox Insights"
    app_version: str = "0.1.0"
    app_host: str = "127.0.0.1"
    app_port: int = Field(default=8000, ge=1, le=65535)
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    # --- Database (decision D9) ---------------------------------------------
    database_url: str = Field(default_factory=default_database_url)
    db_echo: bool = False

    # Serving this from the API is what makes a deployment one process and
    # one origin. Left absent in development: Vite serves the frontend.
    frontend_dist_path: Path = DEFAULT_FRONTEND_DIST

    # --- Reference data (plan §8 Phase 1) -----------------------------------
    workbook_path: Path = DEFAULT_WORKBOOK_PATH
    transcripts_path: Path = DEFAULT_TRANSCRIPTS_PATH

    # --- Logging -----------------------------------------------------------
    log_enabled: bool = True
    log_level: LogLevel = "INFO"
    log_dir: Path = DEFAULT_LOG_DIR
    log_format: LogFormat = "json"
    log_retention_days: int = Field(default=14, ge=1, le=365)
    log_to_console: bool = True

    @field_validator("api_prefix")
    @classmethod
    def _prefix_must_be_rooted(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("API_PREFIX must start with '/'")
        return value.rstrip("/")

    @field_validator("database_url")
    @classmethod
    def _database_must_use_an_async_driver(cls, value: str) -> str:
        # The persistence layer is written against the async SQLAlchemy API. A
        # synchronous URL would fail later, inside a request; catch it here.
        if not value.startswith(_ASYNC_DATABASE_PREFIXES):
            raise ValueError(
                "DATABASE_URL must use an async driver — "
                "sqlite+aiosqlite:///C:/path/to/nanovox_insights.db for a local "
                "file, or postgresql+asyncpg://user:password@host/dbname for "
                "Postgres"
            )
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        """CORS origins as a list, parsed from the comma-separated setting."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def database_file(self) -> Path | None:
        """On-disk location of a SQLite database, or ``None`` for anything else.

        A SQLite URL is the only shape with a triple slash before the path
        (``sqlite+aiosqlite:///...``); a network database like Postgres has no
        on-disk file of its own to create a parent directory for, so this
        naturally and correctly falls through to ``None`` for one.
        """
        _, _, location = self.database_url.partition("///")
        if not location or ":memory:" in location:
            return None
        return Path(location)

    @property
    def is_production(self) -> bool:
        return self.app_env == "prod"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Load and cache the settings, translating validation failure into a domain error.

    Cached because configuration is immutable for the lifetime of the
    process; tests clear the cache explicitly.
    """
    try:
        return Settings()
    except PydanticValidationError as exc:
        problems = "; ".join(
            f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
            for error in exc.errors()
        )
        raise ConfigurationError(
            "Invalid backend configuration — the application cannot start.",
            detail=problems,
        ) from exc
