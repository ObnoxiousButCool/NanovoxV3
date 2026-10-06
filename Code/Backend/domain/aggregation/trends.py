"""What moved, and whether the move means anything.

The executive screen's job is to say what changed since last time. Doing
that honestly is harder than it looks, because two different things both
produce "unresolved calls went from 8 to 12":

- something got worse, or
- there were more calls.

A screen that cannot tell those apart manufactures a finding every time
volume moves, and the reader learns to ignore it. So every comparison here
is **normalised by call volume first**, and a move is only reported as real
when it exceeds what that volume explains.

## Gaps are not zeros, here too

`weekly_series` returns `None` for a week the corpus has no calls in at all,
and `0` for a week that had calls and none of them matched. Those are
different facts and the charts render them differently — a gap in the line
versus a point on the baseline. Collapsing them is the same mistake as
publishing a withheld figure as zero, and it is easier to make here because
`len([]) == 0` is such a natural thing to write.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from domain.aggregation.call_tags import CallContext, Window

#: How far from what volume explains a move has to be before it is reported.
#: Two standard deviations, the conventional bar, and stated here rather than
#: buried in the calculation so it can be argued with.
NOISE_THRESHOLD = 2.0

#: A predicate picking the calls a measure counts.
Measure = Callable[[CallContext], bool]


def weeks_in(window: Window) -> tuple[Window, ...]:
    """The window cut into calendar weeks, earliest first.

    A partial final week is kept rather than dropped: a reader looking at
    "this week so far" is better served by a short bar they can see is short
    than by a week that silently vanished.
    """
    if window.end < window.start:
        return ()
    weeks: list[Window] = []
    start = window.start
    while start <= window.end:
        end = min(start + timedelta(days=6), window.end)
        weeks.append(Window(start, end))
        start = end + timedelta(days=1)
    return tuple(weeks)


def weekly_series(
    calls: Sequence[CallContext], window: Window, measure: Measure
) -> tuple[int | None, ...]:
    """One value per week, with `None` where the corpus is silent.

    `None` means "no calls at all that week", which is an absence of
    evidence. `0` means "calls happened and none matched", which is a
    measurement. The charts draw the first as a gap and the second on the
    baseline, and that distinction is the whole reason this returns an
    optional rather than an int.
    """
    series: list[int | None] = []
    for week in weeks_in(window):
        in_week = week.calls_in(tuple(calls))
        series.append(len([call for call in in_week if measure(call)]) if in_week else None)
    return tuple(series)


@dataclass(frozen=True)
class Movement:
    """One measure's change between two windows of equal length.

    `expected` is what the later window would have shown if nothing changed
    except how many calls came in. `z` is how far the actual count is from
    that, in standard deviations of a Poisson count. `beyond_noise` is the
    only field a screen should use to decide whether to say anything.
    """

    label: str
    now: int
    prior: int
    calls_now: int
    calls_prior: int
    expected: float
    z: float
    beyond_noise: bool
    #: Whether the move is in the direction that is bad for this measure.
    #: Direction is not meaning: unresolved calls rising is bad, resolved
    #: calls rising is good, and one flag cannot serve both.
    worse: bool

    @property
    def unchanged(self) -> bool:
        return self.now == self.prior


def movement(
    label: str,
    *,
    now: Sequence[CallContext],
    prior: Sequence[CallContext],
    measure: Measure,
    bad_when_up: bool = True,
) -> Movement:
    """Compare two windows, normalising for how busy each one was.

    The expected count is the prior count scaled by the change in volume, so
    a period with twice the calls is expected to carry twice the unresolved
    ones before anything is claimed. Without that scaling every busy week
    reads as a deterioration.

    The denominator is `sqrt(max(expected, 1))` rather than `sqrt(expected)`:
    at expected counts below one the Poisson standard deviation goes to zero
    and every observation becomes infinitely significant. At batch-1 volume
    that is the common case, not an edge case.
    """
    now_count = len([call for call in now if measure(call)])
    prior_count = len([call for call in prior if measure(call)])
    calls_now = len(now)
    calls_prior = len(prior)

    expected = prior_count * (calls_now / calls_prior) if calls_prior else float(prior_count)
    z = (now_count - expected) / math.sqrt(max(expected, 1.0))
    rose = now_count > prior_count

    return Movement(
        label=label,
        now=now_count,
        prior=prior_count,
        calls_now=calls_now,
        calls_prior=calls_prior,
        expected=expected,
        z=z,
        beyond_noise=abs(z) >= NOISE_THRESHOLD,
        worse=rose if bad_when_up else (now_count < prior_count),
    )


def preceding(window: Window) -> Window:
    """The window of equal length immediately before this one.

    Equal length is what makes the comparison legitimate. Comparing four
    weeks against a quarter is the other way to manufacture a finding, and
    it is harder to spot than an unnormalised count because both numbers
    are real.
    """
    span = window.end - window.start
    end = window.start - timedelta(days=1)
    return Window(end - span, end)


@dataclass(frozen=True)
class Bucket:
    """One slice of a period, with what it counted."""

    window: Window
    calls: int
    hits: int


@dataclass(frozen=True)
class Emerging:
    """A thing counted across equal slices, earliest first.

    Counts only, deliberately. `plan.md` §9's emerging view notes that at
    about eight calls a week a *share* would be two or three calls, so a
    percentage would imply a precision the corpus cannot support.

    ## Why the middle slices decide direction

    `delta` compares the ends and ignores everything between them, which is
    the right measure of net change and the wrong one for the word
    "emerging". A series of 19, 36, 30 is net up eleven and six below its
    own peak: still worth knowing, no longer emerging. Ranking on `delta`
    alone put exactly that series second on the executive screen's emerging
    panel, above things genuinely still climbing — a reader was told an
    issue was growing while it receded.

    So direction is `receded`, which reads every slice, and `rising` is net
    growth that has not turned back. The two together leave a third state,
    `delta > 0` while receding, which is neither emerging nor easing; it is
    `receded` and the screens report it as its own thing rather than
    dropping it, because a spike that is subsiding is a real finding.
    """

    key: str
    kind: str
    buckets: tuple[Bucket, ...]

    @property
    def delta(self) -> int:
        """Latest minus earliest. Zero when there are fewer than two slices."""
        if len(self.buckets) < 2:
            return 0
        return self.buckets[-1].hits - self.buckets[0].hits

    @property
    def peak(self) -> int:
        """The highest slice. Zero when there are no slices at all."""
        return max((bucket.hits for bucket in self.buckets), default=0)

    @property
    def receded(self) -> bool:
        """Whether the latest slice sits below the window's highest.

        False for a flat series and for one that peaks at the end, so a
        row that is level or still climbing is never called receding.
        """
        if not self.buckets:
            return False
        return self.buckets[-1].hits < self.peak

    @property
    def rising(self) -> bool:
        """Up on the window, and not down from its own peak."""
        return self.delta > 0 and not self.receded


def slice_window(window: Window, parts: int) -> tuple[Window, ...]:
    """Cut a window into `parts` equal slices, earliest first."""
    if parts < 1 or window.end < window.start:
        return ()
    total_days = (window.end - window.start).days + 1
    if total_days < parts:
        return ()
    size = total_days // parts
    slices: list[Window] = []
    start = window.start
    for index in range(parts):
        # The last slice absorbs the remainder rather than leaving days in
        # no slice at all, which would quietly drop calls from the rollup.
        end = window.end if index == parts - 1 else start + timedelta(days=size - 1)
        slices.append(Window(start, end))
        start = end + timedelta(days=1)
    return tuple(slices)


def emerging(
    calls: Sequence[CallContext],
    window: Window,
    *,
    kind: str,
    keys_of: Callable[[CallContext], Sequence[str]],
    parts: int = 3,
) -> tuple[Emerging, ...]:
    """Every value of some attribute, counted across equal slices.

    `keys_of` returns **zero or more** keys per call, which covers both
    shapes the screens need: a call has one category but may raise several
    signals. Returning an empty sequence leaves the call out entirely rather
    than bucketing it under an empty string — "no touchpoint recorded" is a
    real finding on its own screen, and smuggling it in here would put a
    phantom row at the top of a list of rising topics.

    A multi-valued attribute means the bucket counts sum to more than the
    calls in the slice. That is correct and matches the Signal Taxonomy
    sheet's own rule of distinct types per call, never occurrences — but it
    is why `Bucket` carries `calls` alongside `hits` rather than leaving a
    reader to assume the two are comparable.

    Sorted by the largest rise first, then by key, so the order is stable
    for equal deltas and a screen does not reshuffle between requests.
    """
    slices = slice_window(window, parts)
    if not slices:
        return ()

    keys = {key for call in calls for key in keys_of(call)}
    results: list[Emerging] = []

    for key in sorted(keys):
        buckets = tuple(
            Bucket(
                window=part,
                calls=len(in_part),
                hits=len([call for call in in_part if key in keys_of(call)]),
            )
            for part in slices
            for in_part in (part.calls_in(tuple(calls)),)
        )
        results.append(Emerging(key=key, kind=kind, buckets=buckets))

    return tuple(sorted(results, key=lambda item: (-item.delta, item.key)))


def as_of_window(as_of: date, weeks: int) -> Window:
    """The `weeks`-long window ending on `as_of`, inclusive."""
    return Window.of_weeks(as_of, weeks)
