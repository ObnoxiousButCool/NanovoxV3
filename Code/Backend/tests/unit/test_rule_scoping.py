"""Rule scoping: Program/Administration rules apply everywhere; Carrier
rules are filtered to the call's own product lines.
"""

from __future__ import annotations

from domain.entities.rule import Rule
from domain.extraction.rule_scoping import scope_rules
from domain.value_objects.product_line import ProductLine
from domain.value_objects.rule_confidence import RuleConfidence
from domain.value_objects.rule_layer import RuleLayer


def _rule(reference: str, layer: RuleLayer, area: str) -> Rule:
    return Rule(
        reference=reference,
        layer=layer,
        area=area,
        text="Some rule text.",
        commonly_confused_with="Something else.",
        source="Test Source",
        confidence=RuleConfidence.VERIFIED,
    )


_PROGRAM = _rule("P-01", RuleLayer.PROGRAM, "Group eligibility")
_ADMIN = _rule("A-01", RuleLayer.ADMINISTRATION, "New hires")
_DENTAL_CARRIER = _rule("C-01", RuleLayer.CARRIER, "Ameritas — dental PPO")
_VISION_CARRIER = _rule("C-02", RuleLayer.CARRIER, "EyeMed — vision")
_DELTACARE = _rule("C-03", RuleLayer.CARRIER, "DeltaCare USA — DHMO")
_BUNDLED = _rule("C-04", RuleLayer.CARRIER, "Anthem / Delta PPO / EyeMed")

ALL = (_PROGRAM, _ADMIN, _DENTAL_CARRIER, _VISION_CARRIER, _DELTACARE, _BUNDLED)


def test_program_rules_are_always_included() -> None:
    assert _PROGRAM in scope_rules(ALL, (ProductLine.LIFE,))


def test_administration_rules_are_always_included() -> None:
    assert _ADMIN in scope_rules(ALL, (ProductLine.VISION,))


def test_a_carrier_rule_naming_its_line_directly_is_matched() -> None:
    scoped = scope_rules(ALL, (ProductLine.DENTAL,))

    assert _DENTAL_CARRIER in scoped
    assert _VISION_CARRIER not in scoped


def test_a_carrier_rule_for_an_untouched_line_is_excluded() -> None:
    scoped = scope_rules(ALL, (ProductLine.CHIRO,))

    assert _DENTAL_CARRIER not in scoped
    assert _VISION_CARRIER not in scoped


def test_deltacare_usa_is_known_to_be_dental_though_the_name_doesnt_say_so() -> None:
    assert _DELTACARE in scope_rules(ALL, (ProductLine.DENTAL,))
    assert _DELTACARE not in scope_rules(ALL, (ProductLine.VISION,))


def test_a_bundled_carrier_line_matches_every_line_it_bundles() -> None:
    assert _BUNDLED in scope_rules(ALL, (ProductLine.DENTAL,))
    assert _BUNDLED in scope_rules(ALL, (ProductLine.VISION,))
    assert _BUNDLED not in scope_rules(ALL, (ProductLine.LIFE,))


def test_multiple_product_lines_union_their_carrier_rules() -> None:
    scoped = scope_rules(ALL, (ProductLine.DENTAL, ProductLine.VISION))

    assert _DENTAL_CARRIER in scoped
    assert _VISION_CARRIER in scoped


def test_no_product_lines_excludes_every_carrier_rule_but_keeps_program_and_admin() -> None:
    scoped = scope_rules(ALL, ())

    assert _PROGRAM in scoped
    assert _ADMIN in scoped
    assert _DENTAL_CARRIER not in scoped
