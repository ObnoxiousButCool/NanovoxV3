"""Metric 10 and the ten indicator families (B4).

The tests that matter most here are about what the flag is *not*: not a
band, not a prediction, and not something the indicator families can reach.
The prototype renders a four-level band off a count of families, so every
one of those is a live way for this to drift back.
"""

from __future__ import annotations

from datetime import date

import pytest

from domain.aggregation.call_tags import Window
from domain.aggregation.figure import WithheldReason
from domain.aggregation.indicators import (
    FAMILIES,
    assessed,
    first_indicator_on,
    newly_flagged,
    observe,
    observed,
    unavailable,
)
from domain.aggregation.risk_flag import (
    Condition,
    RiskAssessment,
    assess,
    exposure,
    flagged_share,
    flagged_share_n_caveat,
    months_until,
)
from domain.dashboard_config import DashboardConfig
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.control_exception_type import ControlExceptionType
from domain.value_objects.escalation import Escalation
from domain.value_objects.intent_type import IntentType
from domain.value_objects.outcome import Outcome
from domain.value_objects.signal_type import SignalType
from infrastructure.config.dashboard_config import load_dashboard_config
from infrastructure.config.paths import DEFAULT_CONFIG_DIR
from tests.fixtures.tagged_calls import WINDOW, call, calls, day, employer


@pytest.fixture(scope="module")
def config() -> DashboardConfig:
    return load_dashboard_config(DEFAULT_CONFIG_DIR / "dashboard.yaml")


# --- Eligibility is not the same as safety ---------------------------------


def test_an_employer_under_three_calls_is_ineligible_not_unflagged(
    config: DashboardConfig,
) -> None:
    """At batch-1 volume most of the 92 employers with calls have exactly
    one. A page that renders them as "not flagged" is ninety reassuring rows
    about accounts nobody assessed.
    """
    assessment = assess(config, employer(), calls(2), WINDOW)

    assert assessment.eligible is False
    assert assessment.flagged is False
    assert "Not eligible" in assessment.state
    assert "not the same as no risk" in assessment.state.lower()


def test_an_eligible_employer_meeting_two_conditions_is_flagged(
    config: DashboardConfig,
) -> None:
    traffic = (
        call("C-0001", caller_ref="CB-1", outcome=Outcome.UNRESOLVED, on=day(0)),
        call("C-0002", caller_ref="CB-1", on=day(3)),
        call("C-0003", intent=IntentType.MARKET_TEST, on=day(5)),
    )

    assessment = assess(config, employer(), traffic, WINDOW)

    assert assessment.eligible is True
    assert assessment.conditions_met == 2
    assert assessment.flagged is True


def test_one_condition_is_not_enough(config: DashboardConfig) -> None:
    traffic = calls(5, intent=IntentType.MARKET_TEST)

    assessment = assess(config, employer(), traffic, WINDOW)

    assert assessment.conditions_met == 1
    assert assessment.flagged is False
    assert "Not flagged" in assessment.state


def test_a_flag_below_ten_calls_is_shown_but_not_quotable(config: DashboardConfig) -> None:
    """The gap between 3 and 10 is why these are two numbers."""
    traffic = (
        call("C-0001", caller_ref="CB-1", outcome=Outcome.UNRESOLVED, on=day(0)),
        call("C-0002", caller_ref="CB-1", on=day(3)),
        call("C-0003", intent=IntentType.MARKET_TEST, on=day(5)),
    )

    assessment = assess(config, employer(), traffic, WINDOW)

    assert assessment.flagged is True
    assert assessment.quotable is False
    assert "Too few calls to quote" in assessment.state


def test_the_flag_is_never_described_as_a_prediction(config: DashboardConfig) -> None:
    """No termination outcomes exist in this dataset to validate one."""
    traffic = (
        call("C-0001", caller_ref="CB-1", outcome=Outcome.UNRESOLVED, on=day(0)),
        call("C-0002", caller_ref="CB-1", on=day(3)),
        call("C-0003", intent=IntentType.MARKET_TEST, on=day(5)),
    )

    state = assess(config, employer(), traffic, WINDOW).state

    assert "Not a prediction" in state


def test_there_is_no_band_anywhere_on_an_assessment(config: DashboardConfig) -> None:
    """D2's whole point. The prototype renders High/Elevated/Watch/None; the
    workbook wins, and nothing here exposes a level.
    """
    assessment = assess(config, employer(), calls(5), WINDOW)

    assert not hasattr(assessment, "band")
    assert not hasattr(assessment, "level")
    assert isinstance(assessment.flagged, bool)


# --- The four conditions ---------------------------------------------------


def test_market_test_fires_but_expansion_does_not(config: DashboardConfig) -> None:
    """Expansion is a commercial opportunity, not a risk. Widening this
    would flag accounts that said they wanted to buy more.
    """
    wants_more = assess(config, employer(), calls(5, intent=IntentType.EXPANSION), WINDOW)
    shopping = assess(config, employer(), calls(5, intent=IntentType.MARKET_TEST), WINDOW)

    assert wants_more.conditions_met == 0
    assert shopping.conditions_met == 1


def test_a_rising_complaint_rate_is_compared_as_a_rate_not_a_count(
    config: DashboardConfig,
) -> None:
    """An employer whose calls doubled and whose complaints doubled has not
    deteriorated.
    """
    steady = (
        call("C-0001", on=day(0), complaint_to=ComplaintAttribution.CHOICE),
        call("C-0002", on=day(1)),
        call("C-0003", on=day(60), complaint_to=ComplaintAttribution.CHOICE),
        call("C-0004", on=day(61), complaint_to=ComplaintAttribution.CHOICE),
        call("C-0005", on=day(62)),
        call("C-0006", on=day(63)),
    )

    assessment = assess(config, employer(), steady, WINDOW)
    rising = next(c for c in assessment.conditions if c.code == "complaint_rate_rising")

    assert rising.met is False, "50% then 50% is not a rise"


def test_the_renewal_condition_needs_all_three_parts_on_one_call(
    config: DashboardConfig,
) -> None:
    """Ours, unresolved, and close to renewal. A call meeting two of three
    is not this condition, and treating it as one flags most of the book.
    """
    # Window ends 28 Sep 2026; a January renewal is ~95 days out, so nothing
    # inside the 90-day window. Same calls, an October renewal, and it fires.
    traffic = calls(5, outcome=Outcome.UNRESOLVED, complaint_to=ComplaintAttribution.CHOICE)

    far = assess(config, employer(renewal_month="January"), traffic, WINDOW)
    near = assess(config, employer(renewal_month="October"), traffic, WINDOW)

    assert _condition(far, "choice_unresolved_near_renewal").met is False
    assert _condition(near, "choice_unresolved_near_renewal").met is True


def test_an_unresolved_call_blamed_on_the_carrier_is_not_the_renewal_condition(
    config: DashboardConfig,
) -> None:
    traffic = calls(5, outcome=Outcome.UNRESOLVED, complaint_to=ComplaintAttribution.CARRIER)

    assessment = assess(config, employer(renewal_month="October"), traffic, WINDOW)

    assert _condition(assessment, "choice_unresolved_near_renewal").met is False


def test_an_unparseable_renewal_month_fires_nothing_rather_than_defaulting(
    config: DashboardConfig,
) -> None:
    """Defaulting to January would quietly flag every account whose renewal
    reference data does not carry.
    """
    traffic = calls(5, outcome=Outcome.UNRESOLVED, complaint_to=ComplaintAttribution.CHOICE)

    assessment = assess(config, employer(renewal_month="Quartember"), traffic, WINDOW)

    assert _condition(assessment, "choice_unresolved_near_renewal").met is False


def test_a_flagged_assessment_opens_its_evidence(config: DashboardConfig) -> None:
    traffic = (
        call("C-0001", caller_ref="CB-1", outcome=Outcome.UNRESOLVED, on=day(0)),
        call("C-0002", caller_ref="CB-1", on=day(3)),
        call("C-0003", intent=IntentType.MARKET_TEST, on=day(5)),
    )

    assessment = assess(config, employer(), traffic, WINDOW)

    assert assessment.evidence == ("C-0001", "C-0003")


# --- Exposure (insight 14) -------------------------------------------------


def test_exposure_sums_lives_and_premium_and_calls_itself_exposure(
    config: DashboardConfig,
) -> None:
    """ "Presented as exposure, never as expected loss — there is no
    probability to apply to it."
    """
    flagging = (
        call("C-0001", caller_ref="CB-1", outcome=Outcome.UNRESOLVED, on=day(0)),
        call("C-0002", caller_ref="CB-1", on=day(3)),
        call("C-0003", intent=IntentType.MARKET_TEST, on=day(5)),
    )
    employers = [employer("EMP-01", enrolled=120), employer("EMP-02", enrolled=900)]

    assessments = [assess(config, employers[0], flagging, WINDOW)]
    total = exposure(assessments, employers)

    assert total.employers == ("EMP-01",)
    assert total.lives == 120
    assert "not expected loss" in total.caveat


def test_the_flagged_share_divides_by_eligible_employers_not_all_of_them(
    config: DashboardConfig,
) -> None:
    """Dividing by the whole book buries the finding under the ninety
    accounts nobody could assess, and gives a reassuring small percentage.
    """
    flagging = (
        call("C-0001", caller_ref="CB-1", outcome=Outcome.UNRESOLVED, on=day(0)),
        call("C-0002", caller_ref="CB-1", on=day(3)),
        call("C-0003", intent=IntentType.MARKET_TEST, on=day(5)),
    )
    eligible_flagged = assess(config, employer("EMP-01"), flagging, WINDOW)
    eligible_clear = assess(config, employer("EMP-02"), calls(5, employer_ref="EMP-02"), WINDOW)
    ineligible = assess(config, employer("EMP-03"), calls(1, employer_ref="EMP-03"), WINDOW)

    figure = flagged_share(config, [eligible_flagged, eligible_clear, ineligible])

    assert figure.value == pytest.approx(0.5), "1 of 2 eligible, not 1 of 3"


def test_flagged_share_says_so_when_n_is_not_its_own_denominator(
    config: DashboardConfig,
) -> None:
    """`n` is the flagged accounts' evidence calls, which is not the share's
    denominator (eligible employers). A reader who assumes the two match, as
    they do for every other figure, needs telling when they do not.
    """
    flagging = (
        call("C-0001", caller_ref="CB-1", outcome=Outcome.UNRESOLVED, on=day(0)),
        call("C-0002", caller_ref="CB-1", on=day(3)),
        call("C-0003", intent=IntentType.MARKET_TEST, on=day(5)),
    )
    eligible_flagged = assess(config, employer("EMP-01"), flagging, WINDOW)
    eligible_clear_a = assess(config, employer("EMP-02"), calls(5, employer_ref="EMP-02"), WINDOW)
    eligible_clear_b = assess(config, employer("EMP-03"), calls(5, employer_ref="EMP-03"), WINDOW)

    figure = flagged_share(config, [eligible_flagged, eligible_clear_a, eligible_clear_b])

    assert figure.n == 2, "the flagged account's evidence calls, not the 3 eligible employers"
    assert any("assessedCount" in caveat for caveat in figure.caveats)
    assert any("3 eligible employer" in caveat for caveat in figure.caveats)


def test_flagged_share_n_caveat_is_quiet_when_the_counts_coincide() -> None:
    """Computed from the numbers — it only fires when the counts actually
    disagree, not every time the figure is published.
    """
    assert flagged_share_n_caveat(eligible=5, evidence_calls=5) is None


def test_flagged_share_n_caveat_names_both_counts_and_points_at_the_fix() -> None:
    caveat = flagged_share_n_caveat(eligible=50, evidence_calls=54)

    assert caveat is not None
    assert "54" in caveat
    assert "50 eligible employer" in caveat
    assert "assessedCount" in caveat


def test_a_book_where_nobody_is_eligible_is_withheld_not_zero(
    config: DashboardConfig,
) -> None:
    quiet = [assess(config, employer(), calls(1), WINDOW)]

    figure = flagged_share(config, quiet)

    assert figure.withheld_reason is WithheldReason.NOT_ELIGIBLE
    assert figure.value is None


# --- The ten indicator families --------------------------------------------


def test_there_are_exactly_ten_families() -> None:
    assert len(FAMILIES) == 10
    assert len({family.code for family in FAMILIES}) == 10


def test_the_families_do_not_feed_the_flag(config: DashboardConfig) -> None:
    """Informational, never inputs. An employer tripping many families but
    only one of metric 10's conditions is not flagged — which is exactly the
    case the prototype's band would have rendered as High.
    """
    traffic = calls(
        6,
        outcome=Outcome.UNRESOLVED,
        complaint_to=ComplaintAttribution.CHOICE,
        control_exceptions=frozenset({ControlExceptionType.NO_RECORDING_DISCLOSURE}),
        signals=frozenset({SignalType.VERIFICATION_FAILURE}),
        escalation=Escalation(triggered=True, handled=False),
        knowledge_failure_rule="C-12",
    )

    assessment = assess(config, employer(renewal_month="January"), traffic, WINDOW)
    families = observed(observe(config, employer(renewal_month="January"), traffic, WINDOW))

    assert len(families) >= 5
    assert assessment.conditions_met < config.risk_flag.flag_threshold
    assert assessment.flagged is False


def test_a_family_needs_the_floor_and_the_rate_not_either_alone(
    config: DashboardConfig,
) -> None:
    """Two hits out of ninety calls is a trickle, not a condition; two out of
    four is a condition on a sample too thin to say so.
    """
    thin = calls(4, outcome=Outcome.UNRESOLVED)
    diluted = (
        *calls(2, prefix="U", outcome=Outcome.UNRESOLVED),
        *calls(88, prefix="R", outcome=Outcome.RESOLVED),
    )

    assert observed(observe(config, employer(), thin, WINDOW)) == ()
    assert not any(
        o.family.code == "unresolved"
        for o in observed(observe(config, employer(), diluted, WINDOW))
    )


def test_a_family_over_both_gates_is_observed(config: DashboardConfig) -> None:
    traffic = (
        *calls(3, prefix="U", outcome=Outcome.UNRESOLVED),
        *calls(3, prefix="R", outcome=Outcome.RESOLVED),
    )

    codes = {o.family.code for o in observed(observe(config, employer(), traffic, WINDOW))}

    assert "unresolved" in codes


def test_high_effort_is_unavailable_rather_than_zero(config: DashboardConfig) -> None:
    """Member effort is a derived composite Stream A has not built. Showing
    it as zero would assert this account had no high-effort calls.
    """
    unavailable_families = unavailable(observe(config, employer(), calls(10), WINDOW))

    assert [o.family.code for o in unavailable_families] == ["high_effort"]
    assert unavailable_families[0].rate is None
    assert "not the same as it being absent" in unavailable_families[0].family.unavailable_because


def test_the_knowledge_failure_family_does_not_blame_the_agent() -> None:
    """The prototype labels this "Agent stated a published rule incorrectly",
    which is the `knowledge_error` signal's definition. D7 is open on exactly
    that conflation and carrying the wording across would settle it in code.
    """
    family = next(f for f in FAMILIES if f.code == "knowledge_failure")

    assert "agent" not in family.label.lower()


def test_an_account_under_the_floor_is_unassessed_rather_than_clear(
    config: DashboardConfig,
) -> None:
    """The defect this exists to stop.

    Three calls is under `min_employer_calls`, so no family can fire whatever
    its hits — and two of these three carry a complaint. Reporting that as
    nought observed says the account is clean on the strength of never having
    looked, which is the withheld-is-not-zero mistake one level down.
    """
    thin = (
        *calls(2, prefix="U", outcome=Outcome.UNRESOLVED),
        *calls(1, prefix="R", outcome=Outcome.RESOLVED),
    )

    observations = observe(config, employer(), thin, WINDOW)

    assert assessed(observations) is False
    assert all(o.assessable is False for o in observations)
    # The hits are still carried. They are real calls, and a page saying
    # "2 of 3 calls, not assessed" is true where "not observed" is not.
    unresolved = next(o for o in observations if o.family.code == "unresolved")
    assert unresolved.hits == 2
    assert unresolved.observed is False
    assert "not the same as none being present" in unresolved.unassessable_because


def test_an_account_over_the_floor_that_fires_nothing_is_a_finding(
    config: DashboardConfig,
) -> None:
    """The other nought, and it means the opposite. The families were tested
    against this account and none of them cleared — which is something a
    reader may act on, unlike the nought above."""
    quiet = calls(8, outcome=Outcome.RESOLVED)

    observations = observe(config, employer(), quiet, WINDOW)

    assert assessed(observations) is True
    assert observed(observations) == ()
    assert all(o.unassessable_because == "" for o in observations)


def test_the_unassessable_reason_carries_the_configured_floor(
    config: DashboardConfig,
) -> None:
    """Written once from config rather than phrased by each caller: the floor
    is the weakest number in `dashboard.yaml` and is expected to move, and a
    page with "five" hard-coded into a sentence goes quietly wrong the day it
    does."""
    observations = observe(config, employer(), calls(2), WINDOW)

    reason = observations[0].unassessable_because
    assert str(config.indicators.min_employer_calls) in reason
    assert "2 calls" in reason


def test_every_family_is_returned_even_when_it_did_not_fire(
    config: DashboardConfig,
) -> None:
    """A list of only the families that fired cannot tell a reader whether
    the rest were checked and clear, or never checked.
    """
    observations = observe(config, employer(), calls(10), WINDOW)

    assert len(observations) == 10


def _condition(assessment: RiskAssessment, code: str) -> Condition:
    return next(c for c in assessment.conditions if c.code == code)


def test_an_employer_with_no_calls_has_no_indicator_rates(config: DashboardConfig) -> None:
    """A rate over zero calls is undefined, not zero — and the account page
    for a silent employer is exactly where a spurious 0% would appear.
    """
    observations = observe(config, employer("EMP-99"), (), WINDOW)

    assert all(o.rate is None for o in observations)
    assert all(o.observed is False for o in observations)


class TestTheRenewalMonthAsReferenceDataWritesIt:
    """The corpus stores "Jan", not "January".

    Every test above uses the long form, which is how this went unnoticed:
    the fourth condition resolved nothing at all against the real book, and
    every renewal sorted as unknown.
    """

    def test_the_short_form_reference_data_uses_resolves(self) -> None:
        assert months_until("Jan", date(2026, 9, 28)) == 4
        assert months_until("Nov", date(2026, 9, 28)) == 2

    def test_the_long_form_still_resolves(self) -> None:
        assert months_until("January", date(2026, 9, 28)) == 4
        assert months_until("october", date(2026, 9, 28)) == 1

    def test_this_month_is_nearest_rather_than_furthest(self) -> None:
        """A sort key is not a date range. An account renewing this month
        belongs at the top of a list ordered by urgency."""
        assert months_until("Sep", date(2026, 9, 28)) == 0

    def test_a_month_nobody_recorded_stays_unknown(self) -> None:
        assert months_until("", date(2026, 9, 28)) is None
        assert months_until("Quartember", date(2026, 9, 28)) is None


# --- Newly flagged: the first indicator, not the flag -----------------------


def test_newly_flagged_counts_an_account_whose_first_indicator_is_recent() -> None:
    """The tile asks who is new to the list, not who is on it."""
    # WINDOW is 85 days, so the last of three slices starts on day 56.
    recent = [
        call("C-1", on=day(60), employer_ref="EMP-NEW", outcome=Outcome.UNRESOLVED),
        call("C-2", on=day(70), employer_ref="EMP-NEW"),
    ]

    result = newly_flagged(recent, WINDOW)

    assert result is not None
    assert result.employers == ("EMP-NEW",)
    assert result.count == 1
    assert result.since == day(56)


def test_an_account_whose_first_indicator_is_old_is_not_newly_flagged() -> None:
    """An account that has been on the list all quarter is not new to it,
    however many indicators it has raised since."""
    long_standing = [
        call("C-1", on=day(2), employer_ref="EMP-OLD", outcome=Outcome.UNRESOLVED),
        call("C-2", on=day(70), employer_ref="EMP-OLD", outcome=Outcome.UNRESOLVED),
    ]

    result = newly_flagged(long_standing, WINDOW)

    assert result is not None
    assert result.employers == ()


def test_an_account_with_no_indicator_at_all_is_not_newly_flagged() -> None:
    """Unremarkable calls are not a first anything."""
    quiet = [call("C-1", on=day(60), employer_ref="EMP-QUIET")]

    result = newly_flagged(quiet, WINDOW)

    assert result is not None
    assert result.employers == ()


def test_first_indicator_reads_the_same_families_observe_does() -> None:
    """One definition of "an indicator" on this screen. A family `observe`
    counts and this did not would make the tile disagree with the table
    underneath it."""
    assert first_indicator_on([call("C-1", on=day(3))]) is None
    assert first_indicator_on([call("C-1", on=day(3), outcome=Outcome.UNRESOLVED)]) == day(3)
    assert first_indicator_on(
        [call("C-1", on=day(4), signals=frozenset({SignalType.BROKER_CONDUCT_ADVERSE}))]
    ) == day(4)


def test_a_window_too_short_to_slice_gives_absent_not_nought() -> None:
    """A window that cannot be cut has not told anyone that nobody is new."""
    single_day = Window(start=day(0), end=day(0))

    assert newly_flagged([call("C-1", on=day(0), outcome=Outcome.UNRESOLVED)], single_day) is None
