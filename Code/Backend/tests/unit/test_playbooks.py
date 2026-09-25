"""Resolving issue keys to playbooks, and the catalogue's own invariants."""

from __future__ import annotations

from dataclasses import replace

import pytest

from domain.entities.touchpoint import Touchpoint
from domain.errors import ValidationError
from domain.playbooks import (
    DynamicKind,
    DynamicTemplate,
    HeldBack,
    Playbook,
    PlaybookCatalogue,
    PlaybookSeverity,
    PlaybookUnit,
    resolve,
)
from domain.value_objects.signal_type import SignalType, owner_team_of

_STATIC = Playbook(
    key="unresolved",
    label="Unresolved calls",
    unit=PlaybookUnit.CALLS,
    owner_team="Operations",
    severity=PlaybookSeverity.HIGH,
    meaning="The caller ended where they started.",
    why="They come back.",
    steps=("Call back.",),
)


def _template(kind: DynamicKind, **overrides: object) -> DynamicTemplate:
    fields: dict[str, object] = {
        "kind": kind,
        "noun": kind.name.lower(),
        "meaning": "Calls about the {subject} {noun} are rising.",
        "why": "Controlled by {controls}.",
        "steps": ("Take it to {owner}.",),
        "default_owner_team": "Operations",
    }
    fields.update(overrides)
    return DynamicTemplate(**fields)  # type: ignore[arg-type]


def _catalogue(**overrides: object) -> PlaybookCatalogue:
    fields: dict[str, object] = {
        "version": "test",
        "reviewed": False,
        "review_note": "Unreviewed.",
        "playbooks": (_STATIC,),
        "templates": tuple(
            _template(kind, owner_overrides={"Broker Conduct": "Broker Relations"})
            if kind is DynamicKind.CATEGORY
            else _template(kind)
            for kind in DynamicKind
        ),
        "held_back": (HeldBack("brush_off", "D14: archetype dropped."),),
    }
    fields.update(overrides)
    return PlaybookCatalogue(**fields)  # type: ignore[arg-type]


_TOUCHPOINTS = {
    "denial_letter_eob": Touchpoint("denial_letter_eob", "Claims Operations", "the carrier"),
}


def test_a_static_key_resolves_to_its_playbook() -> None:
    assert resolve(_catalogue(), "unresolved", _TOUCHPOINTS) is _STATIC


def test_a_touchpoint_key_takes_the_touchpoints_sheet_owner_and_controls() -> None:
    playbook = resolve(_catalogue(), "tp_denial_letter_eob", _TOUCHPOINTS)

    assert playbook is not None
    assert playbook.owner_team == "Claims Operations"
    assert playbook.why == "Controlled by the carrier."
    assert playbook.steps == ("Take it to Claims Operations.",)
    assert playbook.label == "Denial letter eob"
    assert playbook.dynamic


def test_a_touchpoint_not_on_the_sheet_resolves_to_nothing() -> None:
    """A dead key must fail rather than render an invented playbook."""
    assert resolve(_catalogue(), "tp_made_up", _TOUCHPOINTS) is None


def test_a_signal_key_is_owned_by_the_signal_taxonomy() -> None:
    """The sheet calls the signal owner mandatory, not advisory."""
    playbook = resolve(_catalogue(), "sig_billing_defect", _TOUCHPOINTS)

    assert playbook is not None
    assert playbook.owner_team == owner_team_of(SignalType.BILLING_DEFECT)


def test_a_category_key_uses_the_override_where_one_exists() -> None:
    broker = resolve(_catalogue(), "cat_Broker Conduct", _TOUCHPOINTS)
    claims = resolve(_catalogue(), "cat_Claims & EOB", _TOUCHPOINTS)

    assert broker is not None and broker.owner_team == "Broker Relations"
    assert claims is not None and claims.owner_team == "Operations"
    assert claims.label == "Claims & EOB"


def test_a_product_line_key_resolves_only_for_a_real_line() -> None:
    assert resolve(_catalogue(), "pl_dental", _TOUCHPOINTS) is not None
    assert resolve(_catalogue(), "pl_pets", _TOUCHPOINTS) is None


@pytest.mark.parametrize("key", ["sig_not_a_signal", "cat_Not a category", "nonsense", "tp_"])
def test_keys_naming_nothing_resolve_to_nothing(key: str) -> None:
    assert resolve(_catalogue(), key, _TOUCHPOINTS) is None


def test_a_held_back_key_reports_its_reason_and_does_not_resolve() -> None:
    catalogue = _catalogue()

    assert catalogue.held_back_reason("brush_off") == "D14: archetype dropped."
    assert resolve(catalogue, "brush_off", _TOUCHPOINTS) is None


def test_duplicate_keys_are_refused() -> None:
    with pytest.raises(ValidationError, match="unique"):
        _catalogue(playbooks=(_STATIC, _STATIC))


def test_a_key_cannot_be_both_shipped_and_held_back() -> None:
    with pytest.raises(ValidationError, match="both shipped and held back"):
        _catalogue(held_back=(HeldBack("unresolved", "no"),))


def test_every_dynamic_kind_needs_a_template() -> None:
    with pytest.raises(ValidationError, match="exactly one template"):
        _catalogue(templates=(_template(DynamicKind.TOUCHPOINT),))


def test_a_static_key_may_not_shadow_a_dynamic_prefix() -> None:
    with pytest.raises(ValidationError, match="collides"):
        _catalogue(playbooks=(_STATIC, replace(_STATIC, key="tp_enrolment")))


@pytest.mark.parametrize("steps", [(), ("Call back.", "  ")])
def test_a_playbook_without_real_steps_is_refused(steps: tuple[str, ...]) -> None:
    with pytest.raises(ValidationError, match="steps"):
        replace(_STATIC, steps=steps)


def test_a_playbook_without_an_owner_is_refused() -> None:
    with pytest.raises(ValidationError, match="owner_team"):
        replace(_STATIC, owner_team=" ")
