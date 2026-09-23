"""Group 4 — rules: cited, and failed to explain.

"What do we fail to explain?" The 122 published rules read against the calls
that cite them, which is the one place the corpus records us getting our own
product wrong.

**Counts only, never a per-rule rate.** §9 is explicit about this and the
reason is arithmetic: a rate needs a denominator of "calls where this rule
was in play", and nothing records that. Dividing by calls that *cited* the
rule produces a rate of 1.0 for every rule anyone got wrong, and dividing by
all calls produces a number so small it says nothing. Metric 8's build note
asks for the only defensible output: "a list of knowledge base articles to
rewrite, ranked by call count."

Four cuts, all counts: by rule, by layer (P/A/C), by provenance and by area.
Provenance and area are the Rules sheets' own columns and travel with the
rule rather than being inferred here.

D7 again: a knowledge failure is rolled up by rule id and by touchpoint and
is never attributed to an agent. The agent-conduct event is the separate
`knowledge_error` signal, in `agent_events.py`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from domain.aggregation.call_tags import CallContext, Window
from domain.aggregation.figure import Figure
from domain.aggregation.patterns import share
from domain.dashboard_config import DashboardConfig
from domain.value_objects.rule_confidence import RuleConfidence
from domain.value_objects.rule_layer import RuleLayer


@dataclass(frozen=True)
class RuleFacts:
    """The rule fields a figure may use, from the three Rules sheets."""

    reference: str
    layer: RuleLayer
    area: str
    #: The Rules sheets' own confidence grade — VERIFIED, SECONDARY or
    #: UNVERIFIED. This is provenance of the *rule*, not of any figure about
    #: it, and it is not the panel's epistemic class.
    confidence: RuleConfidence


@dataclass(frozen=True)
class RuleRow:
    """One rule, and the calls that got it wrong."""

    rule_ref: str
    layer: RuleLayer
    area: str
    confidence: RuleConfidence
    #: Calls whose `knowledge_failure` cited this rule.
    failed_call_ids: tuple[str, ...]

    @property
    def failures(self) -> int:
        return len(self.failed_call_ids)


def failures_by_rule(
    rules: Sequence[RuleFacts], calls: Sequence[CallContext], window: Window
) -> tuple[RuleRow, ...]:
    """The rewrite list: rules ranked by how many calls got them wrong.

    Rules with no failures are included at zero. The screen is a reading of
    all 122 published rules, and a list that shows only the broken ones
    cannot answer "how much of the rulebook is actually a problem" — which
    at batch-1 volume is the more honest finding.
    """
    cited: dict[str, list[str]] = {}
    for call in window.calls_in(tuple(calls)):
        failure = call.tags.knowledge_failure
        if failure is not None and failure.present and failure.rule_id:
            cited.setdefault(failure.rule_id, []).append(call.reference)

    rows = [
        RuleRow(
            rule_ref=rule.reference,
            layer=rule.layer,
            area=rule.area,
            confidence=rule.confidence,
            failed_call_ids=tuple(sorted(cited.get(rule.reference, ()))),
        )
        for rule in rules
    ]
    return tuple(sorted(rows, key=lambda row: (-row.failures, row.rule_ref)))


def failures_by_layer(rows: Sequence[RuleRow]) -> tuple[tuple[RuleLayer, int], ...]:
    """Counts by rule layer — Program, Administration, Carrier.

    The layer is who owns the rule, so this answers "whose rulebook is the
    problem" in one line: a carrier's rules misstated is a different
    conversation from our own administration rules misstated.
    """
    counts = dict.fromkeys(RuleLayer, 0)
    for row in rows:
        counts[row.layer] += row.failures
    return tuple((layer, counts[layer]) for layer in RuleLayer)


def failures_by_area(rows: Sequence[RuleRow]) -> tuple[tuple[str, int], ...]:
    """Counts by the Rules sheets' own area column, busiest first."""
    counts: dict[str, int] = {}
    for row in rows:
        if row.failures:
            counts[row.area] = counts.get(row.area, 0) + row.failures
    return tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def failures_by_provenance(rows: Sequence[RuleRow]) -> tuple[tuple[RuleConfidence, int], ...]:
    """Counts by the rule's own confidence grade.

    Worth its own cut: a call that misstated an UNVERIFIED rule is a
    different problem from one that misstated a VERIFIED one. The first says
    our source is weak, the second says our training is.
    """
    counts = dict.fromkeys(RuleConfidence, 0)
    for row in rows:
        counts[row.confidence] += row.failures
    return tuple((confidence, counts[confidence]) for confidence in RuleConfidence)


def knowledge_failure_rate(
    config: DashboardConfig, calls: Sequence[CallContext], window: Window
) -> Figure:
    """Metric 8 overall: calls carrying a knowledge failure, over all calls.

    The one rate this module publishes, and it is about the corpus rather
    than about any single rule. Per-rule rates are the thing §9 forbids.
    """
    in_window = window.calls_in(tuple(calls))
    failed = [
        call
        for call in in_window
        if call.tags.knowledge_failure is not None and call.tags.knowledge_failure.present
    ]
    return share(config.metric("knowledge_failure_rate"), numerator=failed, denominator=in_window)


def failures_by_touchpoint(
    calls: Sequence[CallContext], window: Window
) -> tuple[tuple[str, int], ...]:
    """Knowledge failures by where they originated.

    The Touchpoints sheet argues this answers "what does this organisation
    repeatedly fail to explain, and where" far better than rule id alone —
    the same rule misstated at the enrolment meeting and in the denial
    letter is two different documents to fix.
    """
    counts: dict[str, int] = {}
    for call in window.calls_in(tuple(calls)):
        failure = call.tags.knowledge_failure
        if failure is not None and failure.present:
            where = call.tags.touchpoint or "unattributed"
            counts[where] = counts.get(where, 0) + 1
    return tuple(sorted(counts.items(), key=lambda item: (-item[1], item[0])))
