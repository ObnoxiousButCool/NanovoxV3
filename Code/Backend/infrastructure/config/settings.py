"""Typed application configuration.

Every tunable value in the system is read here, from the environment or a
``.env`` file, and validated once at import of the settings object. Nothing
else in the codebase reads ``os.environ``.

Configuration is validated eagerly so a bad value fails at startup with an
explicit message rather than surfacing as an obscure error on first use.

Scoped to what Phase 0 needs (application, database, logging), plus what
Phase 1 (reference data), Phase 2 (corpus/ingestion) and Phase 3 (model
providers) have added since. Later phases add their own blocks the same
way — dashboard/rubric config paths in Phases 4 and 6 — rather than
declaring fields nothing reads yet.
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

    # --- Model providers (plan §8 Phase 3, decision D1) ---------------------
    # OpenAI gpt-4o-mini is the default; Anthropic and Ollama are the only two
    # extra configurable providers wired in. Azure Foundry is not ported.
    llm_provider: str = "openai"
    llm_timeout_seconds: float = Field(default=120.0, gt=0)
    # Deliberately not llm_timeout_seconds. That budget is for generating one
    # layer's worth of extraction; asking whether a provider is alive must
    # answer in the time a person will wait for a dropdown, and an
    # unreachable host must not hold the picker hostage for two minutes.
    llm_probe_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    llm_max_retries: int = Field(default=2, ge=0, le=10)
    llm_max_output_tokens: int = Field(default=4096, ge=256, le=128_000)

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b-instruct"

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = ""

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-opus-5"

    # --- Logging -----------------------------------------------------------
    log_enabled: bool = True
    log_level: LogLevel = "INFO"
    log_dir: Path = DEFAULT_LOG_DIR
    log_format: LogFormat = "json"
    log_retention_days: int = Field(default=14, ge=1, le=365)
    log_to_console: bool = True
    # Off by default: transcripts are member conversations, and an audit log
    # is not the place to accumulate them.
    log_llm_prompts: bool = False

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

    @field_validator("llm_provider")
    @classmethod
    def _provider_is_normalised(cls, value: str) -> str:
        normalised = value.strip().lower()
        if not normalised:
            raise ValueError("LLM_PROVIDER must not be empty")
        return normalised

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
