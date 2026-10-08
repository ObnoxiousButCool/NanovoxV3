"""Typed application configuration.

Every tunable value in the system is read here, from the environment or a
``.env`` file, and validated once at import of the settings object. Nothing
else in the codebase reads ``os.environ``.

Configuration is validated eagerly so a bad value fails at startup with an
explicit message rather than surfacing as an obscure error on first use.

Scoped to what Phase 0 needs (application, database, logging), plus what
Phase 1 (reference data), Phase 2 (corpus/ingestion), Phase 3 (model
providers) and Phase 6 (dashboard thresholds) have added since. Later
phases add their own blocks the same way — the rubric config path in
Phase 4 — rather than declaring fields nothing reads yet.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, ValidationInfo, field_validator, model_validator
from pydantic import ValidationError as PydanticValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from domain.errors import ConfigurationError
from infrastructure.config.paths import (
    BACKEND_ROOT,
    DEFAULT_APPROVED_EMAILS_PATH,
    DEFAULT_CONFIG_DIR,
    DEFAULT_FRONTEND_DIST,
    DEFAULT_LOG_DIR,
    DEFAULT_RUBRIC_PATH,
    DEFAULT_TRANSCRIPTS_DIR,
    DEFAULT_WORKBOOK_PATH,
    default_database_url,
)

AppEnv = Literal["local", "dev", "prod"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
LogFormat = Literal["json", "text"]
EmailBackend = Literal["console", "smtp"]

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
    # A directory, not one file: the corpus arrives in batches short of a
    # 600-call target, and every current batch's PDF sits directly in here
    # (Documents/notes/Corpus-v10-Schema-Update.md). A superseded revision lives in
    # `<dir>/superseded/` instead, so it is kept as a fixture without ever
    # being ingested alongside its replacement.
    transcripts_dir: Path = DEFAULT_TRANSCRIPTS_DIR
    rubric_path: Path = DEFAULT_RUBRIC_PATH

    # --- Dashboard thresholds (plan §8 Phase 6) ----------------------------
    # Min n per metric, the risk-flag numbers, peer bands and quality bands,
    # transcribed from the workbook. A path rather than the values themselves:
    # thresholds are versioned data, and `.env` is not where a number anyone
    # has to defend in front of a client belongs.
    dashboard_config_path: Path = DEFAULT_CONFIG_DIR / "dashboard.yaml"
    # The playbook catalogue behind every issue key a screen links to
    # (Revised plan Phase 4, I3). Validated at startup, like the thresholds.
    playbooks_path: Path = DEFAULT_CONFIG_DIR / "playbooks.yaml"
    # The action centre's lanes and what each requires (D14, U3: config,
    # not code, until the client confirms the lifecycle).
    action_lifecycle_path: Path = DEFAULT_CONFIG_DIR / "action_lifecycle.yaml"

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

    # --- Email-OTP login (feature/email-otp-login, not on main) ------------
    # The allowlist a sign-in attempt is checked against. A config file, like
    # the dashboard thresholds and the action lifecycle, not a database table.
    approved_emails_path: Path = DEFAULT_APPROVED_EMAILS_PATH
    # `console` logs the code instead of emailing it — the default, so the
    # whole flow runs with nothing configured. Switch to `smtp` once an
    # account exists to send from.
    email_backend: EmailBackend = "console"
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_address: str = ""
    smtp_use_tls: bool = True
    otp_expiry_minutes: int = Field(default=10, ge=1, le=60)
    otp_max_attempts: int = Field(default=5, ge=1, le=20)
    # How soon after one code the same address may be sent another. Guards
    # against a reader mashing "resend" into a burst of emails, not against a
    # determined attacker — that is `otp_max_attempts`' job.
    otp_resend_cooldown_seconds: int = Field(default=30, ge=0, le=600)
    # Signs the session token. There is no safe default: an empty secret
    # would make every session forgeable, so this is required wherever
    # `email_backend` is anything other than a throwaway local run.
    jwt_secret: str = ""
    jwt_expiry_minutes: int = Field(default=12 * 60, ge=1, le=30 * 24 * 60)

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

    @field_validator("jwt_secret")
    @classmethod
    def _jwt_secret_required_outside_local(cls, value: str, info: ValidationInfo) -> str:
        # A forgeable session is a local-only convenience, never a deployed
        # one — unlike the other settings here, there is no safe default to
        # fall back to, so this fails at startup rather than at the first
        # sign-in attempt.
        app_env = info.data.get("app_env", "local")
        if app_env != "local" and not value.strip():
            raise ValueError("JWT_SECRET must be set outside local development")
        return value

    @model_validator(mode="after")
    def _smtp_backend_is_fully_configured(self) -> Settings:
        if self.email_backend != "smtp":
            return self
        missing = [
            name
            for name, value in (
                ("SMTP_HOST", self.smtp_host),
                ("SMTP_USERNAME", self.smtp_username),
                ("SMTP_PASSWORD", self.smtp_password),
                ("SMTP_FROM_ADDRESS", self.smtp_from_address),
            )
            if not value.strip()
        ]
        if missing:
            raise ValueError(f"EMAIL_BACKEND=smtp requires {', '.join(missing)}")
        return self

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

    @property
    def effective_jwt_secret(self) -> str:
        """The secret actually used to sign sessions.

        Outside local development `jwt_secret` is required (see the
        validator above) and this is just it. Left unset in local
        development, a random one is generated for the life of the
        process instead of failing — sessions will not survive a restart,
        the same trade a `console` email backend already makes so the
        whole sign-in flow runs with nothing configured.
        """
        return self.jwt_secret if self.jwt_secret.strip() else secrets.token_urlsafe(32)


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
