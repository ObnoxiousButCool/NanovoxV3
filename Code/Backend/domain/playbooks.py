"""The playbook catalogue behind every issue a screen can link to (Revised
plan Phase 4, checkpoint I3).

Every red or orange number on a screen links to the focused action view for
an *issue key*: what the issue means, why it matters, the suggested owner and
the steps. Keys are referenced from every screen and resolved here, once, so
a key nobody defined fails in CI rather than rendering an empty panel.

## Two kinds of key

**Static keys** — `unresolved`, `escalation_missed`, `flagged`, … — are
written out in `config/playbooks.yaml`.

**Dynamic keys** name one value of a vocabulary: `tp_<touchpoint>`,
`cat_<category>`, `sig_<signal>`, `pl_<product line>`. The executive screen's
emerging issues link to them. They resolve from a per-kind template, and only
for a value that exists — a touchpoint on the Touchpoints sheet, a Category,
a SignalType or a ProductLine. `tp_made_up` resolves to nothing.

## The steps are recommendations, and unreviewed ones

The prototype says so plainly: the steps are generic good practice and need
review by the owning teams before use (Revised plan R7). The catalogue
carries `reviewed` so the response can say it, and every playbook is a
recommendation rather than a measurement (D14, C3a).

## Owner comes from the workbook where the workbook has one

A touchpoint's owner is the Touchpoints sheet's; a signal's is the Signal
Taxonomy's, which the sheet calls mandatory. Only categories and product
lines, which carry no owner in the workbook, fall back to the catalogue's
default.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from domain.entities.touchpoint import Touchpoint
from domain.errors import ValidationError
from domain.value_objects.action_source_kind import ActionSourceKind
from domain.value_objects.category import Category
from domain.value_objects.product_line import ProductLine
from domain.value_objects.signal_type import SignalType, owner_team_of


class PlaybookUnit(StrEnum):
    """What the issue counts."""

    CALLS = "calls"
    ACCOUNTS = "accounts"
    ACTIONS = "actions"


class PlaybookSeverity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"


class DynamicKind(StrEnum):
    """The prefix of a dynamic key, before the underscore."""

    TOUCHPOINT = "tp"
    CATEGORY = "cat"
    SIGNAL = "sig"
    PRODUCT_LINE = "pl"


@dataclass(frozen=True)
class Playbook:
    key: str
    label: str
    unit: PlaybookUnit
    owner_team: str
    severity: PlaybookSeverity
    meaning: str
    why: str
    steps: tuple[str, ...]
    #: The kind of action this issue produces, when it produces one.
    source: ActionSourceKind | None = None
    dynamic: bool = False

    def __post_init__(self) -> None:
        for name in ("key", "label", "owner_team", "meaning", "why"):
            if not getattr(self, name).strip():
                raise ValidationError(f"Playbook {self.key!r} has an empty {name}.")
        if not self.steps or any(not step.strip() for step in self.steps):
            raise ValidationError(f"Playbook {self.key!r} must have steps, none of them blank.")


@dataclass(frozen=True)
class DynamicTemplate:
    """How one dynamic kind is written. `{subject}` is the value's label;
    `{owner}` the resolved owner team; `{controls}` a touchpoint's
    Touchpoints-sheet `controls`."""

    kind: DynamicKind
    noun: str
    meaning: str
    why: str
    steps: tuple[str, ...]
    #: Used only where the workbook names no owner — categories and
    #: product lines.
    default_owner_team: str
    owner_overrides: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class HeldBack:
    """A prototype key deliberately not shipped, and the decision that holds it."""

    key: str
    reason: str


@dataclass(frozen=True)
class PlaybookCatalogue:
    version: str
    reviewed: bool
    review_note: str
    playbooks: tuple[Playbook, ...]
    templates: tuple[DynamicTemplate, ...]
    held_back: tuple[HeldBack, ...] = ()

    def __post_init__(self) -> None:
        keys = [playbook.key for playbook in self.playbooks]
        if len(keys) != len(set(keys)):
            raise ValidationError("Playbook keys must be unique.")
        held = {entry.key for entry in self.held_back}
        if held & set(keys):
            raise ValidationError(f"Keys both shipped and held back: {sorted(held & set(keys))}.")
        kinds = [template.kind for template in self.templates]
        if sorted(kinds) != sorted(DynamicKind):
            raise ValidationError("Every dynamic kind needs exactly one template.")
        for key in keys:
            if _split_dynamic(key) is not None:
                raise ValidationError(f"Static key {key!r} collides with a dynamic prefix.")

    def static(self, key: str) -> Playbook | None:
        return next((playbook for playbook in self.playbooks if playbook.key == key), None)

    def held_back_reason(self, key: str) -> str | None:
        return next((entry.reason for entry in self.held_back if entry.key == key), None)

    def template(self, kind: DynamicKind) -> DynamicTemplate:
        return next(template for template in self.templates if template.kind is kind)


def resolve(
    catalogue: PlaybookCatalogue, key: str, touchpoints: Mapping[str, Touchpoint]
) -> Playbook | None:
    """The playbook for `key`, or `None` when the key names nothing.

    `touchpoints` is the Touchpoints sheet by reference; a `tp_` key for a
    touchpoint not on it resolves to nothing rather than to a guess.
    """
    found = catalogue.static(key)
    if found is not None:
        return found

    split = _split_dynamic(key)
    if split is None:
        return None
    kind, value = split
    template = catalogue.template(kind)

    controls = ""
    if kind is DynamicKind.TOUCHPOINT:
        touchpoint = touchpoints.get(value)
        if touchpoint is None:
            return None
        subject = _humanise(value)
        owner = touchpoint.owner
        controls = touchpoint.controls
    elif kind is DynamicKind.SIGNAL:
        try:
            signal = SignalType(value)
        except ValueError:
            return None
        subject = _humanise(value)
        owner = owner_team_of(signal)
    elif kind is DynamicKind.CATEGORY:
        if value not in {category.value for category in Category}:
            return None
        subject = value
        owner = template.owner_overrides.get(value, template.default_owner_team)
    else:
        if value not in {line.value for line in ProductLine}:
            return None
        subject = _humanise(value)
        owner = template.owner_overrides.get(value, template.default_owner_team)

    def fill(text: str) -> str:
        return text.format(subject=subject, noun=template.noun, owner=owner, controls=controls)

    return Playbook(
        key=key,
        label=subject,
        unit=PlaybookUnit.CALLS,
        owner_team=owner,
        severity=PlaybookSeverity.MEDIUM,
        meaning=fill(template.meaning),
        why=fill(template.why),
        steps=tuple(fill(step) for step in template.steps),
        dynamic=True,
    )


def _split_dynamic(key: str) -> tuple[DynamicKind, str] | None:
    prefix, _, value = key.partition("_")
    if not value:
        return None
    try:
        return DynamicKind(prefix), value
    except ValueError:
        return None


def _humanise(code: str) -> str:
    """`denial_letter_eob` -> `Denial letter eob`. Only the first letter is
    raised: title case would read "Denial Letter Eob"."""
    words = code.replace("_", " ").strip()
    return words[:1].upper() + words[1:]
