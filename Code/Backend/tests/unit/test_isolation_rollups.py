"""The "By region" and "By broker" tables on `/hierarchy`.

What these protect is mostly what the rows count rather than how they
count it: a region is every account reference data puts in it, not every
account that rang; a broker's denominator comes from the Broker Master
sheet and never from the calls beside it; and the flag is assessed over
metric 10's window rather than over whichever period the screen asked for.
"""

from __future__ import annotations

import pytest

from domain.aggregation.call_tags import CallContext, Window
from domain.aggregation.isolation import broker_rows, complaint_ownership, region_rows
from domain.dashboard_config import DashboardConfig
from domain.value_objects.broker_sentiment import BrokerSentiment
from domain.value_objects.complaint import Complaint
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.intent_type import IntentType
from domain.value_objects.outcome import Outcome
from infrastructure.config.dashboard_config import load_dashboard_config
from infrastructure.config.paths import DEFAULT_CONFIG_DIR
from tests.fixtures.tagged_calls import WINDOW, broker, call, day, employer


@pytest.fixture(scope="module")
def config() -> DashboardConfig:
    return load_dashboard_config(DEFAULT_CONFIG_DIR / "dashboard.yaml")


def _flagging(reference: str) -> tuple[CallContext, ...]:
    """Two of metric 10's four conditions: a failure-driven repeat, and
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
        call(f"{reference}-3", employer_ref=reference, intent=IntentType.MARKET_TEST, on=day(5)),
    )


class TestRegionRows:
    def test_a_region_counts_every_account_in_it_not_every_one_that_rang(
        self, config: DashboardConfig
    ) -> None:
        """A region where four of sixteen accounts rang is not a
        four-account region, and a table that said so would make the quiet
        ones disappear."""
        book = [
            employer("EMP-01", region="North"),
            employer("EMP-02", region="North"),
            employer("EMP-03", region="South"),
        ]
        traffic = (call("C-0001", employer_ref="EMP-01"),)

        rows = {row.region: row for row in region_rows(config, book, traffic, WINDOW, WINDOW)}

        assert rows["North"].accounts == 2
        assert rows["North"].calls == 1
        assert rows["South"].accounts == 1
        assert rows["South"].calls == 0

    def test_unresolved_is_counted_beside_the_calls(self, config: DashboardConfig) -> None:
        traffic = (
            call("C-0001", employer_ref="EMP-01", outcome=Outcome.UNRESOLVED),
            call("C-0002", employer_ref="EMP-01"),
        )

        (row,) = region_rows(config, [employer("EMP-01", region="North")], traffic, WINDOW, WINDOW)

        assert (row.calls, row.unresolved) == (2, 1)

    def test_the_flag_is_assessed_over_its_own_window(self, config: DashboardConfig) -> None:
        """D11: a period is not a window. The screen's period moves the
        call counts and must not move metric 10."""
        traffic = _flagging("EMP-01")
        narrow = Window(start=day(40), end=day(50))

        (row,) = region_rows(
            config,
            [employer("EMP-01", region="North")],
            traffic,
            narrow,
            WINDOW,
        )

        assert row.calls == 0
        assert row.flagged == 1

    def test_regions_are_ordered_by_flagged_then_by_calls(self, config: DashboardConfig) -> None:
        book = [
            employer("EMP-01", region="North"),
            employer("EMP-02", region="South"),
            employer("EMP-03", region="West"),
        ]
        traffic = (
            *_flagging("EMP-02"),
            call("C-0100", employer_ref="EMP-03"),
            call("C-0101", employer_ref="EMP-03"),
        )

        rows = region_rows(config, book, traffic, WINDOW, WINDOW)

        assert [row.region for row in rows] == ["South", "West", "North"]


class TestBrokerRows:
    def test_the_denominator_is_the_broker_sheet_s_and_not_a_count_of_calls(
        self, config: DashboardConfig
    ) -> None:
        """The whole reason the two sit side by side: `groups_in_book`
        comes from reference data, so the denominator is not built out of
        the numerator."""
        book = [employer("EMP-01", broker_ref="BRK-01")]
        traffic = (call("C-0001", employer_ref="EMP-01", broker_of_record_ref="BRK-01"),)

        (row,) = broker_rows(
            config, [broker("BRK-01", groups_in_book=9)], book, traffic, WINDOW, WINDOW
        )

        assert row.groups_in_book == 9
        assert row.calls == 1

    def test_a_small_broker_is_not_filtered_out_of_a_table_with_no_rate_in_it(
        self, config: DashboardConfig
    ) -> None:
        """`ranked_book_friction` keeps a 150-lives floor because it
        publishes a rate. This publishes counts, so the floor would only
        hide the finding the pattern test exists to make."""
        book = [employer("EMP-01", broker_ref="BRK-01", enrolled=4)]
        traffic = (
            call(
                "C-0001",
                employer_ref="EMP-01",
                broker_of_record_ref="BRK-01",
                broker_named="BRK-01",
                broker_sentiment=BrokerSentiment.ADVERSE,
            ),
        )

        rows = broker_rows(config, [broker("BRK-01", book_lives=4)], book, traffic, WINDOW, WINDOW)

        assert [row.broker_ref for row in rows] == ["BRK-01"]
        assert rows[0].adverse_mentions == 1

    def test_adverse_mentions_are_counted_with_the_employers_behind_them(
        self, config: DashboardConfig
    ) -> None:
        """The pattern test needs both numbers — three mentions across two
        employers — so a row showing one without the other cannot be read
        against it."""
        book = [
            employer("EMP-01", broker_ref="BRK-01"),
            employer("EMP-02", broker_ref="BRK-01"),
        ]
        traffic = tuple(
            call(
                f"C-000{index}",
                employer_ref=reference,
                broker_of_record_ref="BRK-01",
                broker_named="BRK-01",
                broker_sentiment=BrokerSentiment.ADVERSE,
            )
            for index, reference in enumerate(("EMP-01", "EMP-01", "EMP-02"), start=1)
        )

        (row,) = broker_rows(config, [broker("BRK-01")], book, traffic, WINDOW, WINDOW)

        assert (row.adverse_mentions, row.adverse_employers) == (3, 2)
        assert row.pattern_fires is True

    def test_a_broker_holding_nothing_in_scope_has_no_row(self, config: DashboardConfig) -> None:
        """Filters slice; they do not invent. A broker whose whole book is
        outside the current filters is absent, not present at zero."""
        rows = broker_rows(
            config,
            [broker("BRK-01"), broker("BRK-02")],
            [employer("EMP-01", broker_ref="BRK-01")],
            (),
            WINDOW,
            WINDOW,
        )

        assert [row.broker_ref for row in rows] == ["BRK-01"]

    def test_brokers_are_ordered_by_adverse_mentions_first(self, config: DashboardConfig) -> None:
        book = [
            employer("EMP-01", broker_ref="BRK-01"),
            employer("EMP-02", broker_ref="BRK-02"),
        ]
        traffic = (
            call("C-0001", employer_ref="EMP-02", broker_of_record_ref="BRK-02"),
            call("C-0002", employer_ref="EMP-02", broker_of_record_ref="BRK-02"),
            call(
                "C-0003",
                employer_ref="EMP-01",
                broker_of_record_ref="BRK-01",
                broker_named="BRK-01",
                broker_sentiment=BrokerSentiment.ADVERSE,
            ),
        )

        rows = broker_rows(
            config, [broker("BRK-01"), broker("BRK-02")], book, traffic, WINDOW, WINDOW
        )

        assert [row.broker_ref for row in rows] == ["BRK-01", "BRK-02"]


class TestComplaintOwnership:
    def test_the_denominator_is_complaints_and_not_calls(self) -> None:
        """A different figure from the complaint rate, which divides by
        everyone who rang. This asks how much of the complaint load is
        ours to fix."""
        traffic = (
            call("C-0001", complaint_to=ComplaintAttribution.CHOICE),
            call("C-0002", complaint_to=ComplaintAttribution.CARRIER),
            call("C-0003"),
        )

        ownership = complaint_ownership(traffic, WINDOW)

        assert (ownership.ours, ownership.total) == (1, 2)

    def test_every_complaint_made_is_attributed_to_somebody(self) -> None:
        """`ours` and `total` can be read against each other because the
        rest is always another party's, never an unattributed remainder:
        `Complaint` refuses to exist present and unattributed."""
        with pytest.raises(ValueError, match="must carry an attribution"):
            Complaint(present=True, attributed_to=None)
