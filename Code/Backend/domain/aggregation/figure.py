"""What every aggregation returns: a number that carries its own standing.

§9's practices say this four times over, in four different ways — epistemic
class on every panel, withheld is not zero, every figure opens its evidence,
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

## A note on `EpistemicClass`, which is not from the workbook

The plan requires "epistemic class" on every response and never says what
its values are; neither does the workbook, nor the prototype. (The
prototype's `confidence` chip is the *rule's* grade — VERIFIED / SECONDARY /
UNVERIFIED, already modelled as `RuleConfidence` — which is a different
thing about a different object.)

The three values here are inferred from what the sources do say, not
invented freely:

- `WITHHELD` is used throughout §9 and has its own panel type.
- `DERIVED` is required by name: member effort and complexity are "our
  composites, not v9 fields" and "must be labelled as derived wherever they
  surface".
- `MEASURED` is what is left — computed straight from tagged fields.

**This needs Minnie's confirmation before the screens are built on it.** It
is the one piece of vocabulary in this layer with no source behind it, and
if it is wrong the fix is this enum and its call sites, not the figures.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from domain.dashboard_config import MetricThreshold


class EpistemicClass(str, Enum):
    #: Computed from the Call Tag Schema's own fields, at or above min n.
    MEASURED = "MEASURED"
    #: Our composite, not a v9 field. Labelled as such wherever it surfaces.
    DERIVED = "DERIVED"
    #: Suppressed. Never zero, and always with a reason.
    WITHHELD = "WITHHELD"


class WithheldReason(str, Enum):
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
    epistemic: EpistemicClass
    withheld_reason: WithheldReason | None = None
    caveats: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        withheld = self.epistemic is EpistemicClass.WITHHELD
        if withheld and self.value is not None:
            raise ValueError(
                "A withheld figure must not carry a value — zero reads as good news "
                "where the truth is absence of evidence."
            )
        if withheld and self.withheld_reason is None:
            raise ValueError("A withheld figure must say why it is withheld.")
        if not withheld and self.withheld_reason is not None:
            raise ValueError("A published figure must not carry a withheld reason.")
        if self.n < 0:
            raise ValueError("n cannot be negative.")
        if len(self.call_ids) != self.n:
            raise ValueError(
                f"n is {self.n} but {len(self.call_ids)} call id(s) were given — "
                "every figure opens its evidence, so the two cannot disagree."
            )

    @property
    def published(self) -> bool:
        return self.epistemic is not EpistemicClass.WITHHELD

    @classmethod
    def measured(
        cls,
        value: float,
        call_ids: tuple[str, ...],
        *,
        caveats: tuple[str, ...] = (),
    ) -> Figure:
        return cls(
            value=value,
            n=len(call_ids),
            call_ids=call_ids,
            epistemic=EpistemicClass.MEASURED,
            caveats=caveats,
        )

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
            epistemic=EpistemicClass.DERIVED,
            caveats=caveats,
        )

    @classmethod
    def withheld(
        cls,
        reason: WithheldReason,
        call_ids: tuple[str, ...] = (),
        *,
        caveats: tuple[str, ...] = (),
    ) -> Figure:
        """Suppressed, with its evidence still attached.

        The call ids survive suppression on purpose: a reader who is told
        four calls is too few to publish a rate should still be able to open
        those four calls.
        """
        return cls(
            value=None,
            n=len(call_ids),
            call_ids=call_ids,
            epistemic=EpistemicClass.WITHHELD,
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
        if threshold.withheld(sample):
            return cls.withheld(
                WithheldReason.BELOW_MIN_N,
                call_ids,
                caveats=(below_min_n_caveat(threshold, sample),),
            )
        published = cls.derived if derived else cls.measured
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
