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

import hashlib
import re
from dataclasses import dataclass

from domain.errors import ValidationError

_FIELD = ""  # unlikely to occur in a label
_RECORD = ""

#: A numeric token as it appears in prose: 74, 74.2, 74%, 1,234, £12.
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")

#: Magnitudes written as words. Checking digits alone is not enough: the
#: first real model run wrote "Ninety-five accounts could not be assessed"
#: and walked straight through a check that only reads digits. A figure
#: spelled out is still a figure.
#:
#: **Cardinals and fractions only.** Ordinals are deliberately absent —
#: "first contact resolution" is a metric's name, and a check that refused
#: it would refuse the sentences most worth writing. Quantifiers ("no",
#: "all", "most", "every") are absent too: they are not magnitudes, and
#: whether they are *warranted* is a question about inference rather than
#: about arithmetic.
#:
#: The cost is real and accepted: a sentence saying "one account is
#: flagged" is refused even when true, because the fact says "1" and that
#: is what a sentence should quote.
_NUMBER_WORDS = frozenset(
    [
        "zero",
        "one",
        "two",
        "three",
        "four",
        "five",
        "six",
        "seven",
        "eight",
        "nine",
        "ten",
        "eleven",
        "twelve",
        "thirteen",
        "fourteen",
        "fifteen",
        "sixteen",
        "seventeen",
        "eighteen",
        "nineteen",
        "twenty",
        "thirty",
        "forty",
        "fifty",
        "sixty",
        "seventy",
        "eighty",
        "ninety",
        "hundred",
        "thousand",
        "million",
        "billion",
        "dozen",
        "half",
        "halves",
        "third",
        "thirds",
        "quarter",
        "quarters",
        "fifth",
        "fifths",
    ]
)

_WORD = re.compile(r"[a-z]+")


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


def spelled_numbers(text: str) -> frozenset[str]:
    """Magnitudes written as words rather than digits.

    Returned separately from `numbers_in` because they are not compared
    against the facts — they are refused outright. A fact carries the
    number as the screen prints it, so a sentence has a digit available for
    every figure it is entitled to mention; choosing a word instead is
    either a rounding nobody computed or a way around the check.
    """
    return frozenset(
        word for word in _WORD.findall(text.lower().replace("-", " ")) if word in _NUMBER_WORDS
    )


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
        """The magnitudes this fact licenses a sentence to state.

        The **label** counts too, and that is not a loophole: a number in a
        figure's name is a unit, not a measurement. "Contact rate per 1,000
        lives" is called that whatever the rate turns out to be, and a
        sentence naming the figure has to be able to name it.

        Found the hard way — the prompt was changed to require a sentence
        about any withheld figure, and the first real run wrote about the
        contact rate, said "per 1,000 lives", and had the whole surface
        rejected for quoting a number nobody measured.

        The **reason** counts for the same reason, and it is not hypothetical
        either: "Not a field in the v9 schema" puts a 9 in front of the
        model, and a sentence repeating the reason verbatim would have been
        refused for it.

        The rule this keeps: the model is never shown a number it may not
        quote. `tests/integration` asserts exactly that against the rendered
        prompt, because a number offered and then punished is a trap.
        """
        stated = numbers_in(self.display) if self.display is not None else frozenset()
        described = numbers_in(self.label) | numbers_in(self.withheld_reason or "")
        return stated | described | {normalise_number(str(self.n))}


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

    @property
    def digest(self) -> str:
        """A stable hash of everything the model would be told.

        The cache keys on this rather than on the filters that produced it,
        for the reason `domain/transcript_hash.py` gives about call
        references: two different filter strings can select the same calls
        and therefore the same figures, and a cache keyed on the query would
        bill twice for one answer. Hashing the facts means a changed figure
        is simply a miss, rather than a staleness bug somebody has to
        remember to invalidate.

        Every field that reaches the prompt is in here — including the
        withheld reason and the sample — because each of them can change a
        sentence while the published number stays put.

        Pure and deterministic: no clock, no randomness, same result on any
        machine.
        """
        parts = [self.subject]
        for fact in self.facts:
            parts.append(
                _FIELD.join(
                    (
                        fact.key,
                        fact.label,
                        fact.display or "",
                        str(fact.n),
                        fact.basis or "",
                        fact.withheld_reason or "",
                    )
                )
            )
        parts.extend(sorted(self.context_numbers))
        return hashlib.sha256(_RECORD.join(parts).encode("utf-8")).hexdigest()

    def unsupported_numbers(self, text: str) -> frozenset[str]:
        """Magnitudes in `text` that no fact accounts for.

        Empty is the contract Phase 5 exits on. A non-empty result is not a
        style problem to be edited away — it is the model having stated a
        number the corpus never produced, and the sentence does not ship.
        """
        return numbers_in(text) - self.allowed_numbers


#: The tails a sentence must not end on.
#:
#: Every one of these turns a figure into a claim the figures cannot carry:
#: "2 compliance exceptions were recorded, **indicating potential issues with
#: adherence to guidelines**" counts two things and then asserts a third that
#: nobody measured. The prompt has forbidden them since v1.5.0 and named three
#: of them verbatim; the first real run came back with all of them anyway,
#: which is why this is code and not a paragraph of instructions.
#:
#: Matched only after a comma. "Suggesting" is a normal English word and a
#: sentence is entitled to use it; what is refused is the trailing clause
#: bolted onto a number, which is the shape every one of these took.
_HEDGE_TAILS = (
    "indicating",
    "suggesting",
    "highlighting",
    "reflecting",
    "implying",
    "signalling",
    "signaling",
    "pointing to",
    "which may",
    "which could",
    "which might",
    "potentially",
    "raising concerns",
)

_HEDGE = re.compile(
    r",\s*(?:and\s+|thus\s+|so\s+)?(" + "|".join(_HEDGE_TAILS) + r")\b",
    re.IGNORECASE,
)

#: Metric syntax in the middle of a sentence: "Brokers named adversely = 0".
#: A reader is being shown the inside of the fact list rather than a sentence,
#: and no human writes an equals sign into prose.
_EQUATION = re.compile(r"\S\s*=\s*\S")


#: The shape the prompt gives for a figure nobody can state yet. Legitimate
#: on its own -- "Commercial intent routed cannot be given yet" -- and
#: self-contradictory the moment the same sentence quotes a number, because a
#: figure that has been given cannot also be the one that cannot be. The
#: first real run produced "Accounts that could not be assessed total 81,
#: which cannot be given yet", which is the template stitched onto a count.
_WITHHELD_PHRASE = re.compile(r"cannot be (?:given|said|published)", re.IGNORECASE)
_DIGIT = re.compile(r"\d")


def hedged_tail(sentence: str) -> str | None:
    """The offending phrase, or `None` if the sentence is clean.

    Returns the phrase rather than a bare bool so the log names what was
    wrong: "rejected a sentence" is not actionable, and the point of the
    check is to be able to say which habit the model fell into this time.
    """
    hedge = _HEDGE.search(sentence)
    if hedge is not None:
        return hedge.group(1).lower()
    if _EQUATION.search(sentence) is not None:
        return "="
    if _WITHHELD_PHRASE.search(sentence) is not None and _DIGIT.search(sentence) is not None:
        return "cannot be given, beside a figure"
    return None
