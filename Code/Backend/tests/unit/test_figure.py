"""The envelope every aggregation returns, and the four things it enforces.

These are not shape tests. Each invariant below corresponds to a way a
figure can be published that looks completely normal and is wrong, which is
why they raise rather than warn.
"""

from __future__ import annotations

import pytest

from domain.aggregation.figure import (
    Basis,
    Figure,
    WithheldReason,
    below_min_n_caveat,
    no_field_caveat,
)
from domain.dashboard_config import MetricThreshold

_CALLS = ("C-0001", "C-0002", "C-0003")


def _threshold(*, min_n: int | None = 30, counts: str = "calls") -> MetricThreshold:
    return MetricThreshold(
        key="contact_rate",
        sheet_row="1",
        name="Contact rate",
        window_weeks=12,
        min_n=min_n,
        counts=counts,
    )


# --- Withheld is not zero --------------------------------------------------


def test_a_withheld_figure_cannot_carry_a_value() -> None:
    """The single most damaging thing this layer could do.

    A suppressed figure rendered as 0 reads as good news — no complaints, no
    escalations missed — where the truth is that nobody has enough evidence
    to say anything at all.
    """
    with pytest.raises(ValueError, match="zero reads as good news"):
        Figure(
            value=0.0,
            n=3,
            call_ids=_CALLS,
            basis=Basis.OBSERVED,
            withheld_reason=WithheldReason.BELOW_MIN_N,
        )


def test_a_published_figure_must_say_where_it_came_from() -> None:
    """D13: a number on screen with no stated origin is what `basis` prevents.

    The mirror of the withheld-reason invariant. Before D13 this was
    unreachable — `epistemic` was required and WITHHELD lived inside it, so
    "published with nothing said about it" could not be expressed. Now that
    suppression is `withheld_reason` alone, it can be, so it is refused.
    """
    with pytest.raises(ValueError, match="must say where it came from"):
        Figure(value=1.0, n=0, call_ids=(), basis=None)


def test_suppression_is_one_field_and_published_reads_it() -> None:
    """There is no second field to disagree with. That is what D13 bought.

    `published` was a view of `epistemic`, and `withheld_reason` had to be
    kept consistent with it by two hand-written invariants. One fact now.
    """
    published = Figure(value=1.0, n=0, call_ids=(), basis=Basis.OBSERVED)
    withheld = Figure(
        value=None,
        n=0,
        call_ids=(),
        basis=Basis.OBSERVED,
        withheld_reason=WithheldReason.BELOW_MIN_N,
    )

    assert published.published is True
    assert withheld.published is False


def test_every_withheld_reason_means_something_different() -> None:
    """Not a tautology: these drive five different panels.

    Too few calls resolves itself as the corpus grows. No field never does —
    it needs a schema change. Not eligible is metric 10's employers under
    three calls, which is not "no risk". Money unknown is D4 and is a
    decision, not a data problem. No denominator means the rate is undefined
    rather than unreliable, which is a different sentence on the page.
    """
    assert len({reason.value for reason in WithheldReason}) == 5


# --- Every figure opens its evidence ---------------------------------------


def test_n_and_the_call_ids_cannot_disagree() -> None:
    with pytest.raises(ValueError, match="every figure opens its evidence"):
        Figure(value=1.0, n=10, call_ids=_CALLS, basis=Basis.OBSERVED)


def test_a_withheld_figure_keeps_its_evidence() -> None:
    """A reader told four calls is too few should still be able to open them."""
    figure = Figure.withheld(WithheldReason.BELOW_MIN_N, _CALLS)

    assert figure.call_ids == _CALLS
    assert figure.n == 3
    assert figure.published is False


def test_a_gated_composite_keeps_its_basis_when_withheld() -> None:
    """ "Our composite, too few calls" beats "withheld" on a panel.

    The gate knows the basis whether or not it publishes. Dropping it would
    make a withheld composite indistinguishable from a withheld count, and
    §9 insight 29 requires composites labelled *wherever* they surface —
    which includes the times they do not carry a number.
    """
    figure = Figure.gated(_threshold(), value=42.0, call_ids=_CALLS, derived=True)

    assert figure.published is False
    assert figure.basis is Basis.DERIVED


def test_a_figure_with_no_field_behind_it_names_no_basis() -> None:
    """Insights 6, 17 and 25: the workbook has no such field.

    There is no origin to state, so `basis` is null rather than a guess.
    This is the only case where a figure may decline to say where it came
    from, and it may because there is genuinely nothing there.
    """
    figure = Figure.withheld(WithheldReason.NO_FIELD)

    assert figure.basis is None
    assert figure.published is False


def test_a_reference_fact_is_not_a_sample() -> None:
    """There are no calls behind a renewal date, and n is not evidence here.

    `n == 0` on a REFERENCE figure means "not a sample", not "no evidence".
    A reader must not see it gated against a min n it was never a sample for.
    """
    figure = Figure.reference(1450.0)

    assert figure.basis is Basis.REFERENCE
    assert figure.published is True
    assert figure.n == 0
    assert figure.call_ids == ()


def test_a_negative_n_is_refused() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        Figure(value=None, n=-1, call_ids=(), basis=Basis.OBSERVED)


# --- Gating on the metric's own min n --------------------------------------


def test_a_sample_below_min_n_is_withheld() -> None:
    figure = Figure.gated(_threshold(), value=42.0, call_ids=_CALLS)

    assert figure.published is False
    assert figure.value is None
    assert figure.withheld_reason is WithheldReason.BELOW_MIN_N


def test_a_sample_at_min_n_is_published() -> None:
    calls = tuple(f"C-{i:04d}" for i in range(30))

    figure = Figure.gated(_threshold(), value=42.0, call_ids=calls)

    assert figure.published is True
    assert figure.value == pytest.approx(42.0)
    assert figure.basis is Basis.OBSERVED


def test_a_metric_with_no_min_n_is_never_gated() -> None:
    figure = Figure.gated(_threshold(min_n=None), value=7.0, call_ids=("C-0001",))

    assert figure.published is True


def test_the_sample_can_differ_from_the_call_count() -> None:
    """Escalation integrity's min n is 30 *triggers*, not 30 calls.

    The figure still opens onto every call behind it, but the gate applies
    to the triggers. At batch-1 volume that is 11 against 100 calls, so
    gating on the call count would publish a rate the sheet says to suppress
    — a real gate turned into one that always passes.
    """
    calls = tuple(f"C-{i:04d}" for i in range(100))
    triggers = _threshold(counts="triggers")

    figure = Figure.gated(triggers, value=0.64, call_ids=calls, n=11)

    assert figure.published is False
    assert figure.n == 100, "the evidence is still every call"
    assert "11 triggers" in figure.caveats[0]


def test_a_derived_figure_is_labelled_as_derived() -> None:
    """Member effort and complexity are our composites, not v9 fields, and
    must be labelled wherever they surface.
    """
    calls = tuple(f"C-{i:04d}" for i in range(30))

    figure = Figure.gated(_threshold(), value=1.0, call_ids=calls, derived=True)

    assert figure.basis is Basis.DERIVED
    assert figure.published is True


# --- Caveats are computed, never hand-written ------------------------------


def test_the_withheld_caveat_states_both_numbers_and_the_unit() -> None:
    caveat = below_min_n_caveat(_threshold(counts="triggers"), 11)

    assert "11 triggers" in caveat
    assert "30" in caveat
    assert "contact rate" in caveat


def test_the_no_field_caveat_says_what_would_unlock_it() -> None:
    """Insights 6, 17 and 25. §8 asks the panel to state the question, why it
    cannot be answered, and exactly what data would unlock it — the last part
    being what separates a considered gap from an oversight.
    """
    caveat = no_field_caveat(
        "employer-caused member confusion",
        "an EMPLOYER value in complaint.attributed_to, which v9 does not have",
    )

    assert "cannot be answered from the v9 schema" in caveat
    assert "EMPLOYER value" in caveat
