"""The issues-to-act-on list: every playbook key with something behind it.

`Prototype/v2/actions.html`'s "Issues to act on" panel, which it builds by
walking `NV.PLAYBOOK` and counting each key. This counts the same keys over
the calls and employers in scope.

## Why this is keyed by playbook and not by signal

`domain.aggregation.actions` already groups the same calls by `SignalType`,
and that grouping is insight 21 — where the work came from. It is the right
answer to that question and the wrong one for this panel, because a signal
code is not an issue key: `member_communication_gap` has no playbook, so a
row built from it can name a number and offer nothing to do about it. The
whole promise of the screen is "every issue the platform has flagged, with
the steps to fix it", and a row without steps is that promise broken.

So this counts the fourteen keys `config/playbooks.yaml` defines, and every
row it returns therefore has a meaning, a suggested owner and a recommended
sequence waiting at `/actions?focus=<key>`. It is the same reversal
conflict **C9** needed for `/accounts`: the screen is shaped by the page it
mirrors, not by whichever endpoint happened to exist.

## The predicates are not written twice

Ten of the fourteen keys are the ten indicator families, which
`domain.aggregation.indicators` already defines as predicates over a call.
This reads `FAMILIES` rather than restating them, so a family and its
playbook can never drift into counting different calls. Two more —
`flagged` and `renew_soon` — are metric 10 and are read off `risk_flag`'s
own assessment for the same reason.

## What is deliberately missing, and why it is missing rather than zero

- **`high_effort`** cannot be computed at all: member effort is our
  composite and Stream A has not built it. It is returned with
  `computable=False` and no count. A row reading "High member effort 0"
  would be a false statement about the corpus, not a quiet one.
- **`overdue` and `unowned`** are questions about the action board — which
  cards are past their date, which flagged accounts no card names. The
  board is the write side and this is the read side; the read side has no
  action repository and must not grow one to answer a count. The screen
  holds both queries and can ask that question where both are already in
  hand.
- **`critical_signal`** is here and `flagged` is here, and they overlap. A
  call can be counted under several keys, because a key is a piece of work
  and not a bucket — the same call can need an escalation reviewed and a
  complaint logged. Nothing here sums the counts, and nothing should.

## Two windows, because there are two questions

The call keys are counted over the window the actions screen asks for.
`flagged` and `renew_soon` are metric 10, which `dashboard.yaml` defines
over its own window, and assessing it over somebody else's period would
quietly restate the metric — **D11**: a period is not a window. Both are
passed in, and neither is derived from the other.

## Counts, never rates

Every figure is a count of things to work, so there is no minimum-n floor:
"three escalations missed" is three calls somebody can name, whatever the
denominator would have been. A share would need one and there is none.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from domain.aggregation.call_tags import CallContext, EmployerFacts, Window
from domain.aggregation.indicators import FAMILIES
from domain.aggregation.repeat_contact import repeats
from domain.aggregation.risk_flag import assess, months_until
from domain.dashboard_config import DashboardConfig

#: A month is not a day, and `renewal_month` is all the workbook carries.
#: The risk flag's window is in days, so it is converted here rather than a
#: second, differently worded closeness rule being invented for this list.
_DAYS_PER_MONTH = 30

#: The two keys metric 10 answers, and the unit each counts.
FLAGGED = "flagged"
RENEW_SOON = "renew_soon"


@dataclass(frozen=True)
class IssueAccount:
    """One account's share of an issue, for "where it shows up".

    The reference data travels with the count because the panel ranks by
    renewal as well as by weight — "most calls, then soonest renewal" is
    the prototype's own order, and it is the right one: two accounts with
    the same problem are not equally urgent if one of them renews next
    month.
    """

    reference: str
    name: str
    region: str
    broker_ref: str
    renewal_month: str
    calls: int
    #: Whole months to the next renewal, or `None` when the workbook's
    #: month is not one this understands. Never a guess.
    months_to_renewal: int | None


@dataclass(frozen=True)
class Issue:
    """One playbook key's standing across everything in scope.

    `references` carries the calls or the employers behind the count rather
    than the count alone, so the focused view and the composer can open the
    same evidence this row was built from instead of re-deriving it and
    possibly disagreeing.
    """

    key: str
    #: "calls" or "accounts". Matches the playbook's own `unit`, and is
    #: repeated here so a reader of `references` knows what they are.
    unit: str
    references: tuple[str, ...]
    #: Where it shows up, heaviest first then soonest renewal. Empty for a
    #: key nothing fired on, and for one that cannot be counted at all.
    accounts: tuple[IssueAccount, ...] = ()
    computable: bool = True
    #: Why it cannot be counted, for a screen to show instead of a number.
    unavailable_because: str = ""

    @property
    def count(self) -> int:
        return len(self.references)


def issues_to_act_on(
    config: DashboardConfig,
    employers: Sequence[EmployerFacts],
    calls: Sequence[CallContext],
    window: Window,
    risk_window: Window,
    as_of: date,
) -> tuple[Issue, ...]:
    """Every countable playbook key, including the ones that counted zero.

    Zero rows are returned, not dropped. A caller that wants the
    prototype's list filters them; a caller that wants to say "we checked
    escalations and found none" needs the row to exist. Dropping them here
    would leave no way to tell a key that was clear from a key that was
    never asked.
    """
    in_window = window.calls_in(tuple(calls))
    book = {employer.reference: employer for employer in employers}
    return _call_issues(in_window, book, as_of) + _account_issues(
        config, employers, calls, risk_window, in_window, as_of
    )


def _call_issues(
    calls: Sequence[CallContext], book: dict[str, EmployerFacts], as_of: date
) -> tuple[Issue, ...]:
    """The ten indicator families, counted over the whole scope.

    `observe()` next door answers the same question for one employer. This
    cannot call it: an issue list is about the book, and running it per
    employer and adding up would apply the per-employer firing gate — a
    floor and a rate written for "does this account have a pattern" — to a
    question that is only "how many calls need working".
    """
    repeat_refs = tuple(sorted({pair.first.reference for pair in repeats(calls)}))

    issues: list[Issue] = []
    for family in FAMILIES:
        if not family.computable:
            issues.append(
                Issue(
                    key=family.code,
                    unit="calls",
                    references=(),
                    computable=False,
                    unavailable_because=family.unavailable_because,
                )
            )
            continue
        if family.matches is None:
            references = repeat_refs
        else:
            matches = family.matches
            references = tuple(sorted(call.reference for call in calls if matches(call)))
        issues.append(
            Issue(
                key=family.code,
                unit="calls",
                references=references,
                accounts=_where_it_shows_up(references, calls, book, as_of),
            )
        )
    return tuple(issues)


def _where_it_shows_up(
    references: Sequence[str],
    calls: Sequence[CallContext],
    book: dict[str, EmployerFacts],
    as_of: date,
) -> tuple[IssueAccount, ...]:
    """The accounts these calls landed on, heaviest first.

    A call with no employer is skipped rather than collected under an
    "unknown" account: the panel's whole use is picking an account to work,
    and a row nobody can open is not one. The call itself is still in
    `references`, so nothing is lost from the count — the two numbers
    differing is the honest outcome, not a discrepancy.
    """
    matched = set(references)
    counts: dict[str, int] = {}
    for call in calls:
        if call.reference not in matched or call.employer_ref is None:
            continue
        counts[call.employer_ref] = counts.get(call.employer_ref, 0) + 1
    return _accounts(counts, book, as_of)


def _accounts(
    counts: dict[str, int], book: dict[str, EmployerFacts], as_of: date
) -> tuple[IssueAccount, ...]:
    """Reference data joined to the counts, in the order the panel reads.

    Most calls first, then the soonest renewal, then the reference so two
    identical rows do not swap places between requests. An account with no
    renewal month sorts last rather than first: an unknown date is not an
    urgent one.
    """
    rows = [
        IssueAccount(
            reference=reference,
            name=book[reference].name,
            region=book[reference].region,
            broker_ref=book[reference].broker_ref,
            renewal_month=book[reference].renewal_month,
            calls=calls,
            months_to_renewal=months_until(book[reference].renewal_month, as_of),
        )
        for reference, calls in counts.items()
        if reference in book
    ]
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                -row.calls,
                row.months_to_renewal if row.months_to_renewal is not None else 99,
                row.reference,
            ),
        )
    )


def _account_issues(
    config: DashboardConfig,
    employers: Sequence[EmployerFacts],
    calls: Sequence[CallContext],
    risk_window: Window,
    in_window: Sequence[CallContext],
    as_of: date,
) -> tuple[Issue, ...]:
    """`flagged` and `renew_soon`, both read off metric 10's own assessment.

    An employer the window cannot assess is not flagged and is not counted.
    That is the same rule `RiskAssessment.state` states in words: not
    flagged is not the same as not at risk, and an ineligible account
    belongs in neither column of a to-do list.
    """
    flagged = [
        employer for employer in employers if assess(config, employer, calls, risk_window).flagged
    ]
    soon = [employer for employer in flagged if _renews_soon(config, employer, as_of)]
    book = {employer.reference: employer for employer in employers}
    # The screen's own period, not the flag's: "how much did this account
    # call" is a question about the window the reader is looking at, and
    # answering it from the flag's window would show a number no other
    # panel on the page agrees with.
    volume: dict[str, int] = {}
    for call in in_window:
        if call.employer_ref is not None:
            volume[call.employer_ref] = volume.get(call.employer_ref, 0) + 1

    def rows(chosen: list[EmployerFacts]) -> tuple[IssueAccount, ...]:
        return _accounts({e.reference: volume.get(e.reference, 0) for e in chosen}, book, as_of)

    return (
        Issue(
            key=FLAGGED,
            unit="accounts",
            references=tuple(e.reference for e in flagged),
            accounts=rows(flagged),
        ),
        Issue(
            key=RENEW_SOON,
            unit="accounts",
            references=tuple(e.reference for e in soon),
            accounts=rows(soon),
        ),
    )


def _renews_soon(config: DashboardConfig, employer: EmployerFacts, as_of: date) -> bool:
    """Whether the renewal falls inside metric 10's own renewal window.

    A month the workbook does not give, or does not spell in a way this
    understands, is not a renewal that is far away — it is a renewal nobody
    knows, so it does not go on a list headed by a deadline.
    """
    months = months_until(employer.renewal_month, as_of)
    if months is None:
        return False
    return months * _DAYS_PER_MONTH <= config.risk_flag.renewal_window_days
