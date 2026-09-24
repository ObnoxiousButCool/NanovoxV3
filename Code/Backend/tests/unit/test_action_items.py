"""The action centre's read side.

Three claims worth holding: the taxonomy sets severity and owner rather
than this module, a list meant to be worked top-down is ordered by severity
before volume, and a team's workload counts calls once however many signals
they raised.
"""

from __future__ import annotations

from domain.aggregation.actions import action_items, by_owner
from domain.value_objects.signal_severity import SignalSeverity
from domain.value_objects.signal_type import SignalType
from tests.fixtures.tagged_calls import WINDOW, call, day


class TestItems:
    def test_one_item_per_signal_type_raised(self) -> None:
        calls = (
            call("C-1", signals=frozenset({SignalType.BILLING_DEFECT})),
            call("C-2", signals=frozenset({SignalType.BILLING_DEFECT})),
            call("C-3", signals=frozenset({SignalType.NETWORK_ADEQUACY})),
        )

        items = action_items(calls, WINDOW)

        assert {item.signal for item in items} == {
            SignalType.BILLING_DEFECT,
            SignalType.NETWORK_ADEQUACY,
        }
        billing = next(i for i in items if i.signal is SignalType.BILLING_DEFECT)
        assert billing.call_ids == ("C-1", "C-2")

    def test_a_signal_nobody_raised_is_absent_not_zero(self) -> None:
        """An item is work that exists; a zero-call item is a task nobody needs."""
        items = action_items((call("C-1", signals=frozenset({SignalType.BILLING_DEFECT})),), WINDOW)

        assert len(items) == 1

    def test_severity_and_owner_come_from_the_taxonomy(self) -> None:
        """Compliance failures route to Compliance, not the call centre."""
        items = action_items(
            (call("C-1", signals=frozenset({SignalType.COMPLIANCE_DISCLOSURE_MISSING})),),
            WINDOW,
        )

        assert items[0].owner_team == "Compliance"
        assert items[0].severity is SignalSeverity.HIGH

    def test_severity_beats_volume_in_the_ordering(self) -> None:
        """Twelve low-severity items must not bury one retention risk."""
        many_low = tuple(
            call(f"L-{i}", signals=frozenset({SignalType.REVENUE_OPPORTUNITY}))
            for i in range(1, 13)
        )
        one_critical = (call("C-1", signals=frozenset({SignalType.RETENTION_RISK})),)

        items = action_items((*many_low, *one_critical), WINDOW)

        assert items[0].signal is SignalType.RETENTION_RISK
        assert items[0].calls == 1
        assert items[-1].calls == 12

    def test_within_a_severity_the_heavier_item_leads(self) -> None:
        heavy = tuple(
            call(f"H-{i}", signals=frozenset({SignalType.BILLING_DEFECT})) for i in range(1, 4)
        )
        light = (call("X-1", signals=frozenset({SignalType.PROCESS_BREAKDOWN})),)

        items = action_items((*heavy, *light), WINDOW)

        assert [item.calls for item in items] == [3, 1]

    def test_calls_outside_the_window_raise_nothing(self) -> None:
        items = action_items(
            (call("C-1", on=day(-40), signals=frozenset({SignalType.BILLING_DEFECT})),),
            WINDOW,
        )

        assert items == ()


class TestByOwner:
    def test_a_call_raising_two_signals_for_one_team_counts_once(self) -> None:
        """Summing item counts would report more work than exists."""
        calls = (
            call(
                "C-1",
                signals=frozenset({SignalType.PROCESS_BREAKDOWN, SignalType.ESCALATION_MISSED}),
            ),
        )

        (operations,) = by_owner(action_items(calls, WINDOW))

        assert operations.owner_team == "Operations"
        assert len(operations.items) == 2
        assert operations.calls == 1

    def test_teams_are_ordered_by_critical_work_first(self) -> None:
        calls = (
            call("C-1", signals=frozenset({SignalType.RETENTION_RISK})),
            call("C-2", signals=frozenset({SignalType.PROCESS_BREAKDOWN})),
            call("C-3", signals=frozenset({SignalType.PROCESS_BREAKDOWN})),
            call("C-4", signals=frozenset({SignalType.PROCESS_BREAKDOWN})),
        )

        workloads = by_owner(action_items(calls, WINDOW))

        assert workloads[0].owner_team == "Account Management"
        assert workloads[0].critical == 1

    def test_no_signals_means_no_workloads(self) -> None:
        assert by_owner(action_items((call("C-1"),), WINDOW)) == ()
