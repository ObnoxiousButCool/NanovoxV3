"""The thresholds every published figure is gated on, as domain objects.

`config/dashboard.yaml` holds the numbers; this module holds their shape and
the handful of decisions made *from* them — is this figure withheld, which
peer band is this employer in, is this employer eligible for the risk flag.

Those decisions live here rather than in each aggregation on purpose. Written
out nine times they would be written out nine slightly different ways, and
the ones that matter are exactly the ones an off-by-one makes invisible: a
figure published at n-1 does not look wrong, it looks like a figure.

Pure and framework-free. Reading the YAML is
`infrastructure/config/dashboard_config.py`'s job; nothing here touches a
file, and the `.yaml` is a transcription of the workbook's Metrics, Call
Quality Framework and Questions Worth Asking sheets, not a second definition
of them.
"""

from __future__ import annotations

from dataclasses import dataclass

from domain.value_objects.quality_band import QualityBand


@dataclass(frozen=True)
class MetricThreshold:
    """One row of the Metrics sheet's Window and Min n columns.

    `counts` is what `n` counts — "calls", "triggers", "calls per employer".
    The sheet says so for three of the fourteen rows and leaves the rest
    bare, meaning calls. It is carried rather than dropped because
    escalation integrity's 30 is 30 warranted escalations, and applying it
    to a call count instead turns a real gate into one that passes at
    batch-1 volume with 11 triggers behind it.
    """

    key: str
    sheet_row: str
    name: str
    #: The rolling window in weeks, or None for a row with no window of its
    #: own: metric 12 is scored per call and call volume is cut any way.
    window_weeks: int | None
    #: The sample size below which the figure is withheld, or None for a row
    #: that is never withheld for sample size (the sheet's "n/a" and "—").
    min_n: int | None
    counts: str

    def withheld(self, n: int) -> bool:
        """Is a figure computed over `n` too small to publish?

        Withheld is not zero. A suppressed figure has to say it is suppressed
        and why — rendering it as 0 reads as good news where the truth is
        that nobody has enough evidence to say.
        """
        if self.min_n is None:
            return False
        return n < self.min_n


@dataclass(frozen=True)
class PeerSizeBand:
    """A band of enrolled lives that employers are compared within.

    Not the fee band. Rule P-33's fee bands are a different boundary set over
    *eligible employees*, and `domain/reference_derivations.py` computes
    those separately.
    """

    label: str
    min_lives: int
    #: Inclusive upper bound; None for the open-ended top band.
    max_lives: int | None

    def contains(self, lives: int) -> bool:
        if lives < self.min_lives:
            return False
        return self.max_lives is None or lives <= self.max_lives


@dataclass(frozen=True)
class BrokerPatternTest:
    """Questions Worth Asking, trigger rule 2.

    Fires when the same broker is named adversely enough times, by enough
    different employers, inside the window. Below the line is a finding in
    itself — separate incidents rather than one broker underserving a book —
    so `fires` is asked, and the inputs shown, whichever way it answers.
    """

    min_adverse_mentions: int
    min_distinct_employers: int
    window_weeks: int

    def fires(self, adverse_mentions: int, distinct_employers: int) -> bool:
        return (
            adverse_mentions >= self.min_adverse_mentions
            and distinct_employers >= self.min_distinct_employers
        )


@dataclass(frozen=True)
class QualityBands:
    """Call Quality Framework sheet, stage 4: GOOD >=86, AVERAGE >=60, POOR below."""

    good_min: int
    average_min: int

    def band_for(self, score: int) -> QualityBand:
        if score >= self.good_min:
            return QualityBand.GOOD
        if score >= self.average_min:
            return QualityBand.AVERAGE
        return QualityBand.POOR


@dataclass(frozen=True)
class RiskFlagConfig:
    """Metric 10 (decision D2): a yes/no flag, never a band.

    Three numbers, three jobs, and the first two are the ones a reader gets
    wrong. An employer under `eligibility_min_calls` is NOT ELIGIBLE, which
    is not "not at risk" — at batch-1 volume most employers with calls have
    exactly one, so most of the page is ineligible rather than reassuring.
    """

    eligibility_min_calls: int
    flag_threshold: int
    quote_min_calls: int
    #: How close a renewal has to be for the fourth condition to apply.
    #: Borrowed from Questions Worth Asking trigger rule 4 -- metric 10 says
    #: "inside the renewal window" and never says how wide it is.
    renewal_window_days: int = 90

    def eligible(self, calls: int) -> bool:
        """Does this employer have enough calls to be assessed at all?"""
        return calls >= self.eligibility_min_calls

    def flagged(self, conditions_met: int) -> bool:
        """>=2 of the four named conditions. Never a prediction."""
        return conditions_met >= self.flag_threshold

    def quotable(self, calls: int) -> bool:
        """May the flag be quoted as a figure, rather than only shown?"""
        return calls >= self.quote_min_calls


@dataclass(frozen=True)
class IndicatorGates:
    """When one of the ten families counts as observed.

    Informational only. These never set the risk flag, and nothing in
    `risk_flag.py` reads them -- D2 makes the flag metric 10's four named
    conditions and nothing else, and a second scoring system feeding the
    first is how a yes/no flag turns back into a band.
    """

    #: The employer needs this many calls before any family is assessed. The
    #: prototype's own floor: "a share quoted on two calls is the false
    #: precision every other page avoids."
    min_employer_calls: int
    #: And the family needs this many of them. "Twice is intent. Once is a
    #: question" (Questions Worth Asking, trigger 8).
    min_calls: int
    #: And that many as a share of the employer's calls, so a family does not
    #: fire on two calls out of ninety. No source; needs calibration.
    min_rate: float

    def assessable(self, employer_calls: int) -> bool:
        """Whether the families can be tested against this employer at all.

        Separate from `fires` because it answers a different question, and
        the two answers mean opposite things to a reader. Below this floor
        no family can fire whatever its hits, so a count of nought is not a
        finding of nothing -- it is the families not having been checked.
        The page has to be able to tell those apart.
        """
        return employer_calls >= self.min_employer_calls

    def fires(self, hits: int, employer_calls: int) -> bool:
        """All three gates, or the family is not observed.

        `and`, not `or`: the floor stops one incident reading as a condition,
        and the rate stops a long-standing trickle reading as one. Either
        alone lets through exactly what the other exists to catch.
        """
        if not self.assessable(employer_calls) or hits < self.min_calls:
            return False
        return hits / employer_calls >= self.min_rate


@dataclass(frozen=True)
class DashboardConfig:
    """Everything `config/dashboard.yaml` carries.

    `metrics` is a tuple in the Metrics sheet's own order rather than a
    mapping, so that a diff of this object reads like a diff of the sheet.
    Lookups go through `metric()`, which raises on an unknown key instead of
    returning a default — a metric gated on a threshold nobody configured is
    a metric published with no gate at all.
    """

    version: str
    metrics: tuple[MetricThreshold, ...]
    #: Decision D4: unknown, finance owns it. While None, every money figure
    #: renders withheld and no placeholder is substituted anywhere.
    cost_per_call: float | None
    peer_size_bands: tuple[PeerSizeBand, ...]
    broker_ranking_floor_lives: int
    broker_pattern_test: BrokerPatternTest
    quality_bands: QualityBands
    risk_flag: RiskFlagConfig
    indicators: IndicatorGates

    def metric(self, key: str) -> MetricThreshold:
        for threshold in self.metrics:
            if threshold.key == key:
                return threshold
        known = ", ".join(sorted(t.key for t in self.metrics))
        raise KeyError(f"No metric '{key}' in dashboard config. Known metrics: {known}")

    def size_band_for(self, lives: int) -> PeerSizeBand | None:
        """The peer band an employer sits in, or None if it sits in none.

        None is a real answer, not a failure: the bands start at 2 lives
        because a group of one is not a group, and an employer below the
        first band has no peer set to be compared against.
        """
        for band in self.peer_size_bands:
            if band.contains(lives):
                return band
        return None

    def ranks_broker(self, book_lives: int) -> bool:
        """Insight 10: no book under the floor is ranked.

        `book_lives` is book size from the Broker Master, never a count of
        calls — dividing attributed calls by call volume is the error the
        floor exists alongside, not the one it fixes.
        """
        return book_lives >= self.broker_ranking_floor_lives

    @property
    def money_withheld(self) -> bool:
        """D4: with no cost per call, every money figure renders withheld."""
        return self.cost_per_call is None
