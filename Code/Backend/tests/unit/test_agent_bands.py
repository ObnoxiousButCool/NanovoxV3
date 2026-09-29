"""Bands on `/agents`, and the escalation nobody can argue with.

Grouping by band is what recovers the sample a single agent lacks. What
these protect is the line around it: a band may carry a median where an
agent may not, the floor still applies, and the column the prototype fills
with a difficulty share stays empty rather than claiming the work was easy.
"""

from __future__ import annotations

import pytest

from domain.aggregation.agent_events import (
    BAND_MIN_SCORED,
    COMPLEXITY_UNAVAILABLE,
    AgentEvents,
    agent_events,
    band_rows,
    escalations_refused,
)
from domain.aggregation.call_tags import AgentFacts, CallContext
from domain.dashboard_config import DashboardConfig
from domain.value_objects.escalation import Escalation
from domain.value_objects.signal_type import SignalType
from infrastructure.config.dashboard_config import load_dashboard_config
from infrastructure.config.paths import DEFAULT_CONFIG_DIR
from tests.fixtures.tagged_calls import WINDOW, call


@pytest.fixture(scope="module")
def config() -> DashboardConfig:
    return load_dashboard_config(DEFAULT_CONFIG_DIR / "dashboard.yaml")


def _agent(reference: str, band: str) -> AgentFacts:
    return AgentFacts(
        reference=reference, name=f"Agent {reference}", band=band, expected_score=88.0
    )


def _events(
    config: DashboardConfig, roster: list[AgentFacts], calls: tuple[CallContext, ...]
) -> list[AgentEvents]:
    return [agent_events(config, agent.reference, calls, WINDOW) for agent in roster]


class TestBandRows:
    def test_a_band_pools_the_calls_of_the_agents_in_it(self, config: DashboardConfig) -> None:
        roster = [_agent("AGT-01", "Senior"), _agent("AGT-02", "Senior"), _agent("AGT-03", "New")]
        calls = (
            call("C-0001", agent_ref="AGT-01"),
            call("C-0002", agent_ref="AGT-02"),
            call("C-0003", agent_ref="AGT-03"),
        )

        rows = {
            row.band: row
            for row in band_rows(roster, _events(config, roster, calls), calls, WINDOW)
        }

        assert rows["Senior"].agents == 2
        assert rows["Senior"].calls == 2
        assert rows["New"].calls == 1

    def test_a_band_with_no_calls_in_scope_is_dropped(self, config: DashboardConfig) -> None:
        """Unlike an agent, a band is nobody's name. An empty row invites a
        comparison between a band that did well and one that was not on
        shift."""
        roster = [_agent("AGT-01", "Senior"), _agent("AGT-02", "New")]
        calls = (call("C-0001", agent_ref="AGT-01"),)

        rows = band_rows(roster, _events(config, roster, calls), calls, WINDOW)

        assert [row.band for row in rows] == ["Senior"]

    def test_a_band_under_the_floor_publishes_no_median(self, config: DashboardConfig) -> None:
        roster = [_agent("AGT-01", "Senior")]
        calls = tuple(
            call(f"C-000{index}", agent_ref="AGT-01", quality_score=90)
            for index in range(1, BAND_MIN_SCORED)
        )

        (row,) = band_rows(roster, _events(config, roster, calls), calls, WINDOW)

        assert row.scored_calls == BAND_MIN_SCORED - 1
        assert row.median_score is None

    def test_a_band_at_the_floor_publishes_one(self, config: DashboardConfig) -> None:
        """The whole point of grouping: the sample one agent cannot reach,
        a band can."""
        roster = [_agent("AGT-01", "Senior")]
        calls = tuple(
            call(f"C-000{index}", agent_ref="AGT-01", quality_score=90)
            for index in range(1, BAND_MIN_SCORED + 1)
        )

        (row,) = band_rows(roster, _events(config, roster, calls), calls, WINDOW)

        assert row.median_score == 90

    def test_the_difficulty_share_is_absent_rather_than_zero(self, config: DashboardConfig) -> None:
        """A share of high-complexity calls computed from a field that does
        not exist would read as "this band handles easy work", which is a
        claim about people."""
        roster = [_agent("AGT-01", "Senior")]
        calls = (call("C-0001", agent_ref="AGT-01"),)

        (row,) = band_rows(roster, _events(config, roster, calls), calls, WINDOW)

        assert row.hard_call_share is None
        assert "not a v9 field" in COMPLEXITY_UNAVAILABLE

    def test_events_follow_the_agent_into_their_band(self, config: DashboardConfig) -> None:
        roster = [_agent("AGT-01", "New"), _agent("AGT-02", "Senior")]
        calls = (
            call("C-0001", agent_ref="AGT-01", signals=frozenset({SignalType.KNOWLEDGE_ERROR})),
            call("C-0002", agent_ref="AGT-02"),
        )

        rows = {
            row.band: row
            for row in band_rows(roster, _events(config, roster, calls), calls, WINDOW)
        }

        assert rows["New"].events == 1
        assert rows["Senior"].events == 0

    def test_bands_are_ordered_by_events_then_by_calls(self, config: DashboardConfig) -> None:
        roster = [_agent("AGT-01", "New"), _agent("AGT-02", "Senior"), _agent("AGT-03", "Mid")]
        calls = (
            call("C-0001", agent_ref="AGT-02", signals=frozenset({SignalType.KNOWLEDGE_ERROR})),
            call("C-0002", agent_ref="AGT-03"),
            call("C-0003", agent_ref="AGT-03"),
            call("C-0004", agent_ref="AGT-01"),
        )

        rows = band_rows(roster, _events(config, roster, calls), calls, WINDOW)

        assert [row.band for row in rows] == ["Senior", "Mid", "New"]


class TestEscalationsRefused:
    def test_asked_and_not_given_is_counted(self) -> None:
        """Not "a supervisor was warranted", which is a judgement, but
        "somebody asked and was refused", which is what happened."""
        calls = (
            call(
                "C-0001",
                escalation=Escalation(triggered=True, requested_by_caller=True, handled=False),
            ),
        )

        assert escalations_refused(calls, WINDOW) == ("C-0001",)

    def test_asked_and_given_is_not_counted(self) -> None:
        calls = (
            call(
                "C-0001",
                escalation=Escalation(triggered=True, requested_by_caller=True, handled=True),
            ),
        )

        assert escalations_refused(calls, WINDOW) == ()

    def test_warranted_but_never_asked_for_is_a_different_event(self) -> None:
        """It is still a missed escalation and still counted elsewhere.
        This figure is the narrower one, and conflating them would lose the
        distinction the panel is built on."""
        calls = (
            call(
                "C-0001",
                escalation=Escalation(triggered=True, requested_by_caller=False, handled=False),
            ),
        )

        assert escalations_refused(calls, WINDOW) == ()
