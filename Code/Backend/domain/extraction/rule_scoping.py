"""Which of the 122 rules L3 and L4 are shown for one call (plan §7:
"given only the rules for the call's category and product line, never all
122").

**Program and Administration rules are never scoped out.** Both govern
eligibility, billing, COBRA and the renewal timeline — concerns that cut
across every product line, not things a dental call and a life call would
cite differently. Only Carrier rules (waiting periods, network rules,
benefit limits — what a member actually receives) are line-specific, so
only those are filtered.

**How a Carrier rule is matched to a product line.** The Rules — Carrier
sheet's own "Carrier / line" column names the line directly in most rows
("Ameritas — dental PPO", "EyeMed — vision", "Landmark — chiro/acu") —
matched by the product line's own word appearing in that text. Two carrier
names don't say the word: "DeltaCare USA — DHMO" is a dental HMO product,
and "Anthem / Delta PPO / EyeMed" bundles dental and vision — both
confirmed against the real Rules — Carrier sheet and listed explicitly
below rather than guessed from the name alone.

This is a first cut, not a claim of completeness — a rule whose real scope
this heuristic gets wrong is shown to the wrong calls, which is a finding
for Phase 5's evaluation harness to surface, not something to declare
correct here.
"""

from __future__ import annotations

from domain.entities.rule import Rule
from domain.value_objects.product_line import ProductLine
from domain.value_objects.rule_layer import RuleLayer

# Carrier/line names that don't literally contain their product line's
# word — confirmed against the real Rules — Carrier sheet.
_KNOWN_CARRIER_LINES: dict[str, frozenset[ProductLine]] = {
    "deltacare usa — dhmo": frozenset({ProductLine.DENTAL}),
    "anthem / delta ppo / eyemed": frozenset({ProductLine.DENTAL, ProductLine.VISION}),
}


def _carrier_rule_product_lines(rule: Rule) -> frozenset[ProductLine]:
    known = _KNOWN_CARRIER_LINES.get(rule.area.strip().casefold())
    if known is not None:
        return known

    text = rule.area.casefold()
    return frozenset(line for line in ProductLine if line.value in text)


def scope_rules(
    rules: tuple[Rule, ...], product_lines: tuple[ProductLine, ...]
) -> tuple[Rule, ...]:
    """The rules relevant to a call touching `product_lines`."""
    wanted = frozenset(product_lines)
    scoped = [
        rule
        for rule in rules
        if rule.layer is not RuleLayer.CARRIER or _carrier_rule_product_lines(rule) & wanted
    ]
    return tuple(scoped)
