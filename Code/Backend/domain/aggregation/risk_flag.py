"""Metric 10 — the account risk flag. A yes/no flag, never a band (D2).

This is the largest deliberate divergence from the prototype, which renders
a four-level High / Elevated / Watch / None band off a count of indicator
families. §3.0 settles it: the workbook wins on definitions, and the
workbook's metric 10 is a flag.

The three numbers do three different jobs and the first is the one readers
get wrong:

- **Eligible at 3 calls.** The sheet's denominator is "employers with >=3
  calls in window". Below it an employer is NOT ELIGIBLE, which is not "not
  at risk" and not "flagged false". At batch-1 volume most of the 92
  employers with calls have exactly one, so most of the page is ineligible
  rather than reassuring — and the page has to say so, which is why
  `RiskAssessment` carries `eligible` separately from `flagged` instead of
  collapsing both into a boolean.
- **Flagged on 2 of 4 conditions.**
- **Quotable at 10 calls.** The flag may be shown below this and not quoted
  as a figure.

**Never a prediction.** The sheet is explicit and the reason is concrete:
no termination outcomes exist in this dataset to validate one against.
Nothing here returns a probability, a score or a likelihood, and there is no
function that could be mistaken for one.

**The churn profile is not an input.** The label the corpus was generated
from cannot score the accounts it generated; `tests/unit/test_no_circular_scoring.py`
fails if any calculation so much as names that field. `EmployerFacts` does
not carry it, so it cannot reach this module at all.

## The fourth condition's window

"A CHOICE-attributed UNRESOLVED call inside the renewal window." Metric 10
does not say how wide the window is. Ninety days is borrowed from Questions
Worth Asking trigger rule 4, which pairs a rising complaint rate with a
renewal that "falls within 90 days" and records why: "90 days is the point
at which intervention is still possible." Borrowed, not invented — but
borrowed, so it is configured rather than written in here.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from domain.aggregation.call_tags import CallContext, EmployerFacts, Window
from domain.aggregation.figure import Figure, WithheldReason
from domain.aggregation.repeat_contact import failure_driven_repeats
from domain.dashboard_config import DashboardConfig
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.intent_type import IntentType
from domain.value_objects.outcome import Outcome

_MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)


@dataclass(frozen=True)
class Condition:
    """One of metric 10's four, and the calls that fired it."""

    code: str
    label: str
    met: bool
    call_ids: tuple[str, ...]


@dataclass(frozen=True)
class RiskAssessment:
    """One employer's standing against metric 10.

    `eligible`, `flagged` and `quotable` are three separate booleans on
    purpose. An ineligible employer has `flagged is False`, and a caller who
    reads that as "not at risk" is wrong — which is why `state` exists and
    returns the sentence the page should show rather than leaving the
    rendering to infer it.
    """

    employer_ref: str
    calls: int
    eligible: bool
    conditions: tuple[Condition, ...]
    flagged: bool
    quotable: bool

    @property
    def conditions_met(self) -> int:
        return sum(1 for condition in self.conditions if condition.met)

    @property
    def state(self) -> str:
        """What the page says about this employer, computed from the numbers."""
        if not self.eligible:
            return (
                f"Not eligible: {self.calls} call(s) in the window. "
                "Not the same as no risk — there is not enough here to assess."
            )
        if not self.flagged:
            return f"Not flagged: {self.conditions_met} of {len(self.conditions)} conditions met."
        quoted = "" if self.quotable else " Too few calls to quote this as a figure."
        return (
            f"Flagged: {self.conditions_met} of {len(self.conditions)} conditions met."
            f"{quoted} Not a prediction — no termination outcomes exist to validate one."
        )

    @property
    def evidence(self) -> tuple[str, ...]:
        """Every call behind every condition that fired, deduplicated."""
        return tuple(
            sorted(
                {
                    ref
                    for condition in self.conditions
                    if condition.met
                    for ref in condition.call_ids
                }
            )
        )


def assess(
    config: DashboardConfig,
    employer: EmployerFacts,
    calls: Sequence[CallContext],
    window: Window,
) -> RiskAssessment:
    """Metric 10 for one employer."""
    mine = [
        call for call in window.calls_in(tuple(calls)) if call.employer_ref == employer.reference
    ]
    flag = config.risk_flag
    conditions = (
        _complaint_rate_rising(mine, window),
        _has_failure_driven_repeat(mine),
        _market_test_intent(mine),
        _choice_unresolved_near_renewal(config, employer, mine, window),
    )
    eligible = flag.eligible(len(mine))
    met = sum(1 for condition in conditions if condition.met)
    return RiskAssessment(
        employer_ref=employer.reference,
        calls=len(mine),
        eligible=eligible,
        conditions=conditions,
        flagged=eligible and flag.flagged(met),
        quotable=flag.quotable(len(mine)),
    )


@dataclass(frozen=True)
class Exposure:
    """§9 insight 14 — lives and revenue behind the flagged accounts.

    "Presented as exposure, never as expected loss — there is no probability
    to apply to it." So this sums lives and premium over flagged employers
    and stops. Multiplying by anything would be the prediction metric 10 is
    explicitly not.
    """

    employers: tuple[str, ...]
    lives: int
    annual_premium: float
    #: True when at least one flagged employer has no premium recorded, so
    #: the total is a floor rather than the whole exposure. Said out loud,
    #: because a quietly incomplete sum is worse than a missing one.
    premium_incomplete: bool

    @property
    def caveat(self) -> str:
        floor = " At least one flagged account has no premium recorded, so this is a floor."
        return (
            f"Exposure across {len(self.employers)} flagged account(s): "
            f"{self.lives} lives. Exposure, not expected loss — there is no "
            f"probability to apply to it.{floor if self.premium_incomplete else ''}"
        )


def exposure(assessments: Sequence[RiskAssessment], employers: Sequence[EmployerFacts]) -> Exposure:
    """Sum lives and premium over the flagged employers, and nothing else."""
    flagged = {a.employer_ref for a in assessments if a.flagged}
    behind = [e for e in employers if e.reference in flagged]
    return Exposure(
        employers=tuple(sorted(flagged)),
        lives=sum(e.enrolled for e in behind),
        annual_premium=sum(e.annual_premium or 0.0 for e in behind),
        premium_incomplete=any(e.annual_premium is None for e in behind),
    )


def newly_flagged_count(
    current: Sequence[RiskAssessment], prior: Sequence[RiskAssessment]
) -> int:
    """Employers flagged now that were not flagged in the preceding window
    of equal length (`trends.preceding`) — the first indicator firing, not a
    running total of every account still flagged.

    An employer ineligible in the prior window counts as not flagged then:
    eligibility is a floor on quoting the flag (D2's `quotable`), not the
    flag itself, so a call-count crossing the eligibility floor between the
    two windows is exactly the "newly" this counts.
    """
    flagged_before = {a.employer_ref for a in prior if a.flagged}
    return sum(1 for a in current if a.flagged and a.employer_ref not in flagged_before)


def flagged_share(config: DashboardConfig, assessments: Sequence[RiskAssessment]) -> Figure:
    """Flagged employers as a share of the *eligible* ones.

    Eligible, never all employers. Dividing by every employer in the book
    buries the finding under the ninety accounts nobody could assess, and
    produces a reassuringly small percentage that means nothing.
    """
    eligible = [a for a in assessments if a.eligible]
    if not eligible:
        return Figure.withheld(
            WithheldReason.NOT_ELIGIBLE,
            (),
            caveats=(
                f"No employer reached {config.risk_flag.eligibility_min_calls} calls in this "
                "window, so none could be assessed. Not the same as none being at risk.",
            ),
        )
    flagged = [a for a in eligible if a.flagged]
    return Figure.observed(
        len(flagged) / len(eligible),
        tuple(sorted(ref for a in flagged for ref in a.evidence)),
    )


# --- The four conditions ---------------------------------------------------


def _complaint_rate_rising(calls: Sequence[CallContext], window: Window) -> Condition:
    """Complaint rate up month on month.

    Compared as rates, not counts: an employer whose calls doubled and whose
    complaints doubled has not deteriorated. The two halves of the window
    stand in for the two months — the sheet says "month-on-month" and the
    corpus is a single 12-week batch, so a literal calendar month would give
    three uneven periods and a comparison that moves with the calendar.
    """
    midpoint = window.start + timedelta(days=(window.end - window.start).days // 2)
    earlier = [call for call in calls if call.occurred_on <= midpoint]
    later = [call for call in calls if call.occurred_on > midpoint]
    rising = bool(earlier) and bool(later) and _complaint_share(later) > _complaint_share(earlier)
    return Condition(
        code="complaint_rate_rising",
        label="Complaint rate up on the previous period",
        met=rising,
        call_ids=tuple(sorted(call.reference for call in later if _complained(call))),
    )


def _has_failure_driven_repeat(calls: Sequence[CallContext]) -> Condition:
    """At least one failure-driven repeat (metric 4).

    One, not a rate. The sheet's condition is the presence of the thing, and
    at an employer's own volume a rate would almost always be withheld —
    which would make this condition unfirable for every account on the page.
    """
    repeats = failure_driven_repeats(calls)
    return Condition(
        code="failure_driven_repeat",
        label="A call we failed to resolve, that the caller came back about",
        met=bool(repeats),
        call_ids=tuple(sorted(call.reference for call in repeats)),
    )


def _market_test_intent(calls: Sequence[CallContext]) -> Condition:
    """Verbatim market-test language.

    `market_test` only. Expansion is a commercial opportunity rather than a
    risk, and cancellation is a different and later thing — the sheet names
    market_test specifically and widening it would flag accounts that said
    they wanted to buy more.
    """
    stated = [
        call
        for call in calls
        if any(statement.type is IntentType.MARKET_TEST for statement in call.tags.intent)
    ]
    return Condition(
        code="market_test_intent",
        label="Market-test language, quoted from the call",
        met=bool(stated),
        call_ids=tuple(sorted(call.reference for call in stated)),
    )


def _choice_unresolved_near_renewal(
    config: DashboardConfig,
    employer: EmployerFacts,
    calls: Sequence[CallContext],
    window: Window,
) -> Condition:
    """A CHOICE-attributed UNRESOLVED call inside the renewal window.

    All three parts must hold on the same call: ours, unresolved, and close
    to the renewal. A call meeting two of the three is not this condition,
    and treating it as one would make the flag fire on most of the book.
    """
    renewal = _next_renewal(employer.renewal_month, window.end)
    matching: list[CallContext] = []
    if renewal is not None:
        near = renewal - timedelta(days=config.risk_flag.renewal_window_days)
        matching = [
            call
            for call in calls
            if call.tags.outcome is Outcome.UNRESOLVED
            and _complained(call)
            and call.tags.complaint is not None
            and call.tags.complaint.attributed_to is ComplaintAttribution.CHOICE
            and near <= call.occurred_on <= renewal
        ]
    return Condition(
        code="choice_unresolved_near_renewal",
        label="An unresolved call blamed on us, close to renewal",
        met=bool(matching),
        call_ids=tuple(sorted(call.reference for call in matching)),
    )


def _complaint_share(calls: Sequence[CallContext]) -> float:
    return sum(1 for call in calls if _complained(call)) / len(calls) if calls else 0.0


def _complained(call: CallContext) -> bool:
    return call.tags.complaint is not None and call.tags.complaint.present


def months_until(renewal_month: str, on_or_after: date) -> int | None:
    """Whole months from `on_or_after` to the next renewal, or `None`.

    D12 sorts the risk list by indicator count and then by soonest renewal,
    so the number has to come from somewhere every client agrees on. It
    comes from here, beside the condition that already reads the same field,
    rather than being re-derived from a month name in each screen.

    `None` for a month reference data does not carry — the same refusal
    `_next_renewal` already makes. A caller that sorts on this must decide
    where unknown goes; it must not become zero, which would read as
    "renewing now" for the accounts we know least about.

    **The current month is 0, not 12.** This counts months between month
    names rather than reading `_next_renewal`'s date, and the difference
    only shows in one case: a renewal in the month we are already part-way
    through. `_next_renewal` is right to call that date past and look to
    next year, because it bounds a range of days. A sort key is not a
    range, and "renews this month" belongs at the top of a list ordered by
    urgency rather than at the bottom of it.
    """
    month = _month_number(renewal_month)
    if month is None:
        return None
    return (month - on_or_after.month) % 12


def _next_renewal(renewal_month: str, on_or_after: date) -> date | None:
    """The first of the renewal month, at or after `on_or_after`.

    `None` for a month name reference data does not carry — which happens,
    and is better than defaulting to January and quietly flagging every
    account with an unparseable renewal.
    """
    month = _month_number(renewal_month)
    if month is None:
        return None
    candidate = date(on_or_after.year, month, 1)
    if candidate < on_or_after:
        candidate = date(on_or_after.year + 1, month, 1)
    return candidate


def _month_number(renewal_month: str) -> int | None:
    """The workbook's renewal month as 1-12, or `None`.

    Reference data writes it short — "Jan", "Sep" — and this used to match
    on the full name only, so it resolved nothing at all against the real
    corpus: the fourth condition could not fire and every renewal sorted as
    unknown. Both forms are accepted now, matched on the first three
    letters, which is the same reading `account_stakes` already took of the
    same column.
    """
    prefix = renewal_month.strip()[:3].lower()
    if not prefix:
        return None
    for index, name in enumerate(_MONTHS):
        if name.startswith(prefix):
            return index + 1
    return None
