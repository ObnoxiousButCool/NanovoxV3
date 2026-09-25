"""§9 insight 7 — broker-of-record drift.

> "Flag when the broker named aloud ≠ the employer's broker of record. A
> flag, not a ranking. Zero mismatches renders as a finding."

Two fields have carried this since extraction and nothing compared them:
`CallTags.broker_named_aloud.broker_ref` is who the caller said, and
`CallContext.broker_of_record_ref` is who reference data says. Where they
differ, somebody is working with the wrong broker — or reference data is
stale — and either is worth knowing.

## A flag, not a rate

No denominator, no ranking, no per-broker share. A mention is rare enough
at this volume that a rate would be two calls over three, and the sheet
asks for the flag rather than the ratio. `Drift` counts and names the
calls; nothing here divides.

## Zero mismatches is an answer, not an empty panel

`checked` and `mismatches` are separate on purpose. Zero mismatches out of
fourteen mentions is a real finding — the book agrees with itself — and
reads completely differently from zero mentions, where nobody named a
broker at all and there was nothing to check. A panel that rendered both as
blank would turn a clean result into a missing one.

## Absent is not a mismatch

A call whose **employer has no broker of record** is not counted as a
mismatch. One side of the comparison is unknown, and scoring an unknown as
a disagreement would manufacture drift out of a gap in reference data —
the failure most likely to look correct, because the two values genuinely
are not equal. Those calls are counted in `unresolved` and said out loud.

The other direction cannot happen: `BrokerNamedAloud.__post_init__`
refuses `present=True` without a `broker_ref`, so a present mention always
names somebody. The check below still covers it, because the type says
`str | None` and a guard that matches the type costs nothing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from domain.aggregation.call_tags import CallContext


@dataclass(frozen=True)
class Drift:
    """Insight 7 for one account, or for any set of calls."""

    #: Calls where a broker was named aloud **and** both sides resolved, so
    #: the comparison could actually be made.
    checked: int
    #: Calls where the named broker is not the broker of record.
    mismatches: tuple[str, ...]
    #: Calls where a broker was named but one side was unknown. Counted
    #: apart: an unknown is not a disagreement.
    unresolved: tuple[str, ...]

    @property
    def flagged(self) -> bool:
        return bool(self.mismatches)

    @property
    def finding(self) -> str:
        """The sentence the panel shows, including when nothing is wrong."""
        if self.checked == 0 and not self.unresolved:
            return (
                "No caller named a broker in this window, so there was nothing to "
                "check. Not the same as the book agreeing with itself."
            )
        caveat = (
            ""
            if not self.unresolved
            else (
                f" {len(self.unresolved)} further mention(s) could not be checked "
                "because one side was not resolved; they are not counted as drift."
            )
        )
        if not self.mismatches:
            return (
                f"No drift: all {self.checked} broker mention(s) matched the broker of "
                f"record.{caveat}"
            )
        return (
            f"Drift on {len(self.mismatches)} of {self.checked} broker mention(s): the "
            f"caller named a broker that is not the broker of record.{caveat}"
        )


def drift(calls: Sequence[CallContext]) -> Drift:
    """Compare who was named against who is on record."""
    mismatches: list[str] = []
    unresolved: list[str] = []
    checked = 0
    for call in calls:
        named = call.tags.broker_named_aloud
        if named is None or not named.present:
            continue
        on_record = call.broker_of_record_ref
        if named.broker_ref is None or on_record is None:
            unresolved.append(call.reference)
            continue
        checked += 1
        if named.broker_ref != on_record:
            mismatches.append(call.reference)
    return Drift(
        checked=checked,
        mismatches=tuple(sorted(mismatches)),
        unresolved=tuple(sorted(unresolved)),
    )
