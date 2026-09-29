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

from domain.aggregation.broker_friction import PatternTest, adverse_mentions, pattern_test
from domain.aggregation.call_tags import BrokerFacts, CallContext, EmployerFacts, Window
from domain.aggregation.risk_flag import assess
from domain.dashboard_config import DashboardConfig
from domain.value_objects.category import Category
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.outcome import Outcome

__all__ = [
    "BrokerRow",
    "ComplaintOwnership",
    "EmployerNode",
    "PatternTest",
    "RegionNode",
    "RegionRow",
    "broker_rows",
    "complaint_ownership",
    "drill_tree",
    "pattern_test",
    "region_category_matrix",
    "region_rows",
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


@dataclass(frozen=True)
class RegionRow:
    """One region, as the "By region" table counts it.

    `accounts` is every employer reference data puts in the region, not
    every employer that called. A region where four of sixteen accounts
    rang is not a four-account region, and a table that said so would make
    the quiet ones disappear — the same rule `drill_tree` already keeps.
    """

    region: str
    accounts: int
    flagged: int
    calls: int
    unresolved: int


@dataclass(frozen=True)
class BrokerRow:
    """One broker, as the "By broker" table counts it.

    Reference fields travel with the counts because the table shows them
    side by side and the point of that is the comparison: `groups_in_book`
    comes from the Broker Master sheet and never from a count of calls, so
    the denominator beside the numerator is not built out of it.

    No rate. A three-group broker has roughly ten calls, and the prototype
    says plainly why it shows none: there is not enough there to divide.
    `broker_friction` publishes one where a book is big enough, and that is
    a different table answering a different question.
    """

    broker_ref: str
    agency: str
    name: str
    region: str
    groups_in_book: int
    calls: int
    adverse_mentions: int
    adverse_employers: int
    pattern_fires: bool
    #: What the test reached, fired or not. §9 asks for the pattern test
    #: "shown fired **and** unfired with what it reached" — a table that
    #: only showed the firing ones would leave a reader unable to tell a
    #: broker one mention short from one nobody has ever named.
    pattern_reached: str
    flagged_accounts: int


def region_rows(
    config: DashboardConfig,
    employers: Sequence[EmployerFacts],
    calls: Sequence[CallContext],
    window: Window,
    risk_window: Window,
) -> tuple[RegionRow, ...]:
    """Every region, most flagged accounts first then most calls.

    Two windows, because there are two questions. Calls are counted over
    the window the screen asked for; `flagged` is metric 10, which
    `dashboard.yaml` defines over its own. Assessing the flag over the
    screen's period would restate the metric without saying so — **D11**, a
    period is not a window.
    """
    in_window = window.calls_in(tuple(calls))
    region_of = {employer.reference: employer.region for employer in employers}

    rows: dict[str, dict[str, int]] = {
        region: {"accounts": 0, "flagged": 0, "calls": 0, "unresolved": 0}
        for region in sorted(set(region_of.values()))
    }
    for employer in employers:
        row = rows[employer.region]
        row["accounts"] += 1
        if assess(config, employer, calls, risk_window).flagged:
            row["flagged"] += 1
    for call in in_window:
        region = region_of.get(call.employer_ref or "")
        if region is None:
            continue
        rows[region]["calls"] += 1
        if call.tags.outcome is Outcome.UNRESOLVED:
            rows[region]["unresolved"] += 1

    return tuple(
        sorted(
            (RegionRow(region=region, **counts) for region, counts in rows.items()),
            key=lambda row: (-row.flagged, -row.calls, row.region),
        )
    )


def broker_rows(
    config: DashboardConfig,
    brokers: Sequence[BrokerFacts],
    employers: Sequence[EmployerFacts],
    calls: Sequence[CallContext],
    window: Window,
    risk_window: Window,
) -> tuple[BrokerRow, ...]:
    """Every broker holding an account in scope, worst first.

    **No ranking floor.** `ranked_book_friction` keeps one, and is right
    to: it publishes a per-100-lives rate, and a three-group agency can top
    a rate table on a single call. This table publishes counts and no rate
    at all, so the floor would only hide the finding the pattern test
    exists to make — three adverse mentions across two employers, which a
    small broker can reach as readily as a large one.

    Ordered by adverse mentions, then flagged accounts, then calls: the
    prototype's own order, and it puts the channel question first.
    """
    in_window = window.calls_in(tuple(calls))
    mine = {broker.reference: [] for broker in brokers}  # type: dict[str, list[EmployerFacts]]
    for employer in employers:
        if employer.broker_ref in mine:
            mine[employer.broker_ref].append(employer)

    rows: list[BrokerRow] = []
    for broker in brokers:
        book = mine[broker.reference]
        if not book:
            continue
        pattern = pattern_test(config, broker.reference, calls, window)
        adverse = adverse_mentions(broker.reference, in_window, window)
        rows.append(
            BrokerRow(
                broker_ref=broker.reference,
                agency=broker.agency,
                name=broker.name,
                region=broker.region,
                groups_in_book=broker.groups_in_book,
                calls=sum(1 for call in in_window if call.broker_of_record_ref == broker.reference),
                adverse_mentions=len(adverse),
                adverse_employers=len(
                    {call.employer_ref for call in adverse if call.employer_ref is not None}
                ),
                pattern_fires=pattern.fires,
                pattern_reached=pattern.reached(config),
                flagged_accounts=sum(
                    1 for employer in book if assess(config, employer, calls, risk_window).flagged
                ),
            )
        )

    return tuple(
        sorted(
            rows,
            key=lambda row: (
                -row.adverse_mentions,
                -row.flagged_accounts,
                -row.calls,
                row.broker_ref,
            ),
        )
    )


@dataclass(frozen=True)
class ComplaintOwnership:
    """How many of the complaints made are about us.

    Two counts and not a share. The denominator is complaints, not calls,
    which makes this a different figure from `complaint_attributed_to_choice`
    — that one asks how often a caller complained about us out of everyone
    who rang, and this asks how much of the complaint load is ours to fix.
    Both are true and they are not interchangeable.

    `total` less `ours` is always some other party's — a carrier, a broker,
    an employer — and never an unattributed remainder: `Complaint` refuses
    to exist present and unattributed, so there is no third bucket for a
    reader of these two numbers to wonder about.
    """

    ours: int
    total: int


def complaint_ownership(calls: Sequence[CallContext], window: Window) -> ComplaintOwnership:
    """Complaints about us, against complaints made."""
    complaints = [
        call
        for call in window.calls_in(tuple(calls))
        if call.tags.complaint is not None and call.tags.complaint.present
    ]
    ours = sum(
        1
        for call in complaints
        if call.tags.complaint is not None
        and call.tags.complaint.attributed_to is ComplaintAttribution.CHOICE
    )
    return ComplaintOwnership(ours=ours, total=len(complaints))
