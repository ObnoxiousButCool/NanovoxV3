"""The numbers a generated sentence is allowed to contain.

## Why facts are a type rather than a dict

`Revised-Implementation-Plan.md` §9 Phase 5 says the insight service takes
"already-computed response DTOs". It cannot literally do that: response
models live in `frameworks_drivers`, and the layers contract points inward,
so an application use case importing one would break the build. The
substance of the requirement survives the translation, though, and arguably
improves: the router flattens whatever it already computed into a `FactSet`,
and that set is the **only** input the use case has. There is no repository,
no corpus and no session anywhere in its constructor, so "the service cannot
reach past its facts" is enforced by the type rather than promised in a
docstring.

## Facts carry the rendered number, not the raw one

A `Fact` holds `display` — the number exactly as the screen prints it,
"74%" rather than `0.7421`. The model never sees a float, which removes the
whole class of failure where it helpfully rounds `0.7421` to "74.21%" and
publishes a precision nobody computed, or divides two facts and states a
third the corpus never produced.

It also makes the guardrail cheap. "Every number in the generated text
appears in the input facts" becomes a set comparison over normalised
numeric tokens, rather than an attempt to recompute arithmetic the model
might have done.

## A withheld fact is still a fact

A figure nobody could publish is given to the model **with no number and
with its reason**, because "we cannot say" is often the most useful
sentence on the screen and the one a reader most needs said out loud. What
must never happen is a withheld figure silently becoming zero, so
`display` is `None` and there is nothing numeric to quote.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from domain.errors import ValidationError

#: A numeric token as it appears in prose: 74, 74.2, 74%, 1,234, £12.
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def normalise_number(token: str) -> str:
    """The magnitude of a numeric token, with presentation removed.

    Thousands separators and a trailing percent sign are stripped, and a
    trailing zero decimal is dropped, so "1,234", "1234" and "1234.0" are
    one number and "74%" and "74" are one number.

    Collapsing percent and bare is deliberate. The model writing "74
    percent" where the fact says "74%" is the same claim in different words,
    and refusing it would fail honest sentences. What the check exists to
    catch is a **magnitude nobody computed** — a 74 that became 75, or a
    third number derived from two facts — and normalising presentation does
    not let any of those through.
    """
    cleaned = token.replace(",", "").rstrip("%")
    if "." in cleaned:
        cleaned = cleaned.rstrip("0").rstrip(".")
    return cleaned or "0"


def numbers_in(text: str) -> frozenset[str]:
    """Every distinct magnitude stated in `text`."""
    return frozenset(normalise_number(match.group()) for match in _NUMBER.finditer(text))


@dataclass(frozen=True)
class Fact:
    """One figure, as the screen already shows it."""

    key: str
    #: How a reader would name it, e.g. "First contact resolution".
    label: str
    #: The number as printed, e.g. "74%". `None` exactly when withheld.
    display: str | None
    #: The sample behind it. Quotable, so it joins the allowed numbers.
    n: int
    #: OBSERVED / DERIVED / REFERENCE, or `None` on a withheld figure with
    #: no origin to name. The same value `FigureResponse.basis` carries.
    basis: str | None = None
    #: Why it is withheld. Non-null exactly when `display` is None.
    withheld_reason: str | None = None

    def __post_init__(self) -> None:
        if (self.display is None) != (self.withheld_reason is not None):
            raise ValidationError(
                f"Fact {self.key!r} must carry a number or a reason for having none, "
                "and never both or neither."
            )
        if self.n < 0:
            raise ValidationError(f"Fact {self.key!r} has a negative sample.")
        if any(character.isdigit() for character in self.key):
            # The key is shown to the model beside the numbers, and the
            # guardrail treats everything it was shown as quotable. A key
            # like `escalation_1` would therefore license the model to write
            # "1" and pass the check. Caught once in review; made impossible
            # here rather than left to whoever names the next fact.
            raise ValidationError(
                f"Fact key {self.key!r} contains a digit. Keys are shown to the model "
                "alongside the figures, so a digit in one becomes a number it may quote."
            )

    @property
    def published(self) -> bool:
        return self.display is not None

    @property
    def numbers(self) -> frozenset[str]:
        """The magnitudes this fact licenses a sentence to state."""
        stated = numbers_in(self.display) if self.display is not None else frozenset()
        return stated | {normalise_number(str(self.n))}


@dataclass(frozen=True)
class FactSet:
    """Everything one screen's insights may talk about.

    `context_numbers` is for magnitudes that are true of the page but are
    not figures — the call count in the page head, the year in the period.
    They are listed separately so that adding one is a visible decision
    rather than a fact quietly growing a second meaning.
    """

    #: What the screen is, in a reader's words: "the executive scorecard".
    subject: str
    facts: tuple[Fact, ...]
    context_numbers: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        keys = [fact.key for fact in self.facts]
        if len(keys) != len(set(keys)):
            raise ValidationError("Fact keys must be unique within a set.")

    @property
    def published(self) -> tuple[Fact, ...]:
        return tuple(fact for fact in self.facts if fact.published)

    @property
    def allowed_numbers(self) -> frozenset[str]:
        """Every magnitude a generated sentence may contain."""
        allowed = {normalise_number(number) for number in self.context_numbers}
        for fact in self.facts:
            allowed |= fact.numbers
        return frozenset(allowed)

    def unsupported_numbers(self, text: str) -> frozenset[str]:
        """Magnitudes in `text` that no fact accounts for.

        Empty is the contract Phase 5 exits on. A non-empty result is not a
        style problem to be edited away — it is the model having stated a
        number the corpus never produced, and the sentence does not ship.
        """
        return numbers_in(text) - self.allowed_numbers
