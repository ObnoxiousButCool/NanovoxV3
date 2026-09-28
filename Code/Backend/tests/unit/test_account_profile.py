"""One account's own calls, counted.

What these protect is the difference between a count and a rate. A count of
zero over four calls is a true statement; a rate of zero over four is not,
and the whole application turns on keeping those apart.
"""

from __future__ import annotations

from datetime import date

from domain.aggregation.account_profile import account_profile
from domain.aggregation.call_tags import CallContext, CallTags, Window
from domain.value_objects.category import Category
from domain.value_objects.escalation import Escalation
from domain.value_objects.outcome import Outcome

WINDOW = Window(date(2026, 7, 1), date(2026, 9, 30))


def _call(
    reference: str,
    *,
    day: int = 15,
    month: int = 8,
    outcome: Outcome | None = Outcome.RESOLVED,
    category: Category | None = Category.CLAIMS_AND_EOB,
    escalation: Escalation | None = None,
    quality_score: int | None = None,
    caller: str = "CB-1",
) -> CallContext:
    return CallContext(
        tags=CallTags(
            reference=reference,
            outcome=outcome,
            category=category,
            escalation=escalation,
            quality_score=quality_score,
            caller_ref=caller,
        ),
        occurred_on=date(2026, month, day),
        employer_ref="EMP-1001",
    )


class TestCounts:
    def test_calls_outside_the_window_are_not_counted(self) -> None:
        profile = account_profile([_call("C-1"), _call("C-2", month=5)], WINDOW)

        assert profile.calls == 1

    def test_zero_is_a_real_answer_for_a_count(self) -> None:
        """No suppression: a count of things that happened has no minimum."""
        profile = account_profile([_call("C-1"), _call("C-2")], WINDOW)

        assert profile.calls == 2
        assert profile.unresolved == 0
        assert profile.escalations_missed == 0

    def test_unresolved_counts_only_that_outcome(self) -> None:
        calls = [
            _call("C-1", outcome=Outcome.UNRESOLVED),
            _call("C-2", outcome=Outcome.RESOLVED),
            _call("C-3", outcome=None),
        ]

        assert account_profile(calls, WINDOW).unresolved == 1

    def test_a_warranted_escalation_that_was_handled_is_not_missed(self) -> None:
        calls = [
            _call("C-1", escalation=Escalation(triggered=True, handled=True)),
            _call("C-2", escalation=Escalation(triggered=True, handled=False)),
            # No escalation recorded at all: in neither half, never a miss.
            _call("C-3", escalation=None),
            _call("C-4", escalation=Escalation(triggered=False)),
        ]

        assert account_profile(calls, WINDOW).escalations_missed == 1


class TestTopics:
    def test_most_called_about_first(self) -> None:
        calls = [
            _call("C-1", category=Category.BILLING_AND_PREMIUM),
            _call("C-2", category=Category.CLAIMS_AND_EOB),
            _call("C-3", category=Category.CLAIMS_AND_EOB),
        ]

        topics = account_profile(calls, WINDOW).topics

        assert [topic.category for topic in topics] == [
            Category.CLAIMS_AND_EOB,
            Category.BILLING_AND_PREMIUM,
        ]
        assert [topic.calls for topic in topics] == [2, 1]

    def test_a_tie_keeps_the_workbook_order_rather_than_swapping(self) -> None:
        """Two reads of the same corpus must not reorder the bars."""
        calls = [
            _call("C-1", category=Category.BILLING_AND_PREMIUM),
            _call("C-2", category=Category.COVERAGE_AND_BENEFITS),
        ]

        topics = account_profile(calls, WINDOW).topics

        assert [topic.category for topic in topics] == [
            Category.COVERAGE_AND_BENEFITS,
            Category.BILLING_AND_PREMIUM,
        ]

    def test_a_category_nobody_called_about_is_left_out(self) -> None:
        """Unlike the outcome chart, an absent category is not a finding."""
        topics = account_profile([_call("C-1")], WINDOW).topics

        assert len(topics) == 1

    def test_a_call_with_no_category_is_counted_rather_than_dropped(self) -> None:
        """The bars plus `uncategorised` must reconcile with `calls`."""
        calls = [_call("C-1"), _call("C-2", category=None)]

        profile = account_profile(calls, WINDOW)

        assert profile.uncategorised == 1
        assert sum(topic.calls for topic in profile.topics) + profile.uncategorised == (
            profile.calls
        )


class TestWhatIsDeliberatelyAbsent:
    def test_there_is_no_account_level_quality(self) -> None:
        """Metric 12 is per agent. `agent_quality` states that rolling it up
        to an employer is forbidden by the Metrics sheet, and the prototype's
        "Average call quality" tile on this page is that rollup. It is
        carried as a conflict, not served — so nothing here may grow a
        `quality` field by accident."""
        profile = account_profile([_call("C-1")], WINDOW)

        assert not hasattr(profile, "quality")
        assert not any("quality" in field for field in vars(profile))

    def test_coverage_is_counted_but_never_summarised(self) -> None:
        """`scored_calls` says how many calls carry a score, not how high
        they are. Two calls scoring 20 and 100 give the same count as two
        scoring 90 and 95 — which is the point: it is the coverage of a
        per-call figure, and no ordering of accounts can be read out of it."""
        low = [_call("C-1", quality_score=20), _call("C-2", quality_score=100)]
        high = [_call("C-3", quality_score=90), _call("C-4", quality_score=95)]

        assert account_profile(low, WINDOW).scored_calls == 2
        assert account_profile(high, WINDOW).scored_calls == 2

    def test_an_unscored_call_is_not_counted_as_scored(self) -> None:
        """A missing score is a gap in coverage, never a zero — the same rule
        the withheld figures follow everywhere else."""
        calls = [_call("C-1", quality_score=80), _call("C-2")]

        profile = account_profile(calls, WINDOW)

        assert profile.calls == 2
        assert profile.scored_calls == 1
