"""The envelope every aggregation returns, and the four things it enforces.

These are not shape tests. Each invariant below corresponds to a way a
figure can be published that looks completely normal and is wrong, which is
why they raise rather than warn.
"""

from __future__ import annotations

import pytest

from domain.aggregation.figure import (
    EpistemicClass,
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
            epistemic=EpistemicClass.WITHHELD,
            withheld_reason=WithheldReason.BELOW_MIN_N,
        )


def test_a_withheld_figure_must_say_why() -> None:
    """ "Not shown" with no reason is indistinguishable from a bug."""
    with pytest.raises(ValueError, match="must say why"):
        Figure(value=None, n=0, call_ids=(), epistemic=EpistemicClass.WITHHELD)


def test_a_published_figure_cannot_carry_a_withheld_reason() -> None:
    with pytest.raises(ValueError, match="must not carry a withheld reason"):
        Figure(
            value=1.0,
            n=0,
            call_ids=(),
            epistemic=EpistemicClass.MEASURED,
            withheld_reason=WithheldReason.BELOW_MIN_N,
        )


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
        Figure(value=1.0, n=10, call_ids=_CALLS, epistemic=EpistemicClass.MEASURED)


def test_a_withheld_figure_keeps_its_evidence() -> None:
    """A reader told four calls is too few should still be able to open them."""
    figure = Figure.withheld(WithheldReason.BELOW_MIN_N, _CALLS)

    assert figure.call_ids == _CALLS
    assert figure.n == 3
    assert figure.published is False


def test_a_negative_n_is_refused() -> None:
    with pytest.raises(ValueError, match="cannot be negative"):
        Figure(value=None, n=-1, call_ids=(), epistemic=EpistemicClass.MEASURED)


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
    assert figure.epistemic is EpistemicClass.MEASURED


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

    assert figure.epistemic is EpistemicClass.DERIVED
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
