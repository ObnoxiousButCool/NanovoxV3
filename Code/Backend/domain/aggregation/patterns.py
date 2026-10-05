"""The four calculation patterns every published metric is one of.

Not a refactor — the Metrics sheet's own instruction:

    "Every metric here is one of four calculation patterns, so the
    development team builds four functions and dimensions them rather than
    twenty-four reports."

Three of the four live here. The fourth, *composite flag*, is metric 10's
risk flag and metric 12's quality score; the flag is B4's and the score is
per call rather than an aggregate, so neither belongs in a function that
takes a population and returns a rate.

Writing them once is what makes the build notes enforceable in one place
instead of nine. The notes are not stylistic: metric 1's says that dividing
sample calls by book-wide enrolment is "the classic denominator error", and
metric 6's says that measuring escalations against all calls makes a 0%
handled rate read as good news. Both are mistakes you make by passing the
wrong argument, so both are guarded here.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import date, timedelta

from domain.aggregation.call_tags import CallContext, Window
from domain.aggregation.figure import Figure, WithheldReason
from domain.dashboard_config import MetricThreshold

_WEEKS_PER_YEAR = 52
_SECONDS_PER_MINUTE = 60


def _ids(calls: Sequence[CallContext]) -> tuple[str, ...]:
    return tuple(call.reference for call in calls)


def normalised_rate(
    threshold: MetricThreshold,
    *,
    matching: Sequence[CallContext],
    population: int,
    per: int,
    weeks: float,
) -> Figure:
    """Pattern 1 — calls per `per` people covered, per year.

    Metrics 1 (per 1,000 enrolled) and 2 (per 100 enrolled). The `per` is an
    argument because the two differ on it and nothing else.

    `population` must be the calls' *own* population. The sheet names the
    alternative explicitly: "Dividing sample calls by book-wide enrollment is
    the classic denominator error." Nothing here can check that the caller
    passed the right population — but making it a required argument beside
    the calls it belongs to is the most this layer can do about it, and it
    is why the two are not gathered from one object.

    Annualised by `52 / weeks`, so a 12-week window reports a yearly rate
    rather than a twelve-week one.
    """
    if population <= 0:
        return Figure.withheld(
            WithheldReason.NO_DENOMINATOR,
            _ids(matching),
            caveats=(
                f"Withheld: {threshold.name.lower()} needs a population to divide by, "
                "and this one has none recorded.",
            ),
        )
    annualised = len(matching) * (_WEEKS_PER_YEAR / weeks)
    return Figure.gated(threshold, annualised / (population / per), _ids(matching))


def window_reaches_outside(window: Window, since: date | None, until: date | None) -> bool:
    """Whether a metric's window needs calls from outside the asked-for period.

    Decision D11: a period filter bounds the corpus, it does not redefine a
    metric's window. So a request for three weeks does not turn a twelve-week
    rate into a three-week one — the rate is still the Metrics sheet's
    twelve-week rate, and nine of those weeks lie outside what was asked for.
    """
    if since is not None and window.start < since:
        return True
    return until is not None and window.end > until


def window_note(
    window: Window,
    calls: Sequence[CallContext],
    since: date | None,
    until: date | None,
    *,
    subjects: Sequence[str],
) -> str | None:
    """One sentence for everything a window disagrees with the scope about.

    Two disagreements, and a reader meets both at once:

    - The window reaches **outside** the period asked for. A request for one
      week does not turn a twelve-week rate into a one-week rate; the rate
      is still the Metrics sheet's, and most of its weeks lie outside what
      was asked for.
    - The window **leaves calls out** of the scope. A window ending before
      the corpus does, or a period selecting calls the window does not
      reach, puts calls on the filter bar's count that no figure here used.

    Said together because they are one fact about one window, and said once
    per window rather than once per metric. These were two functions and the
    executive screen printed six paragraphs: five saying a window reached
    outside the period, one per metric, and a sixth saying the same window
    left calls out. Nobody reads six. Grouped, that screen says two things.

    The all-excluded case gets its own words. "Leaves out 56 of the 56 calls
    in scope" is arithmetically true and tells a reader nothing; what it
    means is that the period they picked and the window this metric uses do
    not overlap at all, which is why the figures above are withheld.

    Returns `None` when the window agrees with the scope on both counts, so
    the sentence appears only when there is something to disclose. A caveat
    printed every time stops being read.
    """
    if not subjects:
        return None
    outside = len(calls) - len(window.calls_in(tuple(calls)))
    reaches_out = window_reaches_outside(window, since, until)
    if not reaches_out and outside <= 0:
        return None

    # Plain words, a reader's dates: "use the last 4 weeks (28 Aug to 25 Sep),
    # so 419 of the 600 calls in scope aren't counted in them." The previous
    # sentence ended on D11's own phrasing, which explained the rule and not
    # what it meant for the figures.
    one = len(subjects) == 1
    weeks = round(window.weeks)
    sentence = (
        f"{_subject_list(subjects)} {'uses' if one else 'use'} the last "
        f"{weeks} week{'' if weeks == 1 else 's'} ({_span(window.start, window.end)})"
    )
    if reaches_out:
        sentence += f", which goes beyond the period you picked ({_period_text(since, until)})"
    if outside > 0:
        total = len(calls)
        pronoun = "it" if one else "them"
        verb_not = "isn't" if outside == 1 else "aren't"
        sentence += (
            f", so none of the {_calls(total)} in scope {'is' if total == 1 else 'are'} "
            f"counted in {pronoun}"
            if outside == total
            else f", so {outside} of the {_calls(total)} in scope {verb_not} counted in {pronoun}"
        )
    return f"{sentence}."


def _subject_list(subjects: Sequence[str]) -> str:
    """ "X" for one, "X and Y" for two, Oxford-free list beyond."""
    names = list(subjects)
    if len(names) == 1:
        return names[0]
    return f"{', '.join(names[:-1])} and {names[-1]}"


def _calls(count: int) -> str:
    return f"{count} call" if count == 1 else f"{count} calls"


def _day(day: date) -> str:
    """ "28 Aug", as the filter bar's week picker writes a date."""
    return f"{day.day} {day:%b}"


def _span(start: date, end: date) -> str:
    return f"{_day(start)} to {_day(end)}"


def _period_text(since: date | None, until: date | None) -> str:
    if since is not None and until is not None:
        return _span(since, until)
    if since is not None:
        return f"from {_day(since)}"
    if until is not None:
        return f"up to {_day(until)}"
    return "the whole corpus"


def window_for(threshold: MetricThreshold, as_of: date) -> Window | None:
    """The window one metric is computed over, ending on `as_of`.

    The Metrics sheet sets `window_weeks` per metric, and they differ on a
    single screen: first contact resolution and knowledge failure rate look
    back four weeks where escalation integrity and commercial intent look
    back twelve. Computing a screen's figures over one shared window would
    publish at least two of them against a period their own definition does
    not use, under a heading stating the other period.

    `None` means the metric is never windowed — `agent_quality_score` and
    `call_volume` carry `window_weeks: null`, and a score is a property of
    the call rather than of a period. Callers pass every call in that case
    rather than substituting a window of their own.
    """
    if threshold.window_weeks is None:
        return None
    return Window(as_of - timedelta(weeks=threshold.window_weeks), as_of)


def share(
    threshold: MetricThreshold,
    *,
    numerator: Sequence[CallContext],
    denominator: Sequence[CallContext],
) -> Figure:
    """Pattern 2 — a proportion of a named denominator, in 0..1.

    Metrics 3, 4, 5, 6, 7, 8 and 11. The denominator is always passed in and
    never inferred from the numerator, because which calls belong in it is
    the whole argument in at least three of those metrics:

    - Metric 3: PARTIALLY_RESOLVED and ESCALATED sit in the denominator, not
      the numerator.
    - Metric 6: the denominator is calls where escalation triggered, never
      all calls. Against all calls a 0% handled rate reads as good news;
      against warranted calls it reads as the control failure it is.
    - Metric 7: the denominator is calls *requiring that control*, not every
      call.

    `n` is the size of the denominator, so the gate is applied to the sample
    the rate actually rests on. That is what makes escalation integrity's
    "30 triggers" mean 30 triggers.
    """
    if not denominator:
        return Figure.withheld(
            WithheldReason.NO_DENOMINATOR,
            _ids(numerator),
            caveats=(
                f"Withheld: no calls qualify for {threshold.name.lower()}'s denominator "
                "in this window.",
            ),
        )
    if not _is_subset(numerator, denominator):
        raise ValueError(
            f"{threshold.name}: the numerator contains calls that are not in the denominator, "
            "which would produce a share above 1."
        )
    return Figure.gated(
        threshold,
        len(numerator) / len(denominator),
        _ids(denominator),
        n=len(denominator),
    )


def time_aggregate(
    threshold: MetricThreshold,
    *,
    calls: Sequence[CallContext],
    population: int,
    weeks: float,
) -> Figure:
    """Pattern 3 — minutes of our people per covered life, per year.

    Metric 9, cost to serve: `sum of aht_seconds, annualised, divided by 60`, over lives
    enrolled. The margin metric, because the admin fee is flat per group
    regardless of service consumed.

    Minutes, never money. Decision D4 keeps `cost_per_call` null, and §9
    insight 15 is explicit that money does not enter this view at all rather
    than entering it withheld.

    AHT is talk time only — it excludes hold and after-call work — so every
    figure this produces is a floor, and the caveat says so rather than
    leaving a reader to assume it is the whole cost.
    """
    if population <= 0:
        return Figure.withheld(
            WithheldReason.NO_DENOMINATOR,
            _ids(calls),
            caveats=("Withheld: cost to serve needs enrolled lives, and none are recorded.",),
        )
    timed = [call for call in calls if call.tags.aht_seconds is not None]
    if not timed:
        return Figure.withheld(
            WithheldReason.NO_DENOMINATOR,
            _ids(calls),
            caveats=("Withheld: no call in this window carries a talk time.",),
        )
    seconds = sum(call.tags.aht_seconds or 0 for call in timed)
    minutes_per_year = seconds * (_WEEKS_PER_YEAR / weeks) / _SECONDS_PER_MINUTE
    figure = Figure.gated(threshold, minutes_per_year / population, _ids(timed))
    return _with_caveat(
        figure,
        "Talk time only: hold and after-call work are excluded, so this is a floor.",
    )


def _is_subset(numerator: Sequence[CallContext], denominator: Sequence[CallContext]) -> bool:
    return {call.reference for call in numerator} <= {call.reference for call in denominator}


def _with_caveat(figure: Figure, caveat: str) -> Figure:
    """Append a caveat without disturbing anything else about the figure."""
    return replace(figure, caveats=(*figure.caveats, caveat))
