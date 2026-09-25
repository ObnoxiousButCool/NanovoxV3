"""`config/playbooks.yaml` is read strictly: nothing unknown, nothing missing."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from domain.errors import ConfigurationError
from infrastructure.config.paths import DEFAULT_CONFIG_DIR
from infrastructure.config.playbook_loader import load_playbooks


def _shipped() -> dict[str, object]:
    loaded = yaml.safe_load((DEFAULT_CONFIG_DIR / "playbooks.yaml").read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _write(tmp_path: Path, document: dict[str, object]) -> Path:
    path = tmp_path / "playbooks.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def _playbook(document: dict[str, object], key: str = "unresolved") -> dict[str, object]:
    playbooks = document["playbooks"]
    assert isinstance(playbooks, dict)
    entry = playbooks[key]
    assert isinstance(entry, dict)
    return entry


def test_the_shipped_catalogue_loads(tmp_path: Path) -> None:
    catalogue = load_playbooks(_write(tmp_path, _shipped()))

    assert catalogue.static("unresolved") is not None


def test_an_unknown_top_level_key_is_refused(tmp_path: Path) -> None:
    document = _shipped()
    document["playbookz"] = {}

    with pytest.raises(ConfigurationError, match="unknown keys"):
        load_playbooks(_write(tmp_path, document))


def test_a_misspelt_playbook_field_is_refused(tmp_path: Path) -> None:
    """`stepz:` would otherwise load looking configured, with no steps."""
    document = _shipped()
    entry = _playbook(document)
    entry["stepz"] = entry.pop("steps")

    with pytest.raises(ConfigurationError, match="unknown keys"):
        load_playbooks(_write(tmp_path, document))


def test_a_missing_owner_is_refused(tmp_path: Path) -> None:
    document = _shipped()
    del _playbook(document)["owner_team"]

    with pytest.raises(ConfigurationError, match="missing"):
        load_playbooks(_write(tmp_path, document))


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("unit", "employers", "calls, accounts or actions"),
        ("severity", "critical", "high or medium"),
        ("source", "gossip", "not an action source"),
        ("steps", [], "non-empty list"),
    ],
)
def test_bad_values_are_refused(tmp_path: Path, field: str, value: object, message: str) -> None:
    document = _shipped()
    _playbook(document)[field] = value

    with pytest.raises(ConfigurationError, match=message):
        load_playbooks(_write(tmp_path, document))


def test_reviewed_must_be_a_boolean(tmp_path: Path) -> None:
    document = _shipped()
    document["reviewed"] = "no"

    with pytest.raises(ConfigurationError, match="true or false"):
        load_playbooks(_write(tmp_path, document))


def test_an_unknown_dynamic_kind_is_refused(tmp_path: Path) -> None:
    document = _shipped()
    dynamic = document["dynamic"]
    assert isinstance(dynamic, dict)
    dynamic["emp"] = dynamic["pl"]

    with pytest.raises(ConfigurationError, match="not a dynamic kind"):
        load_playbooks(_write(tmp_path, document))


def test_a_catalogue_invariant_surfaces_as_configuration(tmp_path: Path) -> None:
    """Shipping a held-back key is a configuration error, reported as one."""
    document = _shipped()
    held = document["held_back"]
    assert isinstance(held, dict)
    held["unresolved"] = "held for no reason"

    with pytest.raises(ConfigurationError, match="both shipped and held back"):
        load_playbooks(_write(tmp_path, document))


def test_a_missing_file_is_a_configuration_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="not found"):
        load_playbooks(tmp_path / "absent.yaml")
