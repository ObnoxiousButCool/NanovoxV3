"""Which of the ten indicators drive the risk, across the whole book.

`Prototype/v2/index.html`'s "Which problems drive the risk": each driver is
one indicator family counted **in calls**, ranked, with what it most often
turns up alongside and whether it is moving.

## The same ten families, read the other way round

`indicators.observe()` answers "how does this family stand for *this
employer*". This answers "how much of the book does this family account
for". Same `FAMILIES` tuple, deliberately — a second list of indicators
would be a second definition of the risk flag's inputs, and the two would
part company the first time one was edited.

## The change is a noise test, not a delta chip

The prototype prints a percentage change between the first four weeks and
the last four. At this corpus's volume that manufactures findings: two calls
becoming four is "+100%" and is also a coin flip.

So the comparison goes through `trends.movement`, which scales the earlier
count by how busy each period was and reports `beyond_noise`. A screen shows
the direction only when that is true, and the counts either way. This is the
same treatment the exec page's movements already get, for the same reason.

## Three ways a family has no number, and they differ

- **Not computable.** `high_effort` needs a field v9 does not carry. It is
  reported with its reason and never as zero.
- **Computable, zero calls.** A real answer: nobody raised it.
- **Too short a window to compare.** The count stands; the change does not.
  Splitting an eight-week window into "first four and last four" is honest;
  splitting a three-week one is not.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from domain.aggregation.call_tags import CallContext, Window
from domain.aggregation.indicators import FAMILIES, Family
from domain.aggregation.repeat_contact import failure_driven_repeats
from domain.aggregation.trends import Movement, movement, slice_window
from domain.value_objects.category import Category

#: The window is split into this many equal parts and the last is compared
#: with the first — the prototype's "latest four weeks against the first
#: four across the whole quarter", expressed as a ratio so it survives a
#: change to the risk window's length.
_PARTS = 3

#: Below this many weeks the split is not worth making.
_MIN_WEEKS_TO_COMPARE = 6.0


@dataclass(frozen=True)
class Driver:
    """One indicator family's standing across the book."""

    family: Family
    call_ids: tuple[str, ...]
    #: What these calls were most often about, and where they most often
    #: landed. Context for the driver, never a second measurement of it.
    top_category: Category | None
    top_touchpoint: str | None
    #: `None` when the window is too short to split, or the family cannot be
    #: computed at all. Absent is not "no change".
    change: Movement | None

    @property
    def calls(self) -> int:
        return len(self.call_ids)


def _in(references: frozenset[str] | set[str]) -> Callable[[CallContext], bool]:
    """A membership test shaped like a family's own predicate.

    Repeat contact is derived by pairing a caller's calls rather than read
    off one, so its set is computed once and then queried like any other
    family's test — which is what lets `movement` treat all ten alike.
    """

    def measure(call: CallContext) -> bool:
        return call.reference in references

    return measure


def _commonest(values: Sequence[str]) -> str | None:
    """The most frequent value, ties broken by name so it is stable."""
    if not values:
        return None
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return sorted(counts.items(), key=lambda entry: (-entry[1], entry[0]))[0][0]


def risk_drivers(calls: Sequence[CallContext], window: Window) -> tuple[Driver, ...]:
    """Every family, most calls first. Includes the ones at zero.

    Unlike the account topic ranking, a family with no calls is kept: these
    ten are a fixed list the risk flag is built from, so "nobody raised
    this" is a finding about the book rather than noise in a long tail.
    """
    in_window = window.calls_in(tuple(calls))
    parts = slice_window(window, _PARTS)
    comparable = window.weeks >= _MIN_WEEKS_TO_COMPARE and len(parts) == _PARTS

    # Repeat contact has no per-call predicate — it is derived by pairing a
    # caller's calls — so its membership is computed once and then read like
    # any other family's test.
    repeat_refs = {call.reference for call in failure_driven_repeats(in_window)}

    drivers: list[Driver] = []
    for family in FAMILIES:
        if not family.computable:
            drivers.append(
                Driver(
                    family=family,
                    call_ids=(),
                    top_category=None,
                    top_touchpoint=None,
                    change=None,
                )
            )
            continue

        measure = family.matches if family.matches is not None else _in(repeat_refs)

        matched = [call for call in in_window if measure(call)]
        drivers.append(
            Driver(
                family=family,
                call_ids=tuple(call.reference for call in matched),
                top_category=_top_category(matched),
                top_touchpoint=_commonest(
                    [call.tags.touchpoint for call in matched if call.tags.touchpoint]
                ),
                change=(
                    movement(
                        family.label,
                        now=parts[-1].calls_in(tuple(in_window)),
                        prior=parts[0].calls_in(tuple(in_window)),
                        measure=measure,
                    )
                    if comparable
                    else None
                ),
            )
        )

    # Most calls first; a family that cannot be computed sorts last rather
    # than among the zeros, because it is a different statement.
    return tuple(
        sorted(
            drivers,
            key=lambda driver: (not driver.family.computable, -driver.calls, driver.family.code),
        )
    )


def _top_category(calls: Sequence[CallContext]) -> Category | None:
    commonest = _commonest([call.tags.category.value for call in calls if call.tags.category])
    return Category(commonest) if commonest is not None else None
