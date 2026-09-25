"""The action lifecycle and its one hard rule (Revised plan Phase 4)."""

from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime, timezone

import pytest

from domain.actions import (
    Action,
    ActionChange,
    ChecklistStep,
    Lifecycle,
    LifecycleState,
    MeasurementWindow,
    Priority,
    Requirement,
    apply,
    past_due,
    steps_from,
)
from domain.errors import ValidationError
from domain.value_objects.action_source_kind import ActionSourceKind

_AT = datetime(2026, 9, 25, 9, 0, tzinfo=timezone.utc)
_WINDOW = MeasurementWindow(start=date(2026, 10, 1), end=date(2026, 10, 28))

LIFECYCLE = Lifecycle(
    states=(
        LifecycleState("needs_action", "Needs action", open=True),
        LifecycleState("assigned", "Assigned", open=True),
        LifecycleState("overdue", "Overdue", open=True),
        LifecycleState("action_taken", "Action taken", open=False),
        LifecycleState(
            "monitoring",
            "Monitoring",
            open=False,
            requires=frozenset({Requirement.ACTION_TAKEN, Requirement.MEASUREMENT_WINDOW}),
        ),
        LifecycleState(
            "completed",
            "Completed",
            open=False,
            requires=frozenset(
                {Requirement.ACTION_TAKEN, Requirement.MEASUREMENT_WINDOW, Requirement.OUTCOME}
            ),
        ),
    ),
    initial="needs_action",
)


def _action(**overrides: object) -> Action:
    fields: dict[str, object] = {
        "id": 7,
        "title": "Rewrite the denial letter",
        "source_kind": ActionSourceKind.PROCESS_GAP,
        "source_detail": "denial_letter_eob",
        "issue_key": None,
        "evidence": "3 calls proposed a change at this touchpoint",
        "recommendation": "Validate the proposal.",
        "owner_team": "Claims Operations",
        "owner": None,
        "priority": Priority.HIGH,
        "status": "needs_action",
        "employer_ref": None,
        "broker_ref": None,
        "call_references": ("C-0001",),
        "steps": steps_from(["Read the calls.", "Draft the change."]),
        "log": (),
        "created_at": _AT,
    }
    fields.update(overrides)
    return Action(**fields)  # type: ignore[arg-type]


def test_the_display_reference_matches_the_prototype() -> None:
    assert _action(id=7).reference == "ACT-007"


def test_moving_between_open_lanes_needs_nothing_and_is_logged() -> None:
    moved = apply(_action(), ActionChange(status="assigned"), LIFECYCLE, _AT)

    assert moved.status == "assigned"
    assert [entry.text for entry in moved.log] == ["Moved to Assigned"]


@pytest.mark.parametrize("target", ["monitoring", "completed"])
def test_monitoring_and_completed_are_refused_without_a_measurement(target: str) -> None:
    """The plan's hard rule. The prototype only says it in a tooltip."""
    with pytest.raises(ValidationError, match="measurement window"):
        apply(_action(action_taken="Rewrote it."), ActionChange(status=target), LIFECYCLE, _AT)


def test_monitoring_is_allowed_once_what_was_done_and_the_window_are_recorded() -> None:
    change = ActionChange(status="monitoring", action_taken="Rewrote it.", measurement=_WINDOW)

    moved = apply(_action(), change, LIFECYCLE, _AT)

    assert moved.status == "monitoring"
    assert moved.measurement == _WINDOW


def test_completed_also_needs_the_outcome() -> None:
    ready = _action(action_taken="Rewrote it.", measurement=_WINDOW)

    with pytest.raises(ValidationError, match="outcome"):
        apply(ready, ActionChange(status="completed"), LIFECYCLE, _AT)

    done = apply(
        ready, ActionChange(status="completed", outcome="Repeat calls fell."), LIFECYCLE, _AT
    )
    assert done.status == "completed"


def test_the_refusal_names_everything_missing() -> None:
    with pytest.raises(ValidationError) as caught:
        apply(_action(), ActionChange(status="completed"), LIFECYCLE, _AT)

    assert "action taken, measurement window and outcome" in caught.value.message


def test_an_unknown_lane_is_refused() -> None:
    with pytest.raises(ValidationError, match="not a lifecycle state"):
        apply(_action(), ActionChange(status="archived"), LIFECYCLE, _AT)


def test_ticking_a_step_logs_it_and_unticking_logs_the_reopen() -> None:
    ticked = apply(_action(), ActionChange(ticks={0: True}), LIFECYCLE, _AT)
    reopened = apply(ticked, ActionChange(ticks={0: False}), LIFECYCLE, _AT)

    assert ticked.steps[0].done and not ticked.steps[1].done
    assert [entry.text for entry in reopened.log] == [
        "Completed step: Read the calls.",
        "Reopened step: Read the calls.",
    ]


def test_ticking_a_step_that_is_already_ticked_logs_nothing() -> None:
    ticked = apply(_action(), ActionChange(ticks={0: True}), LIFECYCLE, _AT)

    again = apply(ticked, ActionChange(ticks={0: True}), LIFECYCLE, _AT)

    assert len(again.log) == 1


def test_a_step_that_does_not_exist_is_refused() -> None:
    with pytest.raises(ValidationError, match="no checklist step 5"):
        apply(_action(), ActionChange(ticks={5: True}), LIFECYCLE, _AT)


def test_owner_and_due_can_be_set_and_cleared() -> None:
    assigned = apply(
        _action(), ActionChange(owner="Rebekah Vance", due=date(2026, 10, 9)), LIFECYCLE, _AT
    )
    cleared = apply(assigned, ActionChange(clear_owner=True, clear_due=True), LIFECYCLE, _AT)

    assert assigned.owner == "Rebekah Vance" and assigned.due == date(2026, 10, 9)
    assert cleared.owner is None and cleared.due is None
    assert [e.text for e in cleared.log][-2:] == ["Owner cleared", "Due date cleared"]


def test_setting_and_clearing_the_owner_at_once_is_refused() -> None:
    with pytest.raises(ValidationError, match="both set and clear the owner"):
        apply(_action(), ActionChange(owner="A", clear_owner=True), LIFECYCLE, _AT)


@pytest.mark.parametrize(
    "change",
    [ActionChange(note="  "), ActionChange(action_taken=""), ActionChange(outcome=" ")],
)
def test_blank_text_is_refused(change: ActionChange) -> None:
    with pytest.raises(ValidationError, match="cannot be blank"):
        apply(_action(), change, LIFECYCLE, _AT)


def test_a_note_is_logged_as_written() -> None:
    noted = apply(_action(), ActionChange(note="Called the carrier."), LIFECYCLE, _AT)

    assert noted.log[-1].text == "Called the carrier."
    assert noted.log[-1].at == _AT


def test_a_measurement_window_cannot_end_before_it_starts() -> None:
    with pytest.raises(ValidationError, match="end before it starts"):
        MeasurementWindow(start=date(2026, 10, 2), end=date(2026, 10, 1))


def test_past_due_needs_an_open_lane_and_a_passed_date() -> None:
    today = date(2026, 10, 10)
    late = _action(due=date(2026, 10, 9))

    assert past_due(late, LIFECYCLE, today)
    assert not past_due(replace(late, due=date(2026, 10, 10)), LIFECYCLE, today)
    assert not past_due(replace(late, status="action_taken"), LIFECYCLE, today)
    assert not past_due(_action(), LIFECYCLE, today)


def test_the_lifecycle_refuses_an_initial_state_it_does_not_have() -> None:
    with pytest.raises(ValidationError, match="initial state"):
        Lifecycle(states=LIFECYCLE.states, initial="archived")


def test_the_lifecycle_refuses_duplicate_states() -> None:
    with pytest.raises(ValidationError, match="unique"):
        Lifecycle(states=LIFECYCLE.states + LIFECYCLE.states[:1], initial="needs_action")


def test_a_blank_checklist_step_is_refused() -> None:
    with pytest.raises(ValidationError, match="blank"):
        ChecklistStep(text=" ")
