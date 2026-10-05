"""Group 7 — broker book friction, and the pattern test both it and group 2 use.

§9 insight 10: "**Counts lead.** `broker_named_aloud` present with
`sentiment = ADVERSE`, per broker, at the call's touchpoint; the per-100-lives
rate is a secondary sorting column only. No book under 150 lives is ranked.
Book size from the Broker Master, never from call counts."

Counts lead for a reason worth stating. A rate over a tiny book is a
dramatic number built on one call, and the ranking floor exists to stop that
reaching a page — but the floor only works if the denominator is the real
book. The Broker Master sheet is explicit: "Book size comes from Choice's
broker records and never from call counts, and that single decision is what
makes the small-broker finding possible."

`broker_named_aloud` rather than the `broker_conduct_adverse` signal,
because only the tag carries a `broker_ref`. The signal says a broker was at
fault; the tag says *which* broker, and a per-broker view needs the second.
They usually co-occur and are not interchangeable.

**The caveat is part of the finding.** A broker is counted only when a
caller says the name aloud, so silent accounts and brokers whose clients
never call are invisible here. The v9 README parks that by decision, not
oversight. `naming_coverage` measures how much of the book that hides and
hands the screen a sentence saying so, because for a long time this module
held the caveat as a constant and showed it to nobody.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from domain.aggregation.call_tags import BrokerFacts, CallContext, Window
from domain.aggregation.figure import Figure
from domain.aggregation.patterns import normalised_rate
from domain.dashboard_config import DashboardConfig
from domain.value_objects.broker_sentiment import BrokerSentiment
from domain.value_objects.signal_type import SignalType

#: Metric 2's broker-side rate is per 100 enrolled lives.
PER_HUNDRED = 100

NAMED_ALOUD_CAVEAT = (
    "A broker is counted only where a caller said the name aloud, so silent "
    "accounts and brokers whose clients never call are not represented."
)


@dataclass(frozen=True)
class NamingCoverage:
    """How thin the naming is under every count on the broker screen.

    The caveat above was written and then never shown, and the module
    docstring claimed it rode on every figure here. It did not, and at
    batch-1 density the omission matters: a caller named a broker on one
    call in six hundred while twenty-one calls raised a broker-conduct
    concern without naming anybody, so the table reads nought against
    twenty-nine of thirty agencies. A reader takes that for a clean book.

    Counted rather than asserted, so the sentence stops being alarming by
    itself once the naming improves -- and disappears when every call in
    scope carries a name, which is when there is nothing left to warn about.
    """

    named: int
    calls: int
    #: Calls raising `broker_conduct_adverse` without naming a broker. The
    #: signal says a broker was at fault; only the tag says which, so these
    #: are the concerns this screen cannot attribute to a row.
    unattributed: int

    @property
    def complete(self) -> bool:
        """True when nothing is missing: every call named, nothing unattributed."""
        return self.named >= self.calls and self.unattributed == 0

    @property
    def note(self) -> str:
        """The caveat with this corpus's own numbers in it, or empty."""
        if self.complete or not self.calls:
            return ""
        note = (
            f"A caller named a broker on {self.named} of the {self.calls} calls in "
            "scope, so a nought below is a missing name rather than a finding "
            "about the agency."
        )
        if self.unattributed:
            note += (
                f" A further {self.unattributed} call(s) raised a broker-conduct "
                "concern without naming anyone, and are in no row here."
            )
        return note


def naming_coverage(calls: Sequence[CallContext], window: Window) -> NamingCoverage:
    """What the broker screen's counts rest on, over the window it shows."""
    windowed = window.calls_in(tuple(calls))
    named = {
        call.reference
        for call in windowed
        if (aloud := call.tags.broker_named_aloud) is not None and aloud.present
    }
    return NamingCoverage(
        named=len(named),
        calls=len(windowed),
        unattributed=sum(
            1
            for call in windowed
            if SignalType.BROKER_CONDUCT_ADVERSE in call.tags.signals
            and call.reference not in named
        ),
    )


@dataclass(frozen=True)
class PatternTest:
    """Trigger rule 2, shown fired *and* unfired with what it reached.

    §9 insight 13 asks for both states, and the unfired one is the finding
    at batch-1 density: three adverse mentions from two employers is the
    line between "one broker underserving a book" and "separate incidents".
    Rendering only the fired case would leave a reader unable to tell a
    broker that nearly qualified from one with nothing against it.
    """

    broker_ref: str
    adverse_mentions: int
    distinct_employers: int
    fires: bool
    call_ids: tuple[str, ...]

    def reached(self, config: DashboardConfig) -> str:
        """What the test reached, as text computed from the numbers."""
        test = config.broker_pattern_test
        if self.fires:
            return (
                f"{self.adverse_mentions} adverse mentions from "
                f"{self.distinct_employers} employers — at or above "
                f"{test.min_adverse_mentions} from {test.min_distinct_employers}."
            )
        return (
            f"Below: {self.adverse_mentions} adverse mention(s) from "
            f"{self.distinct_employers} employer(s); needs "
            f"{test.min_adverse_mentions} from {test.min_distinct_employers}."
        )


@dataclass(frozen=True)
class BrokerFriction:
    """One broker's adverse mentions, ranked on counts."""

    broker_ref: str
    adverse_calls: tuple[str, ...]
    #: Adverse mentions split by the touchpoint the failure originated at,
    #: which is what turns "this broker is a problem" into a conversation
    #: about the enrolment meeting or the broker's own material.
    by_touchpoint: tuple[tuple[str, int], ...]
    pattern: PatternTest
    #: Secondary sorting column only, and withheld entirely for a book under
    #: the floor — never rendered as a headline.
    rate_per_hundred_lives: Figure | None


def adverse_mentions(
    broker_ref: str, calls: Sequence[CallContext], window: Window
) -> tuple[CallContext, ...]:
    """Calls naming this broker adversely, out loud, inside the window."""
    return tuple(
        call
        for call in window.calls_in(tuple(calls))
        if (named := call.tags.broker_named_aloud) is not None
        and named.present
        and named.broker_ref == broker_ref
        and named.sentiment is BrokerSentiment.ADVERSE
    )


def pattern_test(
    config: DashboardConfig, broker_ref: str, calls: Sequence[CallContext], window: Window
) -> PatternTest:
    """Trigger rule 2, over the pattern test's own window.

    The window comes from the config rather than the caller's filter: the
    rule is stated as "within a rolling 12 weeks", and a user who has
    narrowed to four weeks has not thereby redefined the workbook's test.
    """
    mentions = adverse_mentions(broker_ref, calls, window)
    employers = {call.employer_ref for call in mentions if call.employer_ref is not None}
    test = config.broker_pattern_test
    return PatternTest(
        broker_ref=broker_ref,
        adverse_mentions=len(mentions),
        distinct_employers=len(employers),
        fires=test.fires(len(mentions), len(employers)),
        call_ids=tuple(call.reference for call in mentions),
    )


def broker_friction(
    config: DashboardConfig,
    broker: BrokerFacts,
    calls: Sequence[CallContext],
    window: Window,
) -> BrokerFriction:
    """One broker's row: counts first, rate only if the book clears the floor."""
    mentions = adverse_mentions(broker.reference, calls, window)
    touchpoints: dict[str, int] = {}
    for call in mentions:
        where = call.tags.touchpoint or "unattributed"
        touchpoints[where] = touchpoints.get(where, 0) + 1

    return BrokerFriction(
        broker_ref=broker.reference,
        adverse_calls=tuple(call.reference for call in mentions),
        by_touchpoint=tuple(sorted(touchpoints.items(), key=lambda item: (-item[1], item[0]))),
        pattern=pattern_test(config, broker.reference, calls, window),
        rate_per_hundred_lives=_rate(config, broker, mentions, window),
    )


def ranked_book_friction(
    config: DashboardConfig,
    brokers: Sequence[BrokerFacts],
    calls: Sequence[CallContext],
    window: Window,
) -> tuple[BrokerFriction, ...]:
    """Every broker whose book clears the ranking floor, worst count first.

    Brokers below the floor are omitted from the *ranking*, not from the
    data — `broker_friction` still computes their row for an account page.
    What the floor prevents is a three-group agency topping a league table
    on one call.
    """
    ranked = [
        broker_friction(config, broker, calls, window)
        for broker in brokers
        if config.ranks_broker(broker.book_lives)
    ]
    return tuple(
        sorted(ranked, key=lambda row: (-len(row.adverse_calls), row.broker_ref)),
    )


def _rate(
    config: DashboardConfig,
    broker: BrokerFacts,
    mentions: Sequence[CallContext],
    window: Window,
) -> Figure | None:
    """The per-100-lives rate, or nothing at all below the ranking floor.

    `None` rather than a withheld `Figure`: the floor is not a sample-size
    judgement about this broker's rate, it is a decision that the rate is
    not a meaningful thing to compute for a book that small. A withheld
    figure would invite a reader to wonder what it would have said.
    """
    if not config.ranks_broker(broker.book_lives):
        return None
    return normalised_rate(
        config.metric("complaint_rate"),
        matching=mentions,
        population=broker.book_lives,
        per=PER_HUNDRED,
        weeks=window.weeks,
    )
