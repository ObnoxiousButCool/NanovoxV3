"""Comparing one field, on one call, between the pipeline and the answer key.

Phase 5's foundation. Four comparison kinds, named by §8 Phase 5: exact
match for enums, set overlap for lists, rule-id match for knowledge failure,
and attribution-target match for `complaint.attributed_to`.

Pure value comparison. Nothing here reads a database, a run or the answer
key itself — it is handed two values and says whether they agree. That is
what lets E4's harness stay the only module in this phase that touches
answer-key material.

## The three verdicts, and why two of them are not "wrong"

§8 asks for agreement; this returns **agreed, disagreed and not
comparable**, because collapsing the third into either of the others
produces a number that is confidently false.

- Folding *not comparable* into **disagreed** understates the pipeline on
  every field the Transcript Tracker leaves blank — which is most fields on
  most calls, since the tracker records what happened rather than filling in
  every column.
- Folding it into **agreed** is worse and is the failure this module is most
  careful about: a pipeline that produced nothing at all would have no
  disagreements and would score 100%. See `Agreement.coverage` in
  `agreement.py` — the rate is never reported without it.

So `NotComparable` carries *which side was missing*. "The tracker never said"
and "the pipeline did not answer" are different findings with different
owners: the first is a limit of the answer key, the second is a layer that
failed or never ran, and §7 is explicit that an L3/L4 failure is recorded as
unavailable with a reason rather than as a blank.
"""

from __future__ import annotations

from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from enum import Enum, StrEnum


class Verdict(StrEnum):
    AGREED = "AGREED"
    DISAGREED = "DISAGREED"
    NOT_COMPARABLE = "NOT_COMPARABLE"


class MissingSide(StrEnum):
    """Which side had nothing to compare. Never both-and-agreed."""

    #: The tracker does not record this field for this call. A limit of the
    #: answer key, and nothing the pipeline can be credited or blamed for.
    ANSWER_KEY = "ANSWER_KEY"
    #: The pipeline produced no value — the layer failed, was skipped, or
    #: never ran. Counted separately because a silent pipeline must not read
    #: as a correct one.
    PIPELINE = "PIPELINE"
    #: Neither side has a value, which is itself an agreement about absence
    #: for a presence-shaped field, and nothing at all for the rest.
    BOTH = "BOTH"


@dataclass(frozen=True)
class Comparison:
    """One field, on one call."""

    field: str
    verdict: Verdict
    #: What the answer key said, rendered for a report. `None` when absent.
    expected: str | None = None
    #: What the pipeline said. `None` when absent.
    actual: str | None = None
    missing: MissingSide | None = None

    def __post_init__(self) -> None:
        comparable = self.verdict is not Verdict.NOT_COMPARABLE
        if comparable and self.missing is not None:
            raise ValueError("A comparable field cannot also record a missing side.")
        if not comparable and self.missing is None:
            raise ValueError(
                "An incomparable field must say which side was missing — "
                "'the tracker never said' and 'the pipeline did not answer' are "
                "different findings."
            )

    @property
    def comparable(self) -> bool:
        return self.verdict is not Verdict.NOT_COMPARABLE


@dataclass(frozen=True)
class SetComparison:
    """One list-valued field, on one call — signals, control exceptions, intents.

    Precision and recall are kept apart and never blended into one score.
    The Signal Taxonomy's own framing is why: a pipeline that finds half the
    signals and invents none is a different problem from one that finds them
    all and invents four. The first is a recall problem in the prompt; the
    second is a precision problem in the schema or the validation. One
    number hides which, and they are fixed differently.
    """

    field: str
    expected: frozenset[str]
    actual: frozenset[str]
    missing: MissingSide | None = None

    @property
    def matched(self) -> frozenset[str]:
        return self.expected & self.actual

    @property
    def missed(self) -> frozenset[str]:
        """In the answer key, not in the pipeline's output."""
        return self.expected - self.actual

    @property
    def spurious(self) -> frozenset[str]:
        """In the pipeline's output, not in the answer key."""
        return self.actual - self.expected

    @property
    def precision(self) -> float | None:
        """Of what the pipeline claimed, how much was right.

        `None` when it claimed nothing — undefined, not zero. A call with no
        signals extracted has no precision, and scoring it 0 would punish
        the pipeline for a call that genuinely had none.
        """
        return len(self.matched) / len(self.actual) if self.actual else None

    @property
    def recall(self) -> float | None:
        """Of what was there, how much the pipeline found. `None` when the
        answer key lists nothing.
        """
        return len(self.matched) / len(self.expected) if self.expected else None

    @property
    def verdict(self) -> Verdict:
        if self.missing is not None:
            return Verdict.NOT_COMPARABLE
        if not self.expected and not self.actual:
            return Verdict.AGREED
        return Verdict.AGREED if self.expected == self.actual else Verdict.DISAGREED


def compare_exact(field: str, expected: object | None, actual: object | None) -> Comparison:
    """Exact match — outcome, category, touchpoint, and the booleans.

    Enum members compare by identity of value, so `Outcome.RESOLVED` and the
    string "RESOLVED" agree. That is deliberate: the answer key stores some
    of these as parsed enums and some as the workbook's own strings, and a
    comparison that failed on the representation would report a disagreement
    about nothing.
    """
    if expected is None and actual is None:
        return Comparison(field=field, verdict=Verdict.NOT_COMPARABLE, missing=MissingSide.BOTH)
    if expected is None:
        return Comparison(
            field=field,
            verdict=Verdict.NOT_COMPARABLE,
            actual=_render(actual),
            missing=MissingSide.ANSWER_KEY,
        )
    if actual is None:
        return Comparison(
            field=field,
            verdict=Verdict.NOT_COMPARABLE,
            expected=_render(expected),
            missing=MissingSide.PIPELINE,
        )
    agreed = _render(expected) == _render(actual)
    return Comparison(
        field=field,
        verdict=Verdict.AGREED if agreed else Verdict.DISAGREED,
        expected=_render(expected),
        actual=_render(actual),
    )


def compare_set(
    field: str,
    expected: AbstractSet[str] | None,
    actual: AbstractSet[str] | None,
) -> SetComparison:
    """Set overlap — signals, control exceptions, intent types.

    An empty set is a real answer ("this call raised no signals") and is
    compared. `None` means the side has nothing to say at all, which is not
    the same thing and is not comparable.
    """
    missing = _missing_side(expected, actual)
    return SetComparison(
        field=field,
        expected=frozenset(expected or ()),
        actual=frozenset(actual or ()),
        missing=missing,
    )


def compare_presence_and_detail(
    field: str,
    *,
    expected_present: bool | None,
    actual_present: bool | None,
    expected_detail: object | None,
    actual_detail: object | None,
) -> tuple[Comparison, Comparison]:
    """Presence first, then the detail — but only where both sides agree it happened.

    This is the shape behind two of §8's four named comparisons:

    - **rule-id match for knowledge failure**: did a knowledge failure occur,
      and if so was it the same rule? Metric 8's output is a ranked list of
      articles to rewrite, so getting the presence right and the rule wrong
      is a real failure with a real consequence, and it has to be visible
      separately from getting the presence wrong.
    - **attribution-target match for complaint**: was there a complaint, and
      if so who was it attributed to?

    Returned as two comparisons, never one. Collapsing them loses which half
    failed, and the two have different causes: presence is a classification
    problem, the detail is a lookup or citation problem.

    The detail is *not comparable* unless both sides say the thing happened
    — asking which rule was wrong on a call where the pipeline found no
    knowledge failure is asking about a value that should not exist.
    """
    presence = compare_exact(f"{field}.present", expected_present, actual_present)
    both_present = expected_present is True and actual_present is True
    if not both_present:
        detail = Comparison(
            field=f"{field}.detail",
            verdict=Verdict.NOT_COMPARABLE,
            expected=_render(expected_detail),
            actual=_render(actual_detail),
            missing=_missing_side(expected_detail, actual_detail) or MissingSide.BOTH,
        )
        return presence, detail
    return presence, compare_exact(f"{field}.detail", expected_detail, actual_detail)


def _missing_side(expected: object | None, actual: object | None) -> MissingSide | None:
    if expected is None and actual is None:
        return MissingSide.BOTH
    if expected is None:
        return MissingSide.ANSWER_KEY
    if actual is None:
        return MissingSide.PIPELINE
    return None


def _render(value: object | None) -> str | None:
    """A value as a report shows it, with enums reduced to their own value."""
    if value is None:
        return None
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)
