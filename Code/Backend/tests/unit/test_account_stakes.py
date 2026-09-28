"""Account facts that raise the stakes.

What these protect is the difference between a threshold the workbook states
and one we picked. Rule P-18 sets 70%, so the participation note may fire;
nothing sets a quality threshold, which is why `account_profile` has no
equivalent. A note whose number nobody can source does not belong here.
"""

from __future__ import annotations

from datetime import date

from domain.aggregation.account_stakes import (
    P18,
    account_stakes,
    months_to_renewal,
)
from domain.aggregation.call_tags import EmployerFacts

AS_OF = date(2026, 9, 28)


def _employer(
    reference: str = "EMP-1001",
    *,
    eligible: int = 165,
    enrolled: int = 112,
    participation: float | None = 0.68,
    dental: str = "ER",
    calls_per_100: float | None = 20.0,
    renewal_month: str = "Jan",
) -> EmployerFacts:
    return EmployerFacts(
        reference=reference,
        name="Park Mechanical",
        enrolled=enrolled,
        region="Bay Area",
        industry="Construction",
        renewal_month=renewal_month,
        broker_ref="BRK-1",
        eligible=eligible,
        participation=participation,
        dental_sponsorship=dental,
        calls_per_100=calls_per_100,
    )


def _stakes(employer: EmployerFacts, book: list[EmployerFacts] | None = None) -> set[str]:
    population = book if book is not None else [employer]
    return {stake.code for stake in account_stakes(employer, population, AS_OF)}


class TestParticipation:
    def test_an_account_below_the_rule_is_named_with_the_rule(self) -> None:
        """The threshold is quoted from P-18, so the note cites it. A reader
        who disagrees should be disagreeing with the workbook, not with us."""
        (stake,) = [
            s
            for s in account_stakes(_employer(), [_employer()], AS_OF)
            if s.code == "participation_below_threshold"
        ]

        assert "70%" in stake.label
        assert P18 in stake.detail
        assert "112 of 165" in stake.detail
        assert "68%" in stake.detail

    def test_voluntary_dental_is_out_of_the_rule_s_reach(self) -> None:
        """P-18 is about employer-sponsored dental. Firing on a voluntary
        plan would apply a requirement that does not exist to it."""
        assert "participation_below_threshold" not in _stakes(_employer(dental="VOL"))

    def test_no_participation_recorded_is_a_gap_not_a_failure(self) -> None:
        assert "participation_below_threshold" not in _stakes(_employer(participation=None))

    def test_meeting_the_threshold_is_not_a_finding(self) -> None:
        assert "participation_below_threshold" not in _stakes(
            _employer(participation=0.82, enrolled=135)
        )

    def test_the_rule_s_other_limb_is_honoured(self) -> None:
        """P-18 requires two enrolled *and* 70%. Calling one enrolled life
        'low participation' is arithmetic, not a finding."""
        assert "participation_below_threshold" not in _stakes(
            _employer(enrolled=1, eligible=4, participation=0.25)
        )


class TestPlannedContactRate:
    def test_a_plan_above_the_book_median_is_named_as_a_plan(self) -> None:
        """The wording has to keep this apart from the measured contact
        rate beside it: the corpus is a sample of planned volume, so the two
        are not comparable and a reader must not add them up."""
        book = [
            _employer("EMP-1001", calls_per_100=40.0),
            _employer("EMP-2", calls_per_100=10.0),
            _employer("EMP-3", calls_per_100=12.0),
        ]
        (stake,) = [
            s for s in account_stakes(book[0], book, AS_OF) if s.code == "high_contact_rate"
        ]

        assert "planned" in stake.detail.lower()
        assert "40.0" in stake.detail

    def test_a_plan_at_or_below_the_median_is_not_a_finding(self) -> None:
        book = [
            _employer("EMP-1001", calls_per_100=10.0),
            _employer("EMP-2", calls_per_100=40.0),
            _employer("EMP-3", calls_per_100=42.0),
        ]

        assert "high_contact_rate" not in {s.code for s in account_stakes(book[0], book, AS_OF)}

    def test_a_median_of_one_is_not_a_median(self) -> None:
        """Same floor the peer comparison uses, for the same reason."""
        book = [_employer("EMP-1001", calls_per_100=99.0), _employer("EMP-2")]

        assert "high_contact_rate" not in {s.code for s in account_stakes(book[0], book, AS_OF)}

    def test_the_account_is_not_in_its_own_comparison(self) -> None:
        """An account compared against a median it is itself half of would
        be told about its own number."""
        book = [
            _employer("EMP-1001", calls_per_100=30.0),
            _employer("EMP-2", calls_per_100=30.0),
            _employer("EMP-3", calls_per_100=10.0),
        ]

        # Median of the *others* is 20.0, so 30.0 is above it. Were the
        # account included the median would be 30.0 and the note would not
        # fire at all.
        assert "high_contact_rate" in {s.code for s in account_stakes(book[0], book, AS_OF)}


class TestRenewal:
    def test_a_renewal_inside_the_window_carries_the_countdown(self) -> None:
        (stake,) = [
            s
            for s in account_stakes(_employer(renewal_month="Nov"), [_employer()], AS_OF)
            if s.code == "renewal_near"
        ]

        assert "2 months" in stake.label

    def test_a_distant_renewal_says_nothing(self) -> None:
        assert "renewal_near" not in _stakes(_employer(renewal_month="Jun"))

    def test_this_month_is_not_twelve_months_away(self) -> None:
        """A forward search that wrapped would turn 'renews this month' into
        the least urgent account in the book."""
        assert months_to_renewal("Sep", AS_OF) == 0

    def test_an_unparseable_month_is_none_rather_than_a_guess(self) -> None:
        assert months_to_renewal("Quarter 3", AS_OF) is None
