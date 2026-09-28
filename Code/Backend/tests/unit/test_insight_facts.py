"""The guardrail's arithmetic, tested without a model.

The property these protect is the one Phase 5 exits on: no generated
sentence contains a number absent from its input facts.
"""

from __future__ import annotations

import pytest

from domain.errors import ValidationError
from domain.insights.facts import (
    Fact,
    FactSet,
    normalise_number,
    numbers_in,
    spelled_numbers,
)


def _facts(*facts: Fact, context: frozenset[str] = frozenset()) -> FactSet:
    return FactSet(subject="the executive scorecard", facts=facts, context_numbers=context)


def _resolution(display: str | None = "74%") -> Fact:
    if display is None:
        return Fact(
            key="first_contact_resolution",
            label="First contact resolution",
            display=None,
            n=4,
            withheld_reason="MIN_N",
        )
    return Fact(
        key="first_contact_resolution",
        label="First contact resolution",
        display=display,
        n=112,
        basis="OBSERVED",
    )


class TestNormalising:
    @pytest.mark.parametrize(
        ("token", "expected"),
        [
            ("74", "74"),
            ("74%", "74"),
            ("1,234", "1234"),
            ("12.50", "12.5"),
            ("12.0", "12"),
            ("0.5", "0.5"),
        ],
    )
    def test_presentation_is_stripped_but_magnitude_is_not(self, token: str, expected: str) -> None:
        assert normalise_number(token) == expected

    def test_percent_and_bare_are_one_number(self) -> None:
        """ "74 percent" is the same claim as "74%", written differently."""
        assert normalise_number("74%") == normalise_number("74")

    def test_a_different_magnitude_stays_different(self) -> None:
        assert normalise_number("74") != normalise_number("75")

    def test_numbers_are_found_inside_prose(self) -> None:
        assert numbers_in("Resolution held at 74% across 112 calls.") == {"74", "112"}

    def test_prose_with_no_numbers_yields_none(self) -> None:
        assert numbers_in("Resolution held steady across the period.") == frozenset()


class TestFact:
    def test_a_published_fact_licenses_its_value_and_its_sample(self) -> None:
        assert _resolution().numbers == {"74", "112"}

    def test_a_withheld_fact_licenses_only_its_sample(self) -> None:
        """Nothing numeric to quote — which is the whole point of withholding."""
        assert _resolution(display=None).numbers == {"4"}

    def test_a_number_and_a_reason_together_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="never both or neither"):
            Fact(
                key="k",
                label="L",
                display="74%",
                n=1,
                withheld_reason="MIN_N",
            )

    def test_neither_a_number_nor_a_reason_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="never both or neither"):
            Fact(key="k", label="L", display=None, n=1)


class TestUnsupportedNumbers:
    def test_a_quoted_figure_is_supported(self) -> None:
        facts = _facts(_resolution())
        assert facts.unsupported_numbers("Resolution held at 74%.") == frozenset()

    def test_the_same_figure_written_as_words_is_supported(self) -> None:
        facts = _facts(_resolution())
        assert facts.unsupported_numbers("Resolution held at 74 percent.") == frozenset()

    def test_a_number_nobody_computed_is_caught(self) -> None:
        facts = _facts(_resolution())
        assert facts.unsupported_numbers("Resolution slipped to 71%.") == {"71"}

    def test_a_figure_derived_from_two_facts_is_caught(self) -> None:
        """The failure this exists for: arithmetic the corpus never did."""
        facts = _facts(
            _resolution(),
            Fact(key="repeat", label="Repeat rate", display="26%", n=112, basis="OBSERVED"),
        )
        # 74 and 26 are both real; 48, the gap between them, is not.
        assert facts.unsupported_numbers("A 48 point gap opened up.") == {"48"}

    def test_a_sample_size_is_quotable(self) -> None:
        facts = _facts(_resolution())
        assert facts.unsupported_numbers("Across 112 calls, resolution held.") == frozenset()

    def test_context_numbers_are_allowed(self) -> None:
        facts = _facts(_resolution(), context=frozenset({"2026"}))
        assert facts.unsupported_numbers("Since 2026 resolution held.") == frozenset()

    def test_prose_without_numbers_always_passes(self) -> None:
        facts = _facts(_resolution())
        assert facts.unsupported_numbers("Resolution is the figure to watch.") == frozenset()


class TestFactSet:
    def test_duplicate_keys_are_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unique"):
            _facts(_resolution(), _resolution())

    def test_published_excludes_withheld_figures(self) -> None:
        facts = _facts(
            _resolution(),
            Fact(
                key="intent", label="Intent routed", display=None, n=0, withheld_reason="NO_FIELD"
            ),
        )
        assert [fact.key for fact in facts.published] == ["first_contact_resolution"]

    def test_a_screen_of_withheld_figures_publishes_nothing(self) -> None:
        facts = _facts(_resolution(display=None))
        assert facts.published == ()


class TestKeysCarryNoNumbers:
    def test_a_key_with_a_digit_is_rejected(self) -> None:
        """A key is shown to the model, and the guardrail counts everything
        it was shown as quotable — so `escalation_1` would license "1"."""
        with pytest.raises(ValidationError, match="contains a digit"):
            Fact(key="escalation_1", label="Escalation", display="10%", n=5)

    def test_a_worded_key_is_fine(self) -> None:
        assert Fact(key="escalation_handled", label="Escalation", display="10%", n=5).key


class TestSpelledNumbers:
    """A figure written as a word is invisible to the digit check.

    Not hypothetical: the first real model run produced "Ninety-five
    accounts could not be assessed" and passed a check that reads digits
    only.
    """

    def test_a_spelled_figure_is_caught(self) -> None:
        assert spelled_numbers("Ninety-five accounts could not be assessed.") == {
            "ninety",
            "five",
        }

    def test_a_fraction_is_caught(self) -> None:
        assert spelled_numbers("Roughly a fifth of calls went unresolved.") == {"fifth"}

    def test_an_ordinal_in_a_metric_name_is_not_a_figure(self) -> None:
        """ "First contact resolution" is what the metric is called."""
        assert spelled_numbers("First contact resolution held steady.") == frozenset()

    def test_a_quantifier_is_not_a_magnitude(self) -> None:
        """Whether "no" is warranted is a question about inference, not
        arithmetic, and a different check's job."""
        assert spelled_numbers("No accounts were flagged.") == frozenset()

    def test_digits_are_left_to_the_other_check(self) -> None:
        assert spelled_numbers("95 accounts could not be assessed.") == frozenset()
