"""What every aggregation returns: a number that carries its own standing.

§9's practices say this four times over, in four different ways — a stated
basis on every figure, withheld is not zero, every figure opens its evidence,
caveats computed from the numbers rather than written by hand. All four are
properties of a *figure*, so they live on one object that every aggregation
returns, instead of being re-honoured nine times in nine slightly different
ways.

The invariants below are enforced in `__post_init__` rather than documented,
because each one is a mistake that produces a plausible-looking number:

- A withheld figure has no value. Rendering a suppressed figure as 0 is the
  single most damaging thing this layer could do — zero reads as good news
  where the truth is that nobody has enough evidence to say anything. So
  `WITHHELD` and a value are structurally impossible.
- A withheld figure says why. "Not shown" with no reason is indistinguishable
  from a bug, and the three reasons mean genuinely different things to a
  reader: too few calls, no such field in the workbook, or not eligible.
- A figure carries the ids of the calls behind it. Not for provenance in the
  abstract — §9 requires every figure to open its evidence, and a figure that
  cannot produce its calls cannot be argued with.

## `Basis` — where a number came from, and only that (D13)

`Basis` answers one question: **where did this number come from?** It does
not say whether the number is published. Those are different facts about a
figure, and holding them in one enum put the reason for suppression in two
places and the full reason in neither.

So suppression lives on `withheld_reason` alone, and `published` is derived
from it. `WITHHELD` is no longer a basis, because "we are not showing this"
is not an origin.

The three values, and why these three:

- `OBSERVED` — counted from the Call Tag Schema's own fields. Renamed from
  `MEASURED`, which is a word no reader uses and the prototype never used.
- `DERIVED` — our composite, not a v9 field. Required by name: member effort
  and complexity "must be labelled as derived wherever they surface".
- `REFERENCE` — an account fact from the workbook rather than from a call.

**`REFERENCE` has no producer in this codebase yet, and that is deliberate.**
Every `Figure` today is computed from calls, sometimes over a reference
denominator such as enrolled lives; the pure account facts (`enrolled`,
`annual_premium`, `renewal_month`) reach the wire as plain fields that carry
no basis at all. The value is defined now because D13 is *the* breaking
release for this vocabulary, and adding a case to an enum later breaks every
exhaustive client switch a second time. It is here to be used when an account
fact is first published as a figure — not as decoration.

## What is deliberately *not* here

`PATTERN`, `INFERENCE` and `RECOMMENDATION`. The prototype wears those on a
**panel header**, above a block of prose, and a panel tagged `inference`
holds no figure at all — it holds a sentence. They describe what a claim
asserts, not where a number came from, and no response carries narrative
today. D13 keeps them in frontend panel copy. (`RuleConfidence` is a third
thing again: the *rule's* provenance grade, about a different object.)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from domain.dashboard_config import MetricThreshold


class Basis(StrEnum):
    """Where a number came from. Never whether it is shown."""

    #: Counted from the Call Tag Schema's own fields.
    OBSERVED = "OBSERVED"
    #: Our composite, not a v9 field. Labelled as such wherever it surfaces.
    DERIVED = "DERIVED"
    #: An account fact from the workbook, not counted from a call. No
    #: producer yet — see the module docstring.
    REFERENCE = "REFERENCE"


class WithheldReason(StrEnum):
    #: Fewer than the metric's own min n. The commonest case, and the one
    #: that resolves itself as the corpus grows.
    BELOW_MIN_N = "BELOW_MIN_N"
    #: The workbook has no field for it, so no amount of data unlocks it —
    #: insights 6, 17 and 25 render withheld panels on exactly this basis.
    #: Distinct from BELOW_MIN_N because the panel has to say something
    #: different: "this needs a schema change", not "this needs more calls".
    NO_FIELD = "NO_FIELD"
    #: Below the eligibility floor rather than the quoting floor — metric
    #: 10's employers with under 3 calls. NOT the same as "not at risk".
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    #: Decision D4: `cost_per_call` is unknown and finance owns it, so every
    #: money figure renders withheld rather than with a placeholder.
    MONEY_UNKNOWN = "MONEY_UNKNOWN"
    #: There is nothing to divide by — an employer with no enrolled lives
    #: recorded, or a window in which no call qualifies for the denominator.
    #: Distinct from BELOW_MIN_N, which has a denominator and finds it too
    #: small: here the rate is undefined rather than unreliable, and the page
    #: has to say the population is missing rather than that the sample is.
    NO_DENOMINATOR = "NO_DENOMINATOR"


@dataclass(frozen=True)
class Figure:
    """One number, its evidence, and what may honestly be said about it."""

    value: float | None
    n: int
    call_ids: tuple[str, ...]
    #: Where the number came from. `None` only on a withheld figure whose
    #: origin is genuinely nothing — NO_FIELD, where the workbook has no
    #: such field, so there is no source to name. A figure withheld below
    #: min n keeps its basis: "our composite, too few calls to publish" is
    #: a more useful thing to render than "withheld".
    basis: Basis | None
    withheld_reason: WithheldReason | None = None
    caveats: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        withheld = self.withheld_reason is not None
        if not withheld and self.basis is None:
            raise ValueError(
                "A published figure must say where it came from — a number on screen "
                "with no stated origin is the thing `basis` exists to prevent."
            )
        if withheld and self.value is not None:
            raise ValueError(
                "A withheld figure must not carry a value — zero reads as good news "
                "where the truth is absence of evidence."
            )
        if self.n < 0:
            raise ValueError("n cannot be negative.")
        if len(self.call_ids) != self.n:
            raise ValueError(
                f"n is {self.n} but {len(self.call_ids)} call id(s) were given — "
                "every figure opens its evidence, so the two cannot disagree."
            )

    @property
    def published(self) -> bool:
        """Suppression lives in one place, and this reads it.

        `withheld_reason` is the single fact; this is a view of it. There is
        no second field to disagree with, which is what D13 bought.
        """
        return self.withheld_reason is None

    @classmethod
    def observed(
        cls,
        value: float,
        call_ids: tuple[str, ...],
        *,
        caveats: tuple[str, ...] = (),
    ) -> Figure:
        """Counted from the calls. Was `measured` before D13."""
        return cls(
            value=value,
            n=len(call_ids),
            call_ids=call_ids,
            basis=Basis.OBSERVED,
            caveats=caveats,
        )

    @classmethod
    def reference(
        cls,
        value: float,
        *,
        caveats: tuple[str, ...] = (),
    ) -> Figure:
        """An account fact from the workbook, not counted from any call.

        No `call_ids`, and that is the point rather than an omission: there
        are no calls behind a renewal date. `n` is 0, which for this basis
        means "not a sample" rather than "no evidence" — a reader must not
        see it gated against a min n it was never a sample for.
        """
        return cls(value=value, n=0, call_ids=(), basis=Basis.REFERENCE, caveats=caveats)

    @classmethod
    def derived(
        cls,
        value: float,
        call_ids: tuple[str, ...],
        *,
        caveats: tuple[str, ...] = (),
    ) -> Figure:
        """Our composite rather than a workbook field. Labelled, always."""
        return cls(
            value=value,
            n=len(call_ids),
            call_ids=call_ids,
            basis=Basis.DERIVED,
            caveats=caveats,
        )

    @classmethod
    def withheld(
        cls,
        reason: WithheldReason,
        call_ids: tuple[str, ...] = (),
        *,
        basis: Basis | None = None,
        caveats: tuple[str, ...] = (),
    ) -> Figure:
        """Suppressed, with its evidence still attached.

        The call ids survive suppression on purpose: a reader who is told
        four calls is too few to publish a rate should still be able to open
        those four calls.

        `basis` survives too, where there is one. A composite withheld below
        min n is still our composite, and saying so is more use than
        "withheld" alone. It stays `None` for `NO_FIELD`, where the workbook
        has no such field and there is no origin to name.
        """
        return cls(
            value=None,
            n=len(call_ids),
            call_ids=call_ids,
            basis=basis,
            withheld_reason=reason,
            caveats=caveats,
        )

    @classmethod
    def gated(
        cls,
        threshold: MetricThreshold,
        value: float,
        call_ids: tuple[str, ...],
        *,
        n: int | None = None,
        derived: bool = False,
    ) -> Figure:
        """Publish or withhold, by the metric's own min n.

        The single place the Metrics sheet's thresholds are applied. Nine
        aggregations each writing `if len(calls) < 30` is nine chances to
        use the wrong number, the wrong comparison, or the wrong n.

        `n` overrides the count of call ids for the metrics whose sample is
        not calls. Escalation integrity's min n is 30 *triggers*: the figure
        still opens onto every call behind it, but the gate is applied to
        the triggers, which at batch-1 volume is 11 where the calls are 100.
        Getting that backwards turns a real gate into one that always passes.
        """
        sample = len(call_ids) if n is None else n
        basis = Basis.DERIVED if derived else Basis.OBSERVED
        if threshold.withheld(sample):
            return cls.withheld(
                WithheldReason.BELOW_MIN_N,
                call_ids,
                # The gate knows the basis whether or not it publishes, so it
                # passes it through. Dropping it here would make a withheld
                # composite indistinguishable from a withheld count.
                basis=basis,
                caveats=(below_min_n_caveat(threshold, sample),),
            )
        published = cls.derived if derived else cls.observed
        return published(value, call_ids)


def below_min_n_caveat(threshold: MetricThreshold, n: int) -> str:
    """The caveat text for a suppressed figure, computed from the numbers.

    §9: "Caveat text generated from the numbers, never hand-written." A
    hand-written caveat is a number in prose, and prose does not get
    recalculated when the window moves.
    """
    return (
        f"Withheld: {n} {threshold.counts} against a minimum of "
        f"{threshold.min_n} for {threshold.name.lower()}."
    )


def no_field_caveat(question: str, needed: str) -> str:
    """The withheld panel for a question the workbook cannot answer.

    Insights 6, 17 and 25. §8 asks these panels to state the question, why it
    cannot be answered, and exactly what data would unlock it — the last part
    being what distinguishes a considered gap from an oversight.
    """
    return f"Withheld: {question} cannot be answered from the v9 schema. It needs {needed}."
