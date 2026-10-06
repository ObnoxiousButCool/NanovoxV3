"""Persisted actions — the action centre's write side (Revised plan Phase 4,
plan §8 Phase 9, decision D6).

## Not the same object as a finding

`domain.aggregation.actions.ActionItem` is a *finding*: a signal raised in the
window, with its owner and calls, derived fresh on every read and carrying no
status. An `Action` is a *record* somebody works: it has a status, an owner, a
checklist and a history. Merging the two is how a finding acquires a fake
status, so they stay separate objects on separate endpoints.

## The lifecycle is configuration

Whether the seven lanes are the client's own process is still open (D14, U3),
so the states, their order and what each requires live in
`config/action_lifecycle.yaml`. A different answer is a config change and a
migration of existing rows, not a rewrite.

## Monitoring and completed require a measurement

The plan's one hard rule. A state lists what an action must carry to be in
it — what was done, a measurement window, the outcome — and `apply` refuses a
change that would leave an action in a state without them. The prototype
states this rule in a tooltip and never enforces it.

## Workflow fields start empty

D6: nothing about who owns an action, when it is due or what was done is
invented. A seeded action has none of them until someone sets them.
"""

from __future__ import annotations

from collections.abc import Container, Iterable, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from enum import StrEnum

from domain.errors import ValidationError
from domain.value_objects.action_source_kind import ActionSourceKind


class Requirement(StrEnum):
    """What an action must carry to be in a given state."""

    ACTION_TAKEN = "action_taken"
    MEASUREMENT_WINDOW = "measurement_window"
    OUTCOME = "outcome"


class Priority(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class LifecycleState:
    code: str
    label: str
    #: Still being worked. An open action past its due date reads as past due.
    open: bool
    requires: frozenset[Requirement] = frozenset()


@dataclass(frozen=True)
class Lifecycle:
    states: tuple[LifecycleState, ...]
    #: Where a seeded action starts. A created one may start elsewhere.
    initial: str

    def __post_init__(self) -> None:
        codes = [state.code for state in self.states]
        if not codes:
            raise ValidationError("The lifecycle needs at least one state.")
        if len(codes) != len(set(codes)):
            raise ValidationError("Lifecycle state codes must be unique.")
        if self.initial not in codes:
            raise ValidationError(f"The initial state {self.initial!r} is not a lifecycle state.")

    def state(self, code: str) -> LifecycleState:
        found = next((state for state in self.states if state.code == code), None)
        if found is None:
            raise ValidationError(
                f"{code!r} is not a lifecycle state.",
                detail=f"Expected one of {[state.code for state in self.states]}.",
            )
        return found


@dataclass(frozen=True)
class MeasurementWindow:
    """The before-and-after period an action's effect is measured over."""

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValidationError("A measurement window cannot end before it starts.")


@dataclass(frozen=True)
class ChecklistStep:
    text: str
    done: bool = False

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise ValidationError("A checklist step cannot be blank.")


@dataclass(frozen=True)
class LogEntry:
    at: datetime
    text: str


@dataclass(frozen=True)
class Action:
    id: int
    title: str
    source_kind: ActionSourceKind
    #: What within the kind: a touchpoint, a rule id, an exception type.
    source_detail: str | None
    #: The playbook key it was raised from, when there is one.
    issue_key: str | None
    evidence: str
    #: A suggestion, never a measurement (D14, C3a).
    recommendation: str | None
    owner_team: str
    owner: str | None
    priority: Priority
    status: str
    employer_ref: str | None
    broker_ref: str | None
    call_references: tuple[str, ...]
    steps: tuple[ChecklistStep, ...]
    log: tuple[LogEntry, ...]
    created_at: datetime
    assigned_on: date | None = None
    due: date | None = None
    action_taken: str | None = None
    outcome: str | None = None
    measurement: MeasurementWindow | None = None

    @property
    def reference(self) -> str:
        """The board's display id, as the prototype writes it."""
        return f"ACT-{self.id:03d}"


@dataclass(frozen=True)
class ActionChange:
    """One edit. A field left `None` is left alone; `clear_owner` and
    `clear_due` exist because `None` cannot also mean "remove it"."""

    status: str | None = None
    owner: str | None = None
    clear_owner: bool = False
    due: date | None = None
    clear_due: bool = False
    action_taken: str | None = None
    outcome: str | None = None
    measurement: MeasurementWindow | None = None
    #: Step index -> done.
    ticks: dict[int, bool] = field(default_factory=dict)
    note: str | None = None


def missing_for(action: Action, state: LifecycleState) -> tuple[Requirement, ...]:
    """What `action` lacks to be in `state`, in a stable order."""
    have = {
        Requirement.ACTION_TAKEN: bool(action.action_taken),
        Requirement.MEASUREMENT_WINDOW: action.measurement is not None,
        Requirement.OUTCOME: bool(action.outcome),
    }
    return tuple(req for req in Requirement if req in state.requires and not have[req])


def check_state(action: Action, lifecycle: Lifecycle) -> None:
    """Refuse an action sitting in a state it does not satisfy."""
    state = lifecycle.state(action.status)
    missing = missing_for(action, state)
    if missing:
        raise ValidationError(
            f"An action can only be {state.label} with "
            f"{_list(req.value.replace('_', ' ') for req in missing)} recorded.",
            detail=f"missing: {[req.value for req in missing]}",
        )


def apply(action: Action, change: ActionChange, lifecycle: Lifecycle, at: datetime) -> Action:
    """`action` with `change` applied, and one log entry per thing changed.

    Validated as a whole after every field is applied, so recording the
    outcome and moving to completed can happen in one edit — the order the
    prototype's "What changed?" form does them in.
    """
    entries: list[str] = []
    updated = action

    if change.owner is not None and change.clear_owner:
        raise ValidationError("An edit cannot both set and clear the owner.")
    if change.due is not None and change.clear_due:
        raise ValidationError("An edit cannot both set and clear the due date.")

    if change.ticks:
        steps = list(updated.steps)
        for index, done in sorted(change.ticks.items()):
            if not 0 <= index < len(steps):
                raise ValidationError(f"There is no checklist step {index}.")
            if steps[index].done != done:
                steps[index] = replace(steps[index], done=done)
                verb = "Completed step" if done else "Reopened step"
                entries.append(f"{verb}: {steps[index].text}")
        updated = replace(updated, steps=tuple(steps))

    if change.action_taken is not None:
        text = _required_text(change.action_taken, "What was done")
        updated = replace(updated, action_taken=text)
        entries.append(f"Action taken: {text}")

    if change.measurement is not None:
        updated = replace(updated, measurement=change.measurement)
        entries.append(
            f"Measurement window: {change.measurement.start.isoformat()} to "
            f"{change.measurement.end.isoformat()}"
        )

    if change.outcome is not None:
        text = _required_text(change.outcome, "What changed")
        updated = replace(updated, outcome=text)
        entries.append(f"Outcome recorded: {text}")

    if change.owner is not None or change.clear_owner:
        owner = None if change.clear_owner else _required_text(change.owner or "", "Owner")
        updated = replace(updated, owner=owner)
        entries.append(f"Owner {owner}" if owner else "Owner cleared")

    if change.due is not None or change.clear_due:
        updated = replace(updated, due=None if change.clear_due else change.due)
        entries.append(f"Due {change.due.isoformat()}" if change.due else "Due date cleared")

    if change.status is not None and change.status != updated.status:
        target = lifecycle.state(change.status)
        updated = replace(updated, status=target.code)
        entries.append(f"Moved to {target.label}")

    if change.note is not None:
        entries.append(_required_text(change.note, "An update"))

    check_state(updated, lifecycle)
    return replace(updated, log=updated.log + tuple(LogEntry(at=at, text=e) for e in entries))


def past_due(action: Action, lifecycle: Lifecycle, today: date) -> bool:
    """Open and past its due date, whatever lane it sits in.

    "Overdue" is a lane someone moves a card into (the prototype's model,
    kept); this is the fact beside it, so a missed date shows even on a card
    nobody moved.
    """
    return action.due is not None and action.due < today and lifecycle.state(action.status).open


def in_scope(
    action: Action,
    *,
    call_references: Container[str],
    employer_refs: Container[str],
    corpus_references: Container[str],
) -> bool:
    """Whether a filtered corpus still has anything to do with this action.

    The prototype's rule in `actions.html`, which the board needs because
    the filter bar is shared: a reader who narrows to a region and then asks
    what to do next should not be handed work on accounts the narrowing
    excluded.

    Three clauses, and the third is the one that matters:

    1. It cites a call the filters kept.
    2. It names an employer whose calls the filters kept.
    3. **It cites no calls at all**, in which case no call filter can speak
       to it either way and it stays. An action raised by hand, about a
       process rather than a conversation, has nothing for a corpus filter
       to match on; dropping it would make it disappear the moment anyone
       touched the bar, and nothing on the screen would say why.

    4. **None of the calls it cites are in the corpus at all.** The corpus
       holds the calls the pipeline has analysed; an action can cite one it
       has not reached yet. Nothing here can place such an action in or out
       of scope, so it stays. Dropping it would make the unfiltered board
       quietly narrower than the set of actions people are working, which
       is the worse of the two errors by far.

    Not "cites only calls the filters kept". An action raised over forty
    calls is still live when the reader has narrowed to one of them -- the
    narrowing changes what they are looking at, not what the action is.

    The whole rule is one sentence: drop an action only when the corpus can
    positively place it out of scope.
    """
    if any(reference in call_references for reference in action.call_references):
        return True
    if action.employer_ref is not None and action.employer_ref in employer_refs:
        return True
    if not action.call_references:
        return True
    return not any(reference in corpus_references for reference in action.call_references)


def steps_from(texts: Sequence[str]) -> tuple[ChecklistStep, ...]:
    return tuple(ChecklistStep(text=text.strip()) for text in texts)


def _required_text(value: str, what: str) -> str:
    text = value.strip()
    if not text:
        raise ValidationError(f"{what} cannot be blank.")
    return text


def _list(items: Iterable[str]) -> str:
    words = list(items)
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]
