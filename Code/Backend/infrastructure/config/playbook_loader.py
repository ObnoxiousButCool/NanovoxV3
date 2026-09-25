"""Read `config/playbooks.yaml` into `domain.playbooks.PlaybookCatalogue`.

Strict in the way `dashboard_config.py` is: a missing key is an error rather
than a default, and so is an unknown one. A playbook with `stepz:` would
otherwise load looking configured and render with no steps. Loaded once, in
`build_container`, so a broken catalogue stops the application from starting
instead of surfacing as an empty panel.
"""

from __future__ import annotations

from pathlib import Path

from domain.errors import ConfigurationError, ValidationError
from domain.playbooks import (
    DynamicKind,
    DynamicTemplate,
    HeldBack,
    Playbook,
    PlaybookCatalogue,
    PlaybookSeverity,
    PlaybookUnit,
)
from domain.value_objects.action_source_kind import ActionSourceKind
from infrastructure.config.yaml_support import YamlReader, load_yaml_mapping

_SOURCE = "playbooks.yaml"
_TOP_LEVEL = frozenset({"version", "reviewed", "review_note", "playbooks", "dynamic", "held_back"})
_PLAYBOOK = frozenset(
    {"label", "unit", "owner_team", "severity", "source", "meaning", "why", "steps"}
)
_PLAYBOOK_REQUIRED = _PLAYBOOK - {"source"}
_TEMPLATE = frozenset({"noun", "meaning", "why", "default_owner_team", "owner_overrides", "steps"})
_TEMPLATE_REQUIRED = _TEMPLATE - {"owner_overrides"}


def load_playbooks(path: Path) -> PlaybookCatalogue:
    """Parse and validate the catalogue at `path`."""
    raw = load_yaml_mapping(path, description="Playbook catalogue")
    document = YamlReader(raw, source=_SOURCE)
    _keys(raw, _TOP_LEVEL, _TOP_LEVEL, "the document")

    reviewed = document.require("reviewed")
    if not isinstance(reviewed, bool):
        raise ConfigurationError(f"{_SOURCE}: reviewed must be true or false.")

    try:
        return PlaybookCatalogue(
            version=document.string("version"),
            reviewed=reviewed,
            review_note=document.string("review_note"),
            playbooks=tuple(
                _playbook(key, entry) for key, entry in document.mapping_items("playbooks")
            ),
            templates=tuple(
                _template(key, entry) for key, entry in document.mapping_items("dynamic")
            ),
            held_back=_held_back(document.mapping("held_back")),
        )
    except ValidationError as exc:  # a domain invariant: surface it as configuration
        raise ConfigurationError(f"{_SOURCE}: {exc.message}") from exc


def _playbook(key: str, entry: YamlReader) -> Playbook:
    _keys(_raw(entry), _PLAYBOOK, _PLAYBOOK_REQUIRED, f"playbooks.{key}")
    source = entry.optional_string("source")
    return Playbook(
        key=key,
        label=entry.string("label"),
        unit=entry.enum("unit", PlaybookUnit, expected="calls, accounts or actions"),
        owner_team=entry.string("owner_team"),
        severity=entry.enum("severity", PlaybookSeverity, expected="high or medium"),
        meaning=entry.string("meaning"),
        why=entry.string("why"),
        steps=_strings(entry, "steps", f"playbooks.{key}"),
        source=_source(source, key) if source is not None else None,
    )


def _template(key: str, entry: YamlReader) -> DynamicTemplate:
    where = f"dynamic.{key}"
    _keys(_raw(entry), _TEMPLATE, _TEMPLATE_REQUIRED, where)
    try:
        kind = DynamicKind(key)
    except ValueError as exc:
        raise ConfigurationError(
            f"{_SOURCE}: {where} is not a dynamic kind.",
            detail=f"Expected one of {[k.value for k in DynamicKind]}.",
        ) from exc
    overrides: dict[str, str] = {}
    if "owner_overrides" in _raw(entry):
        block = entry.mapping("owner_overrides")
        overrides = {name: block.string(name) for name in block.keys()}  # noqa: SIM118
    return DynamicTemplate(
        kind=kind,
        noun=entry.string("noun"),
        meaning=entry.string("meaning"),
        why=entry.string("why"),
        steps=_strings(entry, "steps", where),
        default_owner_team=entry.string("default_owner_team"),
        owner_overrides=overrides,
    )


def _held_back(block: YamlReader) -> tuple[HeldBack, ...]:
    return tuple(HeldBack(key=key, reason=block.string(key)) for key in block.keys())  # noqa: SIM118


def _source(value: str, key: str) -> ActionSourceKind:
    try:
        return ActionSourceKind(value)
    except ValueError as exc:
        raise ConfigurationError(
            f"{_SOURCE}: playbooks.{key}.source is not an action source.",
            detail=f"Got {value!r}; expected one of {[k.value for k in ActionSourceKind]}.",
        ) from exc


def _strings(entry: YamlReader, key: str, where: str) -> tuple[str, ...]:
    value = entry.require(key)
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or not item.strip() for item in value)
    ):
        raise ConfigurationError(
            f"{_SOURCE}: {where}.{key} must be a non-empty list of non-empty strings.",
            detail=f"Got {value!r}.",
        )
    return tuple(value)


def _keys(
    block: dict[str, object], allowed: frozenset[str], required: frozenset[str], where: str
) -> None:
    unknown = sorted(set(block) - allowed)
    missing = sorted(required - set(block))
    if unknown:
        raise ConfigurationError(f"{_SOURCE}: {where} has unknown keys {unknown}.")
    if missing:
        raise ConfigurationError(f"{_SOURCE}: {where} is missing {missing}.")


def _raw(entry: YamlReader) -> dict[str, object]:
    return {key: entry.require(key) for key in entry.keys()}  # noqa: SIM118
