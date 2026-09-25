"""Read `config/action_lifecycle.yaml` into `domain.actions.Lifecycle`.

Strict, like the other config loaders: an unknown key or requirement is an
error, never ignored. A state that meant to require a measurement and
misspelt it would otherwise let a card reach *completed* with none.
"""

from __future__ import annotations

from pathlib import Path

from domain.actions import Lifecycle, LifecycleState, Requirement
from domain.errors import ConfigurationError, ValidationError
from infrastructure.config.yaml_support import YamlReader, load_yaml_mapping

_SOURCE = "action_lifecycle.yaml"
_TOP_LEVEL = frozenset({"initial", "states"})
_STATE = frozenset({"code", "label", "open", "requires"})
_STATE_REQUIRED = _STATE - {"requires"}


def load_action_lifecycle(path: Path) -> Lifecycle:
    raw = load_yaml_mapping(path, description="Action lifecycle")
    _keys(raw, _TOP_LEVEL, _TOP_LEVEL, "the document")
    document = YamlReader(raw, source=_SOURCE)
    states = tuple(_state(entry) for entry in document.sequence_of_mappings("states"))
    try:
        return Lifecycle(states=states, initial=document.string("initial"))
    except ValidationError as exc:
        raise ConfigurationError(f"{_SOURCE}: {exc.message}") from exc


def _state(entry: YamlReader) -> LifecycleState:
    raw = {key: entry.require(key) for key in entry.keys()}  # noqa: SIM118
    code = entry.string("code")
    _keys(raw, _STATE, _STATE_REQUIRED, f"states.{code}")
    is_open = raw["open"]
    if not isinstance(is_open, bool):
        raise ConfigurationError(f"{_SOURCE}: states.{code}.open must be true or false.")
    return LifecycleState(
        code=code,
        label=entry.string("label"),
        open=is_open,
        requires=_requirements(raw.get("requires", []), code),
    )


def _requirements(value: object, code: str) -> frozenset[Requirement]:
    if not isinstance(value, list):
        raise ConfigurationError(f"{_SOURCE}: states.{code}.requires must be a list.")
    try:
        return frozenset(Requirement(item) for item in value)
    except ValueError as exc:
        raise ConfigurationError(
            f"{_SOURCE}: states.{code}.requires names an unknown requirement.",
            detail=f"Got {value!r}; expected any of {[r.value for r in Requirement]}.",
        ) from exc


def _keys(
    block: dict[str, object], allowed: frozenset[str], required: frozenset[str], where: str
) -> None:
    unknown = sorted(set(block) - allowed)
    missing = sorted(required - set(block))
    if unknown:
        raise ConfigurationError(f"{_SOURCE}: {where} has unknown keys {unknown}.")
    if missing:
        raise ConfigurationError(f"{_SOURCE}: {where} is missing {missing}.")
