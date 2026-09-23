"""The OpenAPI export CLI writes a deterministic document, without starting the app."""

from __future__ import annotations

import json
from pathlib import Path

from frameworks_drivers.cli.openapi import EXIT_OK, main


def test_writes_the_openapi_document(tmp_path: Path) -> None:
    destination = tmp_path / "openapi.json"

    exit_code = main([str(destination)])

    assert exit_code == EXIT_OK
    document = json.loads(destination.read_text(encoding="utf-8"))
    assert "/api/v1/health" in document["paths"]


def test_output_is_byte_identical_across_runs(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    main([str(first)])
    main([str(second)])

    assert first.read_bytes() == second.read_bytes()


def test_creates_the_destination_directory(tmp_path: Path) -> None:
    destination = tmp_path / "nested" / "openapi.json"

    exit_code = main([str(destination)])

    assert exit_code == EXIT_OK
    assert destination.is_file()
