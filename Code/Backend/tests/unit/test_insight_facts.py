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
    hedged_tail,
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


class TestLabelsAreQuotable:
    """A number in a figure's name is a unit, not a measurement.

    The prompt requires a sentence about any withheld figure. The first real
    run obeyed, wrote about "Contact rate per 1,000 lives", and had the whole
    surface rejected for quoting the 1,000 in the figure's own name.
    """

    def test_a_unit_in_the_label_may_be_quoted(self) -> None:
        facts = _facts(
            Fact(
                key="contact_rate",
                label="Contact rate per 1,000 lives",
                display=None,
                n=18,
                withheld_reason="BELOW_MIN_N",
            )
        )

        assert (
            facts.unsupported_numbers("Contact rate per 1,000 lives cannot be published yet.")
            == frozenset()
        )

    def test_a_number_that_is_neither_label_nor_value_is_still_caught(self) -> None:
        facts = _facts(
            Fact(key="contact_rate", label="Contact rate per 1,000 lives", display="4.2", n=18)
        )

        assert facts.unsupported_numbers("The rate reached 9.7 per 1,000 lives.") == {"9.7"}


# --- Sentences that read as a machine wrote them ---------------------------
#
# Every string below is verbatim from the first real generation run against
# the live corpus, on 2026-09-30. The prompt had forbidden this shape since
# v1.5.0 and named three of them almost exactly ("..., which may affect
# customer satisfaction"), and the model wrote them anyway -- which is the
# argument for checking in code rather than asking again more firmly.


@pytest.mark.parametrize(
    ("sentence", "phrase"),
    [
        (
            "Commercial intent capture is at 16%, reflecting a low rate of identifying "
            "potential sales opportunities during calls.",
            "reflecting",
        ),
        (
            "First-contact resolution is at 40%, indicating that a significant number "
            "of calls are not resolved on the first attempt.",
            "indicating",
        ),
        (
            "The knowledge failure rate stands at 21%, suggesting that agents may lack "
            "the necessary information to resolve inquiries effectively.",
            "suggesting",
        ),
        (
            "93 lives are behind the 2 flagged accounts, highlighting a significant "
            "number of individuals affected.",
            "highlighting",
        ),
        (
            "8 rules were stated wrongly, which may affect the accuracy of information "
            "provided to callers.",
            "which may",
        ),
    ],
)
def test_a_hedged_tail_is_refused(sentence: str, phrase: str) -> None:
    """The figure is counted and then a third thing is asserted that nobody
    measured. The tail is the claim, and it is the part no reader can check."""
    assert hedged_tail(sentence) == phrase


def test_metric_syntax_in_prose_is_refused() -> None:
    """ "Brokers named adversely = 0" shows a reader the inside of the fact
    list. Nobody writes an equals sign into a sentence."""
    assert hedged_tail("Brokers named adversely = 0, indicating no adverse mentions.") is not None


def test_a_figure_cannot_be_quoted_and_withheld_in_one_breath() -> None:
    """The withheld wording stitched onto a count, which is what the model
    did with the ineligible accounts: it states 81 and denies it in the same
    sentence."""
    assert (
        hedged_tail(
            "Accounts that could not be assessed total 81, which cannot be given yet "
            "— too few calls to publish."
        )
        is not None
    )


@pytest.mark.parametrize(
    "sentence",
    [
        # The prototype's own voice: a figure, and what sits beside it.
        "30 of 95 accounts are flagged for risk, and 12 of them renew between October and January.",
        "Repeat contacts fell from 6 to 2 in the last four weeks.",
        "Control exceptions fell from 5 to 0 in the last 4 weeks.",
        # The withheld sentence the prompt actually asks for, which carries no
        # figure precisely because there is none to carry.
        "Commercial intent routed cannot be given yet — too few calls to publish.",
        # "Suggesting" is an ordinary word. Only the trailing clause bolted
        # onto a number is refused, so a sentence is free to use it.
        "The 3 calls suggesting a renewal date were counted separately.",
    ],
)
def test_a_sentence_a_person_would_write_survives(sentence: str) -> None:
    assert hedged_tail(sentence) is None
