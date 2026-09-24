"""Rolling per-call comparisons up into a number someone will quote.

One field across many calls, and one layer across many fields. §8 asks the
diagnostics for agreement "per field, per layer", and per layer is the half
that says what to fix: L2 disagreeing is a classification-prompt problem and
L4 disagreeing is a signal-taxonomy problem, and a flat per-field list does
not separate them.

## Agreement is never reported without coverage

This is the one rule the module exists to enforce. Agreement is computed
over the *comparable* calls, so a field the pipeline answered twice and got
right twice reads as 100% — and it is 100%, of two calls out of a hundred.

`Agreement.rate` and `Agreement.coverage` are therefore both required to
describe the field, and `summary()` renders them together so no caller has
to remember. A pipeline that produced nothing at all scores an agreement
rate of `None` and a coverage of zero, which is the honest description of
it; the shape that must never appear is a confident rate with no denominator
beside it.

The same reasoning as `Figure` in `domain/aggregation/figure.py`: a figure
that cannot state what it rests on is not a figure.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from domain.evaluation.comparison import Comparison, MissingSide, SetComparison, Verdict


@dataclass(frozen=True)
class Agreement:
    """One field's agreement across a set of calls."""

    field: str
    agreed: int
    disagreed: int
    #: The tracker does not record this field on these calls. A limit of the
    #: answer key; the pipeline is neither credited nor blamed.
    no_answer_key: int
    #: The pipeline produced no value. A failed or skipped layer, and the
    #: number that stops a silent pipeline reading as a correct one.
    no_pipeline_value: int
    #: Neither side had anything to say.
    neither: int

    @property
    def comparable(self) -> int:
        return self.agreed + self.disagreed

    @property
    def calls(self) -> int:
        return self.comparable + self.no_answer_key + self.no_pipeline_value + self.neither

    @property
    def rate(self) -> float | None:
        """Agreed over comparable. `None` when nothing was comparable.

        `None` rather than 0.0, for the same reason a withheld figure is not
        zero: no comparison having been possible is not the same as every
        comparison having failed.
        """
        return self.agreed / self.comparable if self.comparable else None

    @property
    def coverage(self) -> float:
        """Comparable over all calls — what `rate` actually rests on."""
        return self.comparable / self.calls if self.calls else 0.0

    @property
    def summary(self) -> str:
        """Both numbers, in one line, computed rather than written.

        Never the rate alone. An agreement of 100% on four of a hundred
        calls and one on ninety-eight are the same number and different
        findings, and whichever of the two a reader assumes will be the one
        that misleads them.
        """
        if self.rate is None:
            return (
                f"{self.field}: no comparison possible on any of {self.calls} call(s) "
                f"({self.no_pipeline_value} with no pipeline value, "
                f"{self.no_answer_key} with no answer key)."
            )
        return (
            f"{self.field}: {self.rate:.0%} agreement on {self.comparable} of "
            f"{self.calls} call(s) ({self.coverage:.0%} coverage); "
            f"{self.no_pipeline_value} with no pipeline value."
        )


def agreement_for(field: str, comparisons: Sequence[Comparison | SetComparison]) -> Agreement:
    """Roll one field's comparisons up.

    Takes both comparison shapes: a `SetComparison` reduces to agreed or
    disagreed on exact set equality, while its precision and recall stay
    available on the individual comparisons for the diagnostics that want
    them. Set equality is the right roll-up here precisely because it is
    strict — "the pipeline got this call's signals exactly right" is the
    claim a screen ends up making.
    """
    counts = dict.fromkeys(("agreed", "disagreed", "key", "pipeline", "neither"), 0)
    for comparison in comparisons:
        verdict = comparison.verdict
        if verdict is Verdict.AGREED:
            counts["agreed"] += 1
        elif verdict is Verdict.DISAGREED:
            counts["disagreed"] += 1
        elif comparison.missing is MissingSide.ANSWER_KEY:
            counts["key"] += 1
        elif comparison.missing is MissingSide.PIPELINE:
            counts["pipeline"] += 1
        else:
            counts["neither"] += 1

    return Agreement(
        field=field,
        agreed=counts["agreed"],
        disagreed=counts["disagreed"],
        no_answer_key=counts["key"],
        no_pipeline_value=counts["pipeline"],
        neither=counts["neither"],
    )


@dataclass(frozen=True)
class LayerAgreement:
    """Every field one extraction layer is responsible for.

    The layer is what a reader acts on. A per-field list says `touchpoint`
    is weak; the layer roll-up says L2 is weak, which is a prompt to rewrite
    rather than a column to distrust.
    """

    layer: str
    fields: tuple[Agreement, ...]

    @property
    def agreed(self) -> int:
        return sum(field.agreed for field in self.fields)

    @property
    def comparable(self) -> int:
        return sum(field.comparable for field in self.fields)

    @property
    def rate(self) -> float | None:
        return self.agreed / self.comparable if self.comparable else None

    @property
    def weakest(self) -> Agreement | None:
        """The field dragging the layer down, or `None` if nothing compared.

        Fields with nothing comparable are excluded rather than sorted to
        the bottom: a field with no comparisons is not the worst-performing
        one, it is an unanswered question, and naming it as the thing to fix
        sends someone to the wrong place.
        """
        rated = [field for field in self.fields if field.rate is not None]
        if not rated:
            return None
        return min(rated, key=lambda field: (field.rate or 0.0, field.field))
