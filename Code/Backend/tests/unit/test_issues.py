"""The issues-to-act-on list.

What these protect is the screen's promise: every row names work somebody
can pick up, which means every row has to be a playbook key and not a
signal code. The second thing they protect is the difference between a key
that counted nothing and a key that cannot be counted at all.
"""

from __future__ import annotations

from datetime import date

import pytest

from domain.aggregation.call_tags import CallContext, Window
from domain.aggregation.issues import Issue, issues_to_act_on
from domain.dashboard_config import DashboardConfig
from domain.playbooks import PlaybookCatalogue
from domain.value_objects.control_exception_type import ControlExceptionType
from domain.value_objects.escalation import Escalation
from domain.value_objects.intent_type import IntentType
from domain.value_objects.outcome import Outcome
from domain.value_objects.signal_type import SignalType
from infrastructure.config.dashboard_config import load_dashboard_config
from infrastructure.config.paths import DEFAULT_CONFIG_DIR
from infrastructure.config.playbook_loader import load_playbooks
from tests.fixtures.tagged_calls import WINDOW, call, calls, day, employer

AS_OF = date(2026, 9, 28)


@pytest.fixture(scope="module")
def config() -> DashboardConfig:
    return load_dashboard_config(DEFAULT_CONFIG_DIR / "dashboard.yaml")


@pytest.fixture(scope="module")
def catalogue() -> PlaybookCatalogue:
    return load_playbooks(DEFAULT_CONFIG_DIR / "playbooks.yaml")


def _by_key(issues: tuple[Issue, ...]) -> dict[str, Issue]:
    return {issue.key: issue for issue in issues}


class TestEveryRowLeadsSomewhere:
    def test_every_key_returned_has_a_playbook(
        self, config: DashboardConfig, catalogue: PlaybookCatalogue
    ) -> None:
        """The reason this aggregation exists. A row whose key resolves to
        nothing can show a number and offer no steps, which is the promise
        in the screen's own title broken."""
        issues = issues_to_act_on(config, [employer()], calls(5), WINDOW, WINDOW, AS_OF)

        defined = {playbook.key for playbook in catalogue.playbooks}
        assert {issue.key for issue in issues} <= defined

    def test_the_unit_matches_the_playbook_s_own_unit(
        self, config: DashboardConfig, catalogue: PlaybookCatalogue
    ) -> None:
        """`references` is a list of call references or of employer
        references and nothing says which. The unit does, and if it
        disagreed with the playbook the focused view would open the wrong
        evidence."""
        issues = issues_to_act_on(config, [employer()], calls(5), WINDOW, WINDOW, AS_OF)
        units = {playbook.key: playbook.unit.value for playbook in catalogue.playbooks}

        for issue in issues:
            assert issue.unit == units[issue.key]


class TestCounting:
    def test_a_family_counts_the_calls_that_matched_it(self, config: DashboardConfig) -> None:
        traffic = (
            call("C-0001", outcome=Outcome.UNRESOLVED),
            call("C-0002", outcome=Outcome.UNRESOLVED),
            call("C-0003"),
        )

        issues = _by_key(issues_to_act_on(config, [employer()], traffic, WINDOW, WINDOW, AS_OF))

        assert issues["unresolved"].count == 2
        assert issues["unresolved"].references == ("C-0001", "C-0002")

    def test_one_call_can_be_counted_under_several_keys(self, config: DashboardConfig) -> None:
        """A key is a piece of work, not a bucket. The same call can need an
        escalation reviewed and its outcome chased, and putting it in one
        list only would lose one of the two jobs."""
        traffic = (
            call(
                "C-0001",
                outcome=Outcome.UNRESOLVED,
                escalation=Escalation(triggered=True, handled=False),
            ),
        )

        issues = _by_key(issues_to_act_on(config, [employer()], traffic, WINDOW, WINDOW, AS_OF))

        assert issues["unresolved"].references == ("C-0001",)
        assert issues["escalation_missed"].references == ("C-0001",)

    def test_a_key_with_nothing_behind_it_is_returned_at_zero(
        self, config: DashboardConfig
    ) -> None:
        """Kept rather than dropped: a caller that wants the prototype's
        list filters these out, and a caller that wants to say "we checked
        and found none" needs the row to exist to say it."""
        issues = _by_key(issues_to_act_on(config, [employer()], calls(5), WINDOW, WINDOW, AS_OF))

        assert issues["control_exception"].count == 0
        assert issues["control_exception"].computable is True

    def test_calls_outside_the_window_are_not_counted(self, config: DashboardConfig) -> None:
        traffic = (
            call("C-0001", outcome=Outcome.UNRESOLVED, on=day(1)),
            call("C-0002", outcome=Outcome.UNRESOLVED, on=date(2026, 1, 4)),
        )

        issues = _by_key(issues_to_act_on(config, [employer()], traffic, WINDOW, WINDOW, AS_OF))

        assert issues["unresolved"].references == ("C-0001",)

    def test_the_families_read_their_own_fields(self, config: DashboardConfig) -> None:
        """One call per family, to catch a predicate wired to the wrong
        field — the failure mode a shared count would hide."""
        traffic = (
            call(
                "C-0001",
                control_exceptions=frozenset({ControlExceptionType.NO_RECORDING_DISCLOSURE}),
            ),
            call("C-0002", knowledge_failure_rule="P-18"),
            call("C-0003", intent=IntentType.MARKET_TEST),
            call("C-0004", signals=frozenset({SignalType.BROKER_CONDUCT_ADVERSE})),
        )

        issues = _by_key(issues_to_act_on(config, [employer()], traffic, WINDOW, WINDOW, AS_OF))

        assert issues["control_exception"].references == ("C-0001",)
        assert issues["knowledge_failure"].references == ("C-0002",)
        assert issues["exit_language"].references == ("C-0003",)
        assert issues["broker_adverse"].references == ("C-0004",)


class TestHighEffort:
    def test_high_effort_is_unavailable_rather_than_zero(self, config: DashboardConfig) -> None:
        """Member effort is our composite and Stream A has not built it. A
        row reading "High member effort 0" is a false statement about the
        corpus, not a quiet one."""
        issues = _by_key(issues_to_act_on(config, [employer()], calls(5), WINDOW, WINDOW, AS_OF))

        assert issues["high_effort"].computable is False
        assert issues["high_effort"].count == 0
        assert "not a v9 field" in issues["high_effort"].unavailable_because


class TestAccounts:
    def _flagging_traffic(self, reference: str) -> tuple[CallContext, ...]:
        """Two of metric 10's four conditions: a failure-driven repeat and
        market-test language."""
        return (
            call(
                f"{reference}-1",
                employer_ref=reference,
                caller_ref=f"CB-{reference}",
                outcome=Outcome.UNRESOLVED,
                on=day(0),
            ),
            call(f"{reference}-2", employer_ref=reference, caller_ref=f"CB-{reference}", on=day(3)),
            call(
                f"{reference}-3", employer_ref=reference, intent=IntentType.MARKET_TEST, on=day(5)
            ),
        )

    def test_a_flagged_account_is_counted_once_under_its_reference(
        self, config: DashboardConfig
    ) -> None:
        traffic = self._flagging_traffic("EMP-01")

        issues = _by_key(
            issues_to_act_on(config, [employer("EMP-01")], traffic, WINDOW, WINDOW, AS_OF)
        )

        assert issues["flagged"].references == ("EMP-01",)
        assert issues["flagged"].unit == "accounts"

    def test_an_account_the_window_cannot_assess_is_not_counted(
        self, config: DashboardConfig
    ) -> None:
        """Not flagged is not the same as not at risk, which is exactly why
        an ineligible account belongs in neither column of a to-do list."""
        traffic = (call("C-0001", employer_ref="EMP-01", outcome=Outcome.UNRESOLVED),)

        issues = _by_key(
            issues_to_act_on(config, [employer("EMP-01")], traffic, WINDOW, WINDOW, AS_OF)
        )

        assert issues["flagged"].count == 0

    def test_renewing_soon_is_a_subset_of_flagged(self, config: DashboardConfig) -> None:
        """Every account on the renewal list is already on the flagged list.
        A renewal on its own is a date, not a problem."""
        traffic = self._flagging_traffic("EMP-01") + self._flagging_traffic("EMP-02")
        book = [
            employer("EMP-01", renewal_month="November"),
            employer("EMP-02", renewal_month="April"),
        ]

        issues = _by_key(issues_to_act_on(config, book, traffic, WINDOW, WINDOW, AS_OF))

        assert issues["flagged"].references == ("EMP-01", "EMP-02")
        assert issues["renew_soon"].references == ("EMP-01",)

    def test_a_renewal_month_nobody_recorded_is_not_a_distant_renewal(
        self, config: DashboardConfig
    ) -> None:
        """An unparseable month is a renewal nobody knows, and a list headed
        by a deadline is the wrong place to guess one."""
        traffic = self._flagging_traffic("EMP-01")

        issues = _by_key(
            issues_to_act_on(
                config,
                [employer("EMP-01", renewal_month="")],
                traffic,
                WINDOW,
                WINDOW,
                AS_OF,
            )
        )

        assert issues["flagged"].count == 1
        assert issues["renew_soon"].count == 0


class TestTheTwoWindows:
    def test_the_flag_is_assessed_over_its_own_window_not_the_screen_s(
        self, config: DashboardConfig
    ) -> None:
        """Metric 10 is defined over the window `dashboard.yaml` gives it.
        Assessing it over whichever period the actions screen asked for
        would restate the metric without saying so — D11, a period is not a
        window."""
        traffic = (
            call(
                "C-0001",
                caller_ref="CB-1",
                outcome=Outcome.UNRESOLVED,
                on=day(0),
            ),
            call("C-0002", caller_ref="CB-1", on=day(3)),
            call("C-0003", intent=IntentType.MARKET_TEST, on=day(5)),
        )
        # A call window that reaches none of them, and a risk window that
        # reaches all three.
        narrow = Window(start=day(40), end=day(50))

        issues = _by_key(issues_to_act_on(config, [employer()], traffic, narrow, WINDOW, AS_OF))

        assert issues["unresolved"].count == 0
        assert issues["flagged"].references == ("EMP-01",)


class TestWhereItShowsUp:
    def test_the_accounts_are_ranked_by_weight_then_by_renewal(
        self, config: DashboardConfig
    ) -> None:
        """The prototype's own order. Two accounts with the same problem are
        not equally urgent when one of them renews next month."""
        traffic = (
            call("C-0001", employer_ref="EMP-01", outcome=Outcome.UNRESOLVED),
            call("C-0002", employer_ref="EMP-01", outcome=Outcome.UNRESOLVED),
            call("C-0003", employer_ref="EMP-02", outcome=Outcome.UNRESOLVED),
            call("C-0004", employer_ref="EMP-03", outcome=Outcome.UNRESOLVED),
        )
        book = [
            employer("EMP-01", renewal_month="April"),
            employer("EMP-02", renewal_month="April"),
            employer("EMP-03", renewal_month="November"),
        ]

        issues = _by_key(issues_to_act_on(config, book, traffic, WINDOW, WINDOW, AS_OF))
        accounts = issues["unresolved"].accounts

        assert [(a.reference, a.calls) for a in accounts] == [
            ("EMP-01", 2),
            ("EMP-03", 1),
            ("EMP-02", 1),
        ]
        assert accounts[1].months_to_renewal == 2

    def test_a_call_with_no_employer_is_still_counted_but_has_no_row(
        self, config: DashboardConfig
    ) -> None:
        """The panel exists to pick an account to work on, and a row nobody
        can open is not one. The count and the rows disagreeing is the
        honest outcome, not a discrepancy."""
        traffic = (
            call("C-0001", employer_ref="EMP-01", outcome=Outcome.UNRESOLVED),
            call("C-0002", employer_ref=None, outcome=Outcome.UNRESOLVED),
        )

        issues = _by_key(
            issues_to_act_on(config, [employer("EMP-01")], traffic, WINDOW, WINDOW, AS_OF)
        )

        assert issues["unresolved"].count == 2
        assert [a.reference for a in issues["unresolved"].accounts] == ["EMP-01"]

    def test_an_unreadable_renewal_sorts_last_rather_than_first(
        self, config: DashboardConfig
    ) -> None:
        """An unknown date is not an urgent one."""
        traffic = (
            call("C-0001", employer_ref="EMP-01", outcome=Outcome.UNRESOLVED),
            call("C-0002", employer_ref="EMP-02", outcome=Outcome.UNRESOLVED),
        )
        book = [employer("EMP-01", renewal_month=""), employer("EMP-02", renewal_month="November")]

        issues = _by_key(issues_to_act_on(config, book, traffic, WINDOW, WINDOW, AS_OF))

        assert [a.reference for a in issues["unresolved"].accounts] == ["EMP-02", "EMP-01"]
        assert issues["unresolved"].accounts[1].months_to_renewal is None
