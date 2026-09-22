"""Logging configuration: off leaves no trace, on writes app and access files."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

from infrastructure.logging.setup import (
    ACCESS_LOG_FILENAME,
    ACCESS_LOGGER_NAME,
    APP_LOG_FILENAME,
    JsonFormatter,
    configure_logging,
    shutdown_logging,
)
from tests.support.settings import make_settings


def test_disabled_logging_creates_no_directory(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    settings = make_settings(log_enabled=False, log_dir=log_dir)

    try:
        configure_logging(settings)
        assert not log_dir.exists()
    finally:
        shutdown_logging()


def test_enabled_logging_writes_app_and_access_files(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    settings = make_settings(
        log_enabled=True, log_to_console=False, log_dir=log_dir, log_format="json"
    )

    try:
        configure_logging(settings)
        logging.getLogger("nanovox_insights.test").info("hello")
        logging.getLogger(ACCESS_LOGGER_NAME).info("request completed")

        app_log = (log_dir / APP_LOG_FILENAME).read_text(encoding="utf-8").strip()
        access_log = (log_dir / ACCESS_LOG_FILENAME).read_text(encoding="utf-8").strip()

        app_record = json.loads(app_log.splitlines()[-1])
        assert app_record["message"] == "hello"
        assert access_log.splitlines()[-1]
    finally:
        shutdown_logging()


def test_text_format_uses_a_plain_formatter(tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    settings = make_settings(
        log_enabled=True, log_to_console=False, log_dir=log_dir, log_format="text"
    )

    try:
        configure_logging(settings)
        logging.getLogger("nanovox_insights.test").warning("careful")

        app_log = (log_dir / APP_LOG_FILENAME).read_text(encoding="utf-8")
        assert "careful" in app_log
        assert not app_log.strip().startswith("{")
    finally:
        shutdown_logging()


def test_json_formatter_includes_exception_info() -> None:
    formatter = JsonFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.getLogger("test").makeRecord(
            "test", logging.ERROR, __file__, 1, "failed", (), exc_info=sys.exc_info()
        )

    payload = json.loads(formatter.format(record))

    assert payload["level"] == "ERROR"
    assert "boom" in payload["exception"]
