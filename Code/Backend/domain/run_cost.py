"""What a run cost, rolled up from its items.

§8 Phase 5 asks the diagnostics for "token cost of the last run". This is
that number, and the reason it is a type rather than a sum is the word
*floor*.

Computed from the items rather than stored on the run. A stored roll-up is a
second copy of a number, and second copies drift — a resumed run, a retried
item or a backfill each give it a chance to disagree with the items beneath
it, and nothing would say which was right. Recomputing costs a sum over a
hundred rows.

**A total is a floor whenever any item's usage went unreported.** Some
providers do not return usage; the tokens were still spent. `TokenUsage`
carries that through addition, and `RunCost.complete` exposes it so a
diagnostics page can say "at least" rather than stating a number it cannot
stand behind. Reporting the floor as the cost is the same class of mistake
as reporting a withheld figure as zero.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from domain.value_objects.token_usage import TokenUsage


@dataclass(frozen=True)
class RunCost:
    """One run's tokens and wall-clock time."""

    usage: TokenUsage
    #: Items that contributed a usage figure at all — not the run's item
    #: count, because a pending or cancelled item never ran.
    items: int
    #: Items whose provider did not report usage. Above zero, the total is
    #: a floor.
    unreported_items: int
    #: Summed wall-clock milliseconds, over the items that recorded one.
    duration_ms: float

    @property
    def complete(self) -> bool:
        """Whether every item that ran reported what it used."""
        return self.unreported_items == 0 and self.usage.reported

    @property
    def summary(self) -> str:
        """The cost as a page should state it, computed from the numbers.

        Says "at least" whenever the total is a floor. A reader who is shown
        a precise-looking number for a run half of whose providers reported
        nothing has been misled by the format, not by the figure.
        """
        if self.items == 0:
            return "No item in this run recorded a token cost."
        tokens = f"{self.usage.total_tokens:,} tokens"
        prefix = "" if self.complete else "At least "
        floor = (
            ""
            if self.complete
            else f" — {self.unreported_items} of {self.items} item(s) ran against a "
            "provider that did not report usage, so this is a floor."
        )
        return (
            f"{prefix}{tokens} across {self.items} call(s) "
            f"({self.usage.input_tokens:,} in, {self.usage.output_tokens:,} out)"
            f"{floor}"
        )


def run_cost(usages: Sequence[TokenUsage], durations: Iterable[float | None] = ()) -> RunCost:
    """Roll a run's item usages up.

    Items that never ran are the caller's to exclude: a pending item has no
    usage to add and counting it would drag the per-call average down for a
    run that simply has not finished.
    """
    total = TokenUsage.total(usages)
    return RunCost(
        usage=total,
        items=len(usages),
        unreported_items=sum(1 for usage in usages if not usage.reported),
        duration_ms=sum(duration for duration in durations if duration is not None),
    )
