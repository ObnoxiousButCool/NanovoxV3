"""Account facts that raise the stakes on everything else.

`Prototype/v2/employer.html`'s "Account facts that raise the stakes", which
it renders from a stored `structural` array. There is no such array in v9,
and there does not need to be: all three of the notes the prototype carries
are derivable from reference fields the workbook already holds, and two of
them cite a rule the Rules sheet states outright.

## These are reference, not observation

Nothing here counts a call. Every note is a fact about what the account *is*
— how many of its eligible lives enrolled, how many calls its design plans
for, when it renews — which is why `basis` is REFERENCE and why the screen
puts them under the indicators rather than among them. An indicator fired
because something happened; a stake is true whether or not anyone called.

The distinction matters for the reader more than it looks. "Participation is
below the threshold" and "four calls went unresolved" want different
responses, and a panel that mixed them would invite the reader to treat a
standing structural fact as a recent event.

## Why a threshold is allowed here and forbidden elsewhere

`account_profile` refuses to count "calls scoring below N" because nothing
in the workbook sets N, so picking one would be inventing a finding. The
opposite is true here: **rule P-18 states the number.**

    Employer-sponsored dental: minimum 2 enrolled AND 70% participation.

So the threshold is quoted, not chosen, and the note names the rule it comes
from so a reader can go and disagree with the workbook rather than with us.
A note whose threshold we cannot source does not belong in this module.

## The contact-rate note compares plans, never plans against measurements

`calls_per_100` is what the workbook's design *planned* for the account. It
is not `contact_rate`, which is what actually happened, and the two must not
be compared: the corpus is a sample of the planned volume, so an account
would look far below its own plan for no reason but batch size.

The note therefore ranks a plan against other plans — this account's
planned rate against the book's median planned rate — and says "planned" in
its own wording so the two can never be read as one number.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from statistics import median

from domain.aggregation.call_tags import EmployerFacts

#: Rule P-18's own threshold, quoted rather than chosen. The rule text is
#: carried alongside so a screen can cite it without a second copy of the
#: number drifting away from this one.
P18_PARTICIPATION = 0.70
P18_MINIMUM_ENROLLED = 2
P18 = "P-18"

#: The sponsorship value P-18 applies to. Voluntary dental has no
#: participation requirement, so the note must not fire on it.
EMPLOYER_SPONSORED = "ER"

#: How close a renewal has to be to be worth saying. The prototype's own
#: ninety days, expressed in months because `renewal_month` is a month and
#: pretending to a day's precision it does not have would be false.
RENEWAL_SOON_MONTHS = 3

_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


@dataclass(frozen=True)
class Stake:
    """One structural fact about an account, with the figures behind it."""

    code: str
    label: str
    #: The numbers, already worded. Kept as one string because each note's
    #: figures mean something different and a generic {value, unit} pair
    #: would lose the "of", the "%" and the rule citation that make the
    #: sentence checkable.
    detail: str


def months_to_renewal(renewal_month: str, as_of: date) -> int | None:
    """Whole months from `as_of` to the next occurrence of that month.

    `None` when the workbook's month is not one this understands, rather
    than a guess — a wrong countdown on a renewal is worse than none.
    Returns 0 for the current month: the renewal is this month, not
    "twelve months away", which is what a naive forward search would say.
    """
    try:
        target = _MONTHS.index(renewal_month[:3].title()) + 1
    except ValueError:
        return None
    return (target - as_of.month) % 12


def account_stakes(
    employer: EmployerFacts, book: Sequence[EmployerFacts], as_of: date
) -> tuple[Stake, ...]:
    """The structural notes for one account, most consequential first.

    `book` is every employer in reference data, which is what makes the
    contact-rate note a comparison rather than an assertion. It is the same
    population the peer comparison uses, and for the same reason: a median
    over the employers that happened to call would move with call volume.
    """
    stakes: list[Stake] = []

    participation = _participation_note(employer)
    if participation is not None:
        stakes.append(participation)

    contact = _planned_contact_note(employer, book)
    if contact is not None:
        stakes.append(contact)

    renewal = _renewal_note(employer, as_of)
    if renewal is not None:
        stakes.append(renewal)

    return tuple(stakes)


def _participation_note(employer: EmployerFacts) -> Stake | None:
    """Rule P-18, and only where P-18 applies.

    Three ways this stays silent, all of them deliberate: the plan is
    voluntary rather than employer-sponsored, so the rule does not reach it;
    the workbook has no participation figure, which is a gap and not a
    failure; or the account meets the threshold, which is the normal case
    and not a finding.
    """
    if employer.dental_sponsorship != EMPLOYER_SPONSORED:
        return None
    if employer.participation is None or employer.eligible <= 0:
        return None
    if employer.participation >= P18_PARTICIPATION:
        return None
    if employer.enrolled < P18_MINIMUM_ENROLLED:
        # P-18 has two limbs and this one fails the other; saying
        # "participation is low" about a group of one would be noise.
        return None

    percent = round(employer.participation * 100)
    required = round(P18_PARTICIPATION * 100)
    return Stake(
        code="participation_below_threshold",
        label=f"Participation below {required}% on employer-sponsored dental",
        detail=(
            f"{employer.enrolled} of {employer.eligible} eligible lives enrolled "
            f"({percent}%) — rule {P18} requires {required}%"
        ),
    )


def _planned_contact_note(employer: EmployerFacts, book: Sequence[EmployerFacts]) -> Stake | None:
    """This account's planned contact rate against the book's median plan.

    Silent when the account has no planned rate, and silent when fewer than
    two other accounts do — a median of one is not a median, and the same
    rule governs the peer comparison next to it.
    """
    if employer.calls_per_100 is None:
        return None

    others = [
        other.calls_per_100
        for other in book
        if other.calls_per_100 is not None and other.reference != employer.reference
    ]
    if len(others) < 2:
        return None

    book_median = median(others)
    if employer.calls_per_100 <= book_median:
        return None

    return Stake(
        code="high_contact_rate",
        label="Planned contact rate above the book median",
        detail=(
            f"{employer.calls_per_100:.1f} planned calls per 100 lives, against a "
            f"book median of {book_median:.1f}. A plan, not a count — the measured "
            "contact rate is the figure above."
        ),
    )


def _renewal_note(employer: EmployerFacts, as_of: date) -> Stake | None:
    """A renewal close enough that the open issues have a deadline."""
    months = months_to_renewal(employer.renewal_month, as_of)
    if months is None or months > RENEWAL_SOON_MONTHS:
        return None

    when = "this month" if months == 0 else f"in {months} month{'' if months == 1 else 's'}"
    return Stake(
        code="renewal_near",
        label=f"Renews {when}",
        detail=(
            f"Renews {employer.renewal_month}. Anything open on this account has "
            "that as its deadline."
        ),
    )
