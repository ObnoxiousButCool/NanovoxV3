"""The nine aggregation groups, against fixtures derived from the schema.

Each test names the rule it protects. The ones worth reading are the
negative cases — the peer median that must not fold in a withheld rate, the
components that must not be summed, the rate that must not be computed for a
small book — because those are the mistakes that produce a number rather
than an error.
"""

from __future__ import annotations

import pytest

from domain.aggregation.agent_events import agent_events, agent_quality, control_exception_rates
from domain.aggregation.broker_friction import broker_friction, ranked_book_friction
from domain.aggregation.contact_rate import peer_comparison
from domain.aggregation.demand import (
    complaint_attributed_to_choice,
    cost_to_serve,
    self_inflicted_demand,
)
from domain.aggregation.exec_scorecard import escalation_integrity_pair, exec_scorecard
from domain.aggregation.figure import EpistemicClass, WithheldReason
from domain.aggregation.isolation import (
    broker_pattern,
    drill_tree,
    region_category_matrix,
    systemic_categories,
)
from domain.aggregation.repeat_contact import (
    exposed_unresolved,
    failure_driven_repeats,
    first_contact_resolutions,
    repeats,
)
from domain.aggregation.rules import (
    RuleFacts,
    failures_by_area,
    failures_by_layer,
    failures_by_provenance,
    failures_by_rule,
    failures_by_touchpoint,
)
from domain.aggregation.touchpoints import (
    enrolment_promise_gaps,
    touchpoint_ranking,
    unattributed_calls,
)
from domain.aggregation.withheld import WITHHELD_PANELS
from domain.dashboard_config import DashboardConfig
from domain.value_objects.category import Category
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.control_exception_type import ControlExceptionType
from domain.value_objects.escalation import Escalation
from domain.value_objects.intent_type import IntentType
from domain.value_objects.outcome import Outcome
from domain.value_objects.rule_confidence import RuleConfidence
from domain.value_objects.rule_layer import RuleLayer
from domain.value_objects.signal_type import SignalType
from infrastructure.config.dashboard_config import load_dashboard_config
from infrastructure.config.paths import DEFAULT_CONFIG_DIR
from tests.fixtures.tagged_calls import WINDOW, broker, call, calls, day, employer


@pytest.fixture(scope="module")
def config() -> DashboardConfig:
    """The shipped config, not a fixture one — the thresholds are the point."""
    return load_dashboard_config(DEFAULT_CONFIG_DIR / "dashboard.yaml")


# --- Group 1: peer contact rate --------------------------------------------


def test_an_employer_is_compared_against_its_own_size_band(config: DashboardConfig) -> None:
    mine = employer("EMP-01", enrolled=50)
    peers = [mine, employer("EMP-02", enrolled=60), employer("EMP-99", enrolled=5_000)]
    traffic = (
        *calls(40, prefix="A", employer_ref="EMP-01"),
        *calls(40, prefix="B", employer_ref="EMP-02"),
        *calls(40, prefix="Z", employer_ref="EMP-99"),
    )

    comparison = peer_comparison(config, mine, peers, traffic, WINDOW)

    assert comparison.band is not None
    assert comparison.band.label == "25-74 lives"
    assert comparison.peers == 1, "only EMP-02 shares the band; EMP-99 is in 200+"


def test_a_withheld_peer_rate_is_left_out_of_the_median_not_counted_as_zero(
    config: DashboardConfig,
) -> None:
    """The withheld-is-not-zero mistake one level up, where it is far harder
    to see: a suppressed peer folded in at zero drags the median down and
    makes every employer in a thin band look worse than its peers.
    """
    mine = employer("EMP-01", enrolled=50)
    quiet_peer = employer("EMP-02", enrolled=60)
    traffic = (
        *calls(40, prefix="A", employer_ref="EMP-01"),
        *calls(3, prefix="B", employer_ref="EMP-02"),
    )

    comparison = peer_comparison(config, mine, [mine, quiet_peer], traffic, WINDOW)

    assert comparison.peers == 0
    assert comparison.peer_median is None
    assert comparison.difference is None, "no comparison is not the same as no difference"


def test_an_employer_is_excluded_from_its_own_peer_median(config: DashboardConfig) -> None:
    """Comparing a figure against a set containing itself pulls the result
    toward zero, hardest in the small bands where it is already weakest.
    """
    # Equal enrolment, so the only thing separating the two rates is call
    # volume and the expected difference is exactly +100%.
    mine = employer("EMP-01", enrolled=50)
    peer = employer("EMP-02", enrolled=50)
    traffic = (
        *calls(80, prefix="A", employer_ref="EMP-01"),
        *calls(40, prefix="B", employer_ref="EMP-02"),
    )

    comparison = peer_comparison(config, mine, [mine, peer], traffic, WINDOW)

    assert comparison.peers == 1
    assert comparison.difference == pytest.approx(1.0), "double the peer's rate"


# --- Group 2: isolation ----------------------------------------------------


def test_the_drill_tree_keeps_employers_that_never_called() -> None:
    """A tree that drops them makes a quiet region look like a small one."""
    employers = [
        employer("EMP-01", region="North", broker_ref="BRK-01"),
        employer("EMP-02", region="South", broker_ref="BRK-02"),
    ]

    tree = drill_tree(employers, calls(3, employer_ref="EMP-01"), WINDOW)

    assert [node.region for node in tree] == ["North", "South"]
    assert tree[1].calls == 0


def test_the_matrix_shows_every_category_in_every_region_including_zero() -> None:
    """ "A dark column is book-wide, a dark cell is local" only works if the
    columns line up, which a sparse matrix destroys.
    """
    employers = [employer("EMP-01", region="North"), employer("EMP-02", region="South")]

    matrix = region_category_matrix(employers, calls(3, employer_ref="EMP-01"), WINDOW)

    assert len(matrix) == 2
    for _region, row in matrix:
        assert len(row) == len(Category)


def test_a_category_present_in_every_region_is_named_systemic() -> None:
    employers = [employer("EMP-01", region="North"), employer("EMP-02", region="South")]
    traffic = (
        call("C-0001", employer_ref="EMP-01", category=Category.BILLING_AND_PREMIUM),
        call("C-0002", employer_ref="EMP-02", category=Category.BILLING_AND_PREMIUM),
        call("C-0003", employer_ref="EMP-01", category=Category.PROVIDER_NETWORK),
    )

    matrix = region_category_matrix(employers, traffic, WINDOW)

    assert systemic_categories(matrix) == (Category.BILLING_AND_PREMIUM,)


# --- Group 3: agent events -------------------------------------------------


def test_agent_events_count_knowledge_error_not_knowledge_failure(
    config: DashboardConfig,
) -> None:
    """D7. The signal is the agent-conduct event; schema field 8's tag is a
    different thing the workbook contradicts itself about, and it is never
    attributed to an agent.
    """
    traffic = (
        call("C-0001", signals=frozenset({SignalType.KNOWLEDGE_ERROR})),
        call("C-0002", knowledge_failure_rule="C-12"),
    )

    events = agent_events(config, "AG-01", traffic, WINDOW)

    assert events.knowledge_errors == ("C-0001",)


def test_agent_quality_reports_a_range_with_a_caveat_not_a_ranking() -> None:
    traffic = (
        call("C-0001", quality_score=91),
        call("C-0002", quality_score=44),
        call("C-0003", quality_score=70),
    )

    quality = agent_quality("AG-01", traffic, WINDOW)

    assert quality.median_score == 70
    assert (quality.lowest, quality.highest) == (44, 91)
    assert "not a ranking" in quality.caveat


def test_control_exceptions_are_reported_by_type_never_blended(
    config: DashboardConfig,
) -> None:
    """ "Report by exception type, not as one blended number." A single
    compliance rate hides which control failed, which is the fixable part.
    """
    rates = control_exception_rates(config, calls(40), WINDOW)

    assert [exception for exception, _ in rates] == list(ControlExceptionType)


# --- Group 4: rules --------------------------------------------------------


def _rule(
    reference: str, layer: RuleLayer = RuleLayer.CARRIER, area: str = "Waiting periods"
) -> RuleFacts:
    return RuleFacts(
        reference=reference, layer=layer, area=area, confidence=RuleConfidence.VERIFIED
    )


def test_rules_are_ranked_by_call_count_and_never_carry_a_rate() -> None:
    """Metric 8's build note asks for "a list of knowledge base articles to
    rewrite, ranked by call count". A per-rule rate has no honest
    denominator: nothing records which calls had a rule in play.
    """
    rules = [_rule("C-12"), _rule("P-14")]
    traffic = (
        call("C-0001", knowledge_failure_rule="C-12"),
        call("C-0002", knowledge_failure_rule="C-12"),
        call("C-0003", knowledge_failure_rule="P-14"),
    )

    rows = failures_by_rule(rules, traffic, WINDOW)

    assert [(row.rule_ref, row.failures) for row in rows] == [("C-12", 2), ("P-14", 1)]
    assert not any(hasattr(row, "rate") for row in rows)


def test_rules_with_no_failures_are_still_listed() -> None:
    """A list of only the broken rules cannot answer how much of the rulebook
    is actually a problem — the more honest finding at this volume.
    """
    rows = failures_by_rule([_rule("C-12"), _rule("P-99")], (), WINDOW)

    assert {row.rule_ref for row in rows} == {"C-12", "P-99"}


def test_failures_cut_by_layer_area_provenance_and_touchpoint() -> None:
    rules = [
        _rule("C-12", RuleLayer.CARRIER, "Waiting periods"),
        _rule("A-09", RuleLayer.ADMINISTRATION, "Billing"),
    ]
    traffic = (
        call("C-0001", knowledge_failure_rule="C-12", touchpoint="denial_letter_eob"),
        call("C-0002", knowledge_failure_rule="A-09", touchpoint="invoice_statement"),
    )
    rows = failures_by_rule(rules, traffic, WINDOW)

    assert dict(failures_by_layer(rows))[RuleLayer.CARRIER] == 1
    assert dict(failures_by_area(rows))["Billing"] == 1
    assert dict(failures_by_provenance(rows))[RuleConfidence.VERIFIED] == 2
    assert dict(failures_by_touchpoint(traffic, WINDOW))["denial_letter_eob"] == 1


# --- Group 5: exec scorecard -----------------------------------------------


def test_escalation_integrity_is_handled_over_triggered(config: DashboardConfig) -> None:
    """Never over all calls. The corpus's own figure is 7 handled of 11."""
    triggered = tuple(
        call(f"T-{i:04d}", escalation=Escalation(triggered=True, handled=i <= 7))
        for i in range(1, 12)
    )
    quiet = calls(89, prefix="Q", escalation=Escalation(triggered=False))

    scorecard = exec_scorecard(config, (*triggered, *quiet), WINDOW)

    assert scorecard.escalation_integrity.n == 11
    assert scorecard.escalation_incidence.n == 100


def test_both_escalation_views_travel_together(config: DashboardConfig) -> None:
    """A screen cannot take the control measure and leave the context."""
    scorecard = exec_scorecard(config, calls(40, escalation=Escalation(triggered=False)), WINDOW)

    labels = [label for label, _ in escalation_integrity_pair(scorecard)]

    assert len(labels) == 2
    assert "warranted" in labels[0]


def test_whether_intent_was_routed_is_withheld_not_reported_as_zero(
    config: DashboardConfig,
) -> None:
    """Zero would assert that we checked and found none. Nothing in v9
    records routing, so the honest answer is that we cannot say.
    """
    scorecard = exec_scorecard(config, calls(40, intent=IntentType.MARKET_TEST), WINDOW)

    assert scorecard.intent_routed.withheld_reason is WithheldReason.NO_FIELD
    assert scorecard.intent_routed.value is None


# --- Group 6: self-inflicted demand ----------------------------------------


def test_the_three_components_are_published_separately(config: DashboardConfig) -> None:
    """ "Publish the three components separately so a reader can dispute one
    without discarding the total."
    """
    demand = self_inflicted_demand(config, calls(60), WINDOW)

    assert demand.failure_driven_repeats.published
    assert demand.chasing_submitted_action.published
    assert demand.logged_process_defect.published
    assert demand.total.published


def test_the_total_is_distinct_calls_not_the_sum_of_the_components(
    config: DashboardConfig,
) -> None:
    """A call that is both chasing a submitted action and carries a process
    gap is one self-inflicted call. Summing would count it twice and could
    push the total above 1.
    """
    both = call(
        "C-0001",
        signals=frozenset({SignalType.PROCESS_BREAKDOWN}),
        process_gap_change="name the waiting period",
        touchpoint="denial_letter_eob",
    )
    demand = self_inflicted_demand(config, (both, *calls(59, prefix="Q")), WINDOW)

    chasing = demand.chasing_submitted_action.value or 0
    defect = demand.logged_process_defect.value or 0
    assert (demand.total.value or 0) == pytest.approx(1 / 60)
    assert (demand.total.value or 0) < chasing + defect


def test_the_two_middle_components_read_different_fields(config: DashboardConfig) -> None:
    """§9 insight 15 asked for this to be checked rather than assumed.
    "Chasing an already-submitted action" is the process_breakdown signal;
    "a logged process defect" is process_gap.present. They are not one field.
    """
    chasing_only = calls(30, prefix="A", signals=frozenset({SignalType.PROCESS_BREAKDOWN}))
    defect_only = calls(
        30, prefix="B", process_gap_change="name the waiting period", touchpoint="enrolment_meeting"
    )

    demand = self_inflicted_demand(config, (*chasing_only, *defect_only), WINDOW)

    assert (demand.chasing_submitted_action.value or 0) == pytest.approx(0.5)
    assert (demand.logged_process_defect.value or 0) == pytest.approx(0.5)
    assert (demand.total.value or 0) == pytest.approx(1.0)


def test_cost_to_serve_carries_no_money_figure_at_all(config: DashboardConfig) -> None:
    """D4: money stays out of this view entirely rather than appearing
    withheld — there is no suppressed money field to un-suppress later.
    """
    figure = cost_to_serve(config, employer(enrolled=100), calls(40, aht_seconds=600), WINDOW)

    assert figure.published
    assert config.money_withheld is True


# --- Group 7: broker book friction -----------------------------------------


def test_a_book_under_the_floor_gets_no_rate_at_all(config: DashboardConfig) -> None:
    """`None`, not a withheld figure. The floor is not a judgement about
    sample size — the rate is not a meaningful thing to compute for a book
    that small, and a withheld figure invites a reader to wonder.
    """
    small = broker("BRK-09", groups_in_book=3, book_lives=40)

    row = broker_friction(config, small, calls(3, broker_named="BRK-09"), WINDOW)

    assert row.rate_per_hundred_lives is None
    assert len(row.adverse_calls) == 3, "counts still lead"


def test_only_books_over_the_floor_are_ranked(config: DashboardConfig) -> None:
    brokers = [broker("BRK-01", book_lives=400), broker("BRK-09", book_lives=40)]

    ranked = ranked_book_friction(config, brokers, calls(3, broker_named="BRK-09"), WINDOW)

    assert [row.broker_ref for row in ranked] == ["BRK-01"]


def test_the_pattern_test_needs_three_mentions_from_two_employers(
    config: DashboardConfig,
) -> None:
    """Shown fired and unfired alike, with what it reached."""
    one_client = (
        call("C-0001", broker_named="BRK-01", employer_ref="EMP-01"),
        call("C-0002", broker_named="BRK-01", employer_ref="EMP-01"),
        call("C-0003", broker_named="BRK-01", employer_ref="EMP-01"),
    )

    row = broker_friction(config, broker("BRK-01"), one_client, WINDOW)

    assert row.pattern.fires is False
    assert row.pattern.adverse_mentions == 3
    assert row.pattern.distinct_employers == 1
    assert "needs 3 from 2" in row.pattern.reached(config)


def test_the_pattern_test_fires_across_two_employers(config: DashboardConfig) -> None:
    spread = (
        call("C-0001", broker_named="BRK-01", employer_ref="EMP-01"),
        call("C-0002", broker_named="BRK-01", employer_ref="EMP-01"),
        call("C-0003", broker_named="BRK-01", employer_ref="EMP-02"),
    )

    row = broker_friction(config, broker("BRK-01"), spread, WINDOW)

    assert row.pattern.fires is True


# --- Group 8: touchpoint ranking -------------------------------------------


def test_touchpoints_are_ranked_and_split_by_attribution_not_by_a_winner() -> None:
    """ "Coloured by complaint.attributed_to where present, NOT a dominant
    party model that assumes fault records."
    """
    traffic = (
        call("C-0001", touchpoint="denial_letter_eob", complaint_to=ComplaintAttribution.CARRIER),
        call("C-0002", touchpoint="denial_letter_eob", complaint_to=ComplaintAttribution.CHOICE),
        call("C-0003", touchpoint="invoice_statement"),
    )

    ranking = touchpoint_ranking(traffic, WINDOW)

    assert ranking[0].touchpoint == "denial_letter_eob"
    assert dict(ranking[0].attribution)[ComplaintAttribution.CARRIER] == 1
    assert dict(ranking[0].attribution)[ComplaintAttribution.CHOICE] == 1
    assert ranking[1].without_complaint == 1


def test_calls_with_no_touchpoint_go_to_a_named_residual() -> None:
    """Dropping them would make every touchpoint's share of the total wrong.
    This bucket is also insight 18, which turned out to duplicate it.
    """
    ranking = touchpoint_ranking(
        (call("C-0001"), call("C-0002", touchpoint="welcome_pack")), WINDOW
    )

    assert unattributed_calls(ranking) == ("C-0001",)


# --- Group 9: enrolment promise gap ----------------------------------------


def test_promise_gaps_group_by_proposed_change_with_their_minutes() -> None:
    """Seven calls proposing the same change to the same document is a
    backlog item with evidence and cost attached.
    """
    change = "name the waiting period and its end date"
    traffic = (
        call("C-0001", touchpoint="enrolment_meeting", process_gap_change=change, aht_seconds=600),
        call("C-0002", touchpoint="enrolment_meeting", process_gap_change=change, aht_seconds=600),
        call("C-0003", touchpoint="denial_letter_eob", process_gap_change=change),
    )

    gaps = enrolment_promise_gaps(traffic, WINDOW)

    assert len(gaps) == 1, "the denial letter is not an enrolment touchpoint"
    assert gaps[0].calls == 2
    assert gaps[0].minutes == pytest.approx(20.0)


# --- Repeat contact (metrics 3 and 4) --------------------------------------


def test_a_repeat_needs_only_the_same_caller_not_the_same_category() -> None:
    """ "Same category" is not a workbook condition and was deliberately
    dropped. A member who calls about a denial then an ID card called twice.
    """
    traffic = (
        call("C-0001", caller_ref="CB-1", category=Category.CLAIMS_AND_EOB, on=day(0)),
        call("C-0002", caller_ref="CB-1", category=Category.ENROLLMENT_AND_ID_CARDS, on=day(3)),
    )

    assert len(repeats(traffic)) == 1


def test_a_contact_outside_fourteen_days_is_not_a_repeat() -> None:
    traffic = (
        call("C-0001", caller_ref="CB-1", on=day(0)),
        call("C-0002", caller_ref="CB-1", on=day(15)),
    )

    assert repeats(traffic) == ()


def test_only_unresolved_calls_are_failure_driven_repeats() -> None:
    traffic = (
        call("C-0001", caller_ref="CB-1", outcome=Outcome.UNRESOLVED, on=day(0)),
        call("C-0002", caller_ref="CB-1", on=day(2)),
        call("C-0003", caller_ref="CB-2", outcome=Outcome.RESOLVED, on=day(0)),
        call("C-0004", caller_ref="CB-2", on=day(2)),
    )

    assert [c.reference for c in failure_driven_repeats(traffic)] == ["C-0001"]


def test_the_last_fourteen_days_are_excluded_from_the_denominator() -> None:
    """Those calls have not had an exposure period. Counting them as
    non-repeats drags every rate toward zero as the window's end approaches,
    and the shape of the trend does not change, so nothing looks wrong.
    """
    early = call("C-0001", outcome=Outcome.UNRESOLVED, on=day(0))
    late = call("C-0002", outcome=Outcome.UNRESOLVED, on=WINDOW.end)

    exposed = exposed_unresolved((early, late), WINDOW)

    assert [c.reference for c in exposed] == ["C-0001"]


def test_a_resolved_call_the_caller_came_back_about_is_not_first_contact_resolution() -> None:
    """Resolution alone is not FCR. A call tagged RESOLVED that the same
    caller followed within fourteen days did not end the problem.
    """
    traffic = (
        call("C-0001", caller_ref="CB-1", outcome=Outcome.RESOLVED, on=day(0)),
        call("C-0002", caller_ref="CB-1", outcome=Outcome.RESOLVED, on=day(3)),
        call("C-0003", caller_ref="CB-9", outcome=Outcome.RESOLVED, on=day(0)),
    )

    assert {c.reference for c in first_contact_resolutions(traffic)} == {"C-0002", "C-0003"}


def test_a_call_with_no_caller_reference_is_skipped_rather_than_guessed_at() -> None:
    traffic = (
        call("C-0001", caller_ref=None, on=day(0)),
        call("C-0002", caller_ref=None, on=day(1)),
    )

    assert repeats(traffic) == ()


# --- The withheld panels ---------------------------------------------------


def test_every_withheld_panel_says_what_would_unlock_it() -> None:
    """§8 asks for the question, why it cannot be answered, and exactly what
    data would unlock it — the third being what separates a considered gap
    from an oversight.
    """
    for panel in WITHHELD_PANELS:
        assert panel.question and panel.why and panel.unlocked_by
        assert panel.figure.withheld_reason is WithheldReason.NO_FIELD
        assert panel.figure.value is None
        assert panel.figure.epistemic is EpistemicClass.WITHHELD


def test_the_withheld_panels_cover_the_insights_section_9_marks_withheld() -> None:
    """6, 17 and 25 are §9's WITHHELD list; 22 is withheld too and is missing
    from the §8 summary, which is a documentation error raised separately.
    """
    assert {panel.insight for panel in WITHHELD_PANELS} == {6, 17, 22, 25}


# --- Remaining branches, each a real case ----------------------------------


def test_the_complaint_cut_of_demand_stays_a_separate_measure(config: DashboardConfig) -> None:
    """§9 insight 15: it "stays labelled as a different measure". A member
    can cause us work without complaining, and complain about a call we
    handled well, so the two answer different questions.
    """
    ours = calls(20, prefix="A", complaint_to=ComplaintAttribution.CHOICE)
    theirs = calls(20, prefix="B", complaint_to=ComplaintAttribution.CARRIER)

    figure = complaint_attributed_to_choice(config, (*ours, *theirs), WINDOW)

    assert figure.value == pytest.approx(0.5)


def test_a_fired_pattern_test_says_what_it_reached(config: DashboardConfig) -> None:
    fired = (
        call("C-0001", broker_named="BRK-01", employer_ref="EMP-01"),
        call("C-0002", broker_named="BRK-01", employer_ref="EMP-01"),
        call("C-0003", broker_named="BRK-01", employer_ref="EMP-02"),
    )

    reached = broker_pattern(config, "BRK-01", fired, WINDOW).reached(config)

    assert "3 adverse mentions from 2 employers" in reached
    assert "at or above" in reached


def test_an_empty_matrix_names_no_systemic_category() -> None:
    assert systemic_categories(()) == ()


def test_knowledge_failures_with_no_touchpoint_land_in_the_residual() -> None:
    traffic = (call("C-0001", knowledge_failure_rule="C-12", touchpoint=None),)

    assert dict(failures_by_touchpoint(traffic, WINDOW)) == {"unattributed": 1}


def test_an_agent_with_no_scored_call_says_so_rather_than_showing_a_number() -> None:
    quality = agent_quality("AG-01", (call("C-0001", quality_score=None),), WINDOW)

    assert quality.median_score is None
    assert "No scored call" in quality.caveat


def test_control_exceptions_are_counted_per_agent_by_type(config: DashboardConfig) -> None:
    traffic = (
        call(
            "C-0001",
            control_exceptions=frozenset({ControlExceptionType.NO_RECORDING_DISCLOSURE}),
        ),
        call("C-0002", signals=frozenset({SignalType.ESCALATION_MISSED})),
    )

    events = agent_events(config, "AG-01", traffic, WINDOW)

    assert dict(events.control_exceptions)[ControlExceptionType.NO_RECORDING_DISCLOSURE] == 1
    assert events.escalations_missed == ("C-0002",)


def test_a_broker_row_splits_its_mentions_by_touchpoint(config: DashboardConfig) -> None:
    """ "This broker is a problem" becomes a conversation about the enrolment
    meeting or their own material.
    """
    traffic = (
        call("C-0001", broker_named="BRK-01", touchpoint="enrolment_meeting"),
        call("C-0002", broker_named="BRK-01", touchpoint="enrolment_meeting"),
        call("C-0003", broker_named="BRK-01", touchpoint="broker_material"),
    )

    row = broker_friction(config, broker("BRK-01"), traffic, WINDOW)

    assert row.by_touchpoint == (("enrolment_meeting", 2), ("broker_material", 1))
