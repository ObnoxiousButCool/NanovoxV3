"""Group 2 — isolated or systemic (§9 insight 13).

"Port `hierarchy.html`: the drill tree; region-by-category heatmap ('a dark
column is book-wide, a dark cell is local'); the pattern test shown fired
**and** unfired with what it reached."

The whole screen answers one question: is this one unhappy client or
something structural? Three views, each answering it a different way, and
the reading rule for the matrix is the prototype's own — a dark column means
a category is a problem everywhere, a dark cell means it is a problem in one
region. Nothing here decides which; the point is to let a reader see it.

Counts, not rates. A region with four calls and a region with forty produce
incomparable rates, and the tree exists for drilling rather than for
ranking. Where a rate is wanted it is group 1's, over a population.

The pattern test lives in `broker_friction` and is re-exported here, because
it is one test and having two would be how the two screens start disagreeing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from domain.aggregation.broker_friction import PatternTest, pattern_test
from domain.aggregation.call_tags import CallContext, EmployerFacts, Window
from domain.dashboard_config import DashboardConfig
from domain.value_objects.category import Category

__all__ = [
    "EmployerNode",
    "PatternTest",
    "RegionNode",
    "drill_tree",
    "pattern_test",
    "region_category_matrix",
]


@dataclass(frozen=True)
class EmployerNode:
    employer_ref: str
    name: str
    call_ids: tuple[str, ...]

    @property
    def calls(self) -> int:
        return len(self.call_ids)


@dataclass(frozen=True)
class BrokerNode:
    broker_ref: str
    employers: tuple[EmployerNode, ...]

    @property
    def calls(self) -> int:
        return sum(node.calls for node in self.employers)


@dataclass(frozen=True)
class RegionNode:
    region: str
    brokers: tuple[BrokerNode, ...]

    @property
    def calls(self) -> int:
        return sum(node.calls for node in self.brokers)


def drill_tree(
    employers: Sequence[EmployerFacts], calls: Sequence[CallContext], window: Window
) -> tuple[RegionNode, ...]:
    """Region → broker → employer, with the calls at each leaf.

    Employers with no calls in the window are included with an empty leaf
    rather than dropped. "This employer has not called" is information, and
    a tree that silently omits them makes a quiet region look like a small
    one — the filters-slice-never-hide practice, applied to a hierarchy.
    """
    in_window = window.calls_in(tuple(calls))
    by_employer: dict[str, list[str]] = {}
    for call in in_window:
        if call.employer_ref is not None:
            by_employer.setdefault(call.employer_ref, []).append(call.reference)

    regions: dict[str, dict[str, list[EmployerNode]]] = {}
    for employer in employers:
        node = EmployerNode(
            employer_ref=employer.reference,
            name=employer.name,
            call_ids=tuple(sorted(by_employer.get(employer.reference, ()))),
        )
        regions.setdefault(employer.region, {}).setdefault(employer.broker_ref, []).append(node)

    return tuple(
        RegionNode(
            region=region,
            brokers=tuple(
                BrokerNode(broker_ref=broker, employers=tuple(sorted(nodes, key=_by_calls)))
                for broker, nodes in sorted(brokers.items())
            ),
        )
        for region, brokers in sorted(regions.items())
    )


def region_category_matrix(
    employers: Sequence[EmployerFacts], calls: Sequence[CallContext], window: Window
) -> tuple[tuple[str, tuple[tuple[Category, int], ...]], ...]:
    """Calls per region per category — the heatmap's own numbers.

    Every category appears in every row, including at zero. A sparse matrix
    that omits empty cells destroys the reading rule: "a dark column is
    book-wide, a dark cell is local" only works if the columns line up.

    Zero here is a real count, not a withheld figure. The matrix is call
    volume, which the Metrics sheet publishes as base measure B1 with no min
    n — there is nothing to suppress.
    """
    region_of = {employer.reference: employer.region for employer in employers}
    counts: dict[str, dict[Category, int]] = {
        region: dict.fromkeys(Category, 0) for region in sorted(set(region_of.values()))
    }

    for call in window.calls_in(tuple(calls)):
        region = region_of.get(call.employer_ref or "")
        if region is None or call.tags.category is None:
            continue
        counts[region][call.tags.category] += 1

    return tuple(
        (region, tuple((category, row[category]) for category in Category))
        for region, row in counts.items()
    )


def systemic_categories(
    matrix: Sequence[tuple[str, tuple[tuple[Category, int], ...]]],
) -> tuple[Category, ...]:
    """Categories that appear in every region — the dark columns.

    Deliberately weak: presence in every region, not a threshold on volume.
    A stronger test would need a per-region denominator the matrix does not
    carry, and inventing one here would be a judgement dressed as a count.
    The screen shows the matrix; this only names the columns worth reading
    first.
    """
    if not matrix:
        return ()
    everywhere = [
        category
        for category in Category
        if all(any(c is category and n > 0 for c, n in row) for _, row in matrix)
    ]
    return tuple(everywhere)


def _by_calls(node: EmployerNode) -> tuple[int, str]:
    return (-node.calls, node.employer_ref)


def broker_pattern(
    config: DashboardConfig, broker_ref: str, calls: Sequence[CallContext], window: Window
) -> PatternTest:
    """The pattern test, as this screen asks for it — fired and unfired alike."""
    return pattern_test(config, broker_ref, calls, window)
