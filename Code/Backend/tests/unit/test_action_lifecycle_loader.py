"""`config/action_lifecycle.yaml`: strict to read, and the shipped one enforces
the plan's rule."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from domain.actions import Requirement
from domain.errors import ConfigurationError
from infrastructure.config.action_lifecycle_loader import load_action_lifecycle
from infrastructure.config.paths import DEFAULT_CONFIG_DIR

_SHIPPED = DEFAULT_CONFIG_DIR / "action_lifecycle.yaml"


def _shipped() -> dict[str, object]:
    loaded = yaml.safe_load(_SHIPPED.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _write(tmp_path: Path, document: dict[str, object]) -> Path:
    path = tmp_path / "action_lifecycle.yaml"
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def _states(document: dict[str, object]) -> list[dict[str, object]]:
    states = document["states"]
    assert isinstance(states, list)
    return states


def test_the_shipped_lifecycle_has_the_prototypes_seven_lanes_in_order() -> None:
    lifecycle = load_action_lifecycle(_SHIPPED)

    assert [state.code for state in lifecycle.states] == [
        "needs_action",
        "assigned",
        "in_progress",
        "overdue",
        "action_taken",
        "monitoring",
        "completed",
    ]
    assert lifecycle.initial == "needs_action"


def test_the_shipped_lifecycle_requires_a_measurement_for_monitoring_and_completed() -> None:
    """The plan's rule, pinned: editing it out of the config fails CI."""
    lifecycle = load_action_lifecycle(_SHIPPED)

    for code in ("monitoring", "completed"):
        requires = lifecycle.state(code).requires
        assert {Requirement.ACTION_TAKEN, Requirement.MEASUREMENT_WINDOW} <= requires, code
    assert Requirement.OUTCOME in lifecycle.state("completed").requires


def test_only_the_working_lanes_are_open() -> None:
    lifecycle = load_action_lifecycle(_SHIPPED)

    assert {state.code for state in lifecycle.states if state.open} == {
        "needs_action",
        "assigned",
        "in_progress",
        "overdue",
    }


def test_a_misspelt_requirement_is_refused(tmp_path: Path) -> None:
    """Misspelt, the measurement rule would silently stop applying."""
    document = _shipped()
    _states(document)[-1]["requires"] = ["measurment_window"]

    with pytest.raises(ConfigurationError, match="unknown requirement"):
        load_action_lifecycle(_write(tmp_path, document))


def test_an_unknown_state_field_is_refused(tmp_path: Path) -> None:
    document = _shipped()
    _states(document)[0]["colour"] = "red"

    with pytest.raises(ConfigurationError, match="unknown keys"):
        load_action_lifecycle(_write(tmp_path, document))


def test_open_must_be_a_boolean(tmp_path: Path) -> None:
    document = _shipped()
    _states(document)[0]["open"] = "yes"

    with pytest.raises(ConfigurationError, match="true or false"):
        load_action_lifecycle(_write(tmp_path, document))


def test_an_initial_state_not_in_the_list_is_refused(tmp_path: Path) -> None:
    document = _shipped()
    document["initial"] = "archived"

    with pytest.raises(ConfigurationError, match="initial state"):
        load_action_lifecycle(_write(tmp_path, document))
