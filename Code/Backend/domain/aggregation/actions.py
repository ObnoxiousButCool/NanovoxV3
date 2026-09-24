"""Group 8 — the action centre's read side (§9 insights 20 and 21).

Every signal raised in the window becomes an item: what was found, who it
routes to, how serious the taxonomy says it is, and the calls behind it.
Insight 21 — "items by the finding that produced them" — is the same data
grouped the other way, so both come from one aggregation rather than two
that could disagree about how many items exist.

## There are no statuses here, and that is not an omission

`actions.html` shows a lifecycle: a board with states, an owner, a
resolution. None of that exists yet. The write path is Phase 9 and decision
D6, and until it lands nobody has moved an item anywhere. Inventing a
default status — "open", "new" — would put a lifecycle claim on the wire
that no stored record supports, and the first person to filter the board by
status would be filtering on a constant.

So an item carries what the signal itself says and nothing more. When the
write path arrives it adds state to these items; it does not change what
they are.

## Severity and owner come from the taxonomy, never from here

The Signal Taxonomy sheet sets both, and calls the owner mandatory rather
than advisory: a compliance failure routes to Compliance and a knowledge
error to Knowledge Management, not to the call centre. `severity_of` and
`owner_team_of` read the sheet's columns, so a re-issued taxonomy moves the
routing without touching this module.

## Ordering is severity first, then weight

Worst severity first, and within a severity the item with more calls behind
it. Ordering by count alone would put twelve low-severity revenue
opportunities above one retention risk, which is the opposite of a list
meant to be worked top-down.

## Counts, not rates

An item has no denominator. "Three billing defects" is a count of findings,
and there is no population of calls that could have raised one — every call
could. A rate here would need a denominator nobody has defined, so there
is none.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from domain.aggregation.call_tags import CallContext, Window
from domain.value_objects.signal_severity import SignalSeverity
from domain.value_objects.signal_type import (
    SEVERITY_ORDER,
    SignalType,
    owner_team_of,
    severity_of,
)


@dataclass(frozen=True)
class ActionItem:
    """One finding, with who owns it and the calls that raised it."""

    signal: SignalType
    severity: SignalSeverity
    #: The Signal Taxonomy sheet's "Owner" column. Mandatory per the sheet.
    owner_team: str
    call_ids: tuple[str, ...]

    @property
    def calls(self) -> int:
        return len(self.call_ids)


@dataclass(frozen=True)
class OwnerWorkload:
    """One team's items, for the routing view.

    Carries the items rather than a count, because "Compliance has four" is
    not actionable and "Compliance has four, three of them critical" is.
    """

    owner_team: str
    items: tuple[ActionItem, ...]

    @property
    def calls(self) -> int:
        """Distinct calls behind this team's items.

        Distinct, because one call can raise several signals routing to the
        same team, and summing the items' counts would report more work than
        exists.
        """
        return len({ref for item in self.items for ref in item.call_ids})

    @property
    def critical(self) -> int:
        return sum(1 for item in self.items if item.severity is SignalSeverity.CRITICAL)


def action_items(calls: Sequence[CallContext], window: Window) -> tuple[ActionItem, ...]:
    """Every signal raised in the window, worst first.

    Signal types with nothing against them are absent rather than present at
    zero. That is the opposite of the indicator families on the risk screen,
    and deliberately so: a family there answers "was this checked", where an
    item here is a piece of work that exists. A zero-call action item would
    be a task nobody needs to do.
    """
    raised: dict[SignalType, list[str]] = {}
    for call in window.calls_in(tuple(calls)):
        for signal in call.tags.signals:
            raised.setdefault(signal, []).append(call.reference)

    items = [
        ActionItem(
            signal=signal,
            severity=severity_of(signal),
            owner_team=owner_team_of(signal),
            call_ids=tuple(sorted(references)),
        )
        for signal, references in raised.items()
    ]
    return tuple(sorted(items, key=_worst_first))


def by_owner(items: Sequence[ActionItem]) -> tuple[OwnerWorkload, ...]:
    """Insight 21's other cut: the same items, routed.

    Ordered by the team carrying the most critical items, then the most
    calls — the order someone deciding where to look first would want,
    rather than alphabetical.
    """
    grouped: dict[str, list[ActionItem]] = {}
    for item in items:
        grouped.setdefault(item.owner_team, []).append(item)

    workloads = [
        OwnerWorkload(owner_team=team, items=tuple(sorted(group, key=_worst_first)))
        for team, group in grouped.items()
    ]
    return tuple(sorted(workloads, key=lambda load: (-load.critical, -load.calls, load.owner_team)))


def _worst_first(item: ActionItem) -> tuple[int, int, str]:
    """Severity first, then weight, then a stable tiebreak.

    Twelve low-severity revenue opportunities above one retention risk is
    the wrong list for someone working top-down.
    """
    return (SEVERITY_ORDER.index(item.severity), -item.calls, item.signal.value)
