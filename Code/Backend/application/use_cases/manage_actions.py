"""Create, edit and read actions (Revised plan Phase 4, plan §8 Phase 9, D6).

## Raised from a playbook, or by hand

The prototype's composer prefills a card from the playbook for the issue in
front of it: its steps become the checklist, its owner the team, its
severity the priority, its meaning and why the description. The same happens
here when an issue key is given, and a key that resolves to nothing is
refused — a card raised from a dead key would carry nothing it claims to.
Without a key the caller supplies all of that itself.

## Nothing is invented

D6: an action has no owner, due date or outcome until someone sets one.
`assigned_on` is set the first time an owner is — it records when that
happened, not a guess at when it might have.

## Trusted network, single tenant

D14 (R9): there is no sign-in, so anyone who can reach this service can edit
any action. The API says so on every board response rather than implying a
permission model that does not exist.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date

from application.ports.action_repository import ActionRepository, NewAction
from application.ports.clock import Clock
from application.ports.reference_lookup import ReferenceLookup
from domain.actions import (
    Action,
    ActionChange,
    Lifecycle,
    LogEntry,
    Priority,
    apply,
    check_state,
    steps_from,
)
from domain.errors import NotFoundError, ValidationError
from domain.playbooks import PlaybookCatalogue, PlaybookSeverity, resolve
from domain.value_objects.action_source_kind import ActionSourceKind

TRUST_NOTE = (
    "Trusted network, single tenant: anyone who can reach this service can edit any "
    "action. There is no sign-in and no per-user permission (D14, R9)."
)


@dataclass(frozen=True)
class CreateActionRequest:
    title: str
    call_references: tuple[str, ...] = ()
    issue_key: str | None = None
    evidence: str | None = None
    owner_team: str | None = None
    owner: str | None = None
    priority: Priority | None = None
    status: str | None = None
    due: date | None = None
    steps: tuple[str, ...] | None = None
    employer_ref: str | None = None
    #: Set only by seeding (`application.use_cases.seed_actions`), never by
    #: the API — a human raising a card has no seed to record and no
    #: business setting one by hand. `NewAction.seed_key`'s own docstring:
    #: "so a second seed finds it rather than creating it again."
    seed_key: str | None = None


@dataclass(frozen=True)
class ActionContext:
    """What rendering one action needs besides the action: the lanes, and
    today for `past_due`."""

    lifecycle: Lifecycle
    today: date


@dataclass(frozen=True)
class ActionBoard:
    actions: tuple[Action, ...]
    lifecycle: Lifecycle
    today: date
    trust_note: str = TRUST_NOTE
    #: Per action id, how many of its cited calls belong to the account the
    #: board was scoped to. Empty on the unscoped board, where the question
    #: has no subject.
    #:
    #: **The card's own figures are the whole corpus and stay that way.** A
    #: seeded action counts every call that raised its signal, because that
    #: is what the piece of work is -- one card, one owner team, worked
    #: once. Re-counting it per account would describe a different job from
    #: the one on the board, and the same card would then disagree with
    #: itself between two screens. So the account's share travels beside the
    #: card's number rather than replacing it.
    calls_on_account: dict[int, int] = field(default_factory=dict)
    #: Per action id, its name with no count in it -- the playbook's own
    #: label, which is what `seed_actions` built the title from before
    #: appending "-- N calls".
    #:
    #: Sent because a screen showing its own figure beside the card's needs
    #: the name without a number in it, and the alternative is the client
    #: cutting the count back off a title the server composed. That is
    #: string surgery on somebody else's prose: it breaks the moment the
    #: wording changes, and it would quietly mangle a hand-raised action
    #: whose title happens to end in the same shape.
    labels: dict[int, str] = field(default_factory=dict)


class CreateAction:
    def __init__(
        self,
        *,
        actions: ActionRepository,
        lifecycle: Lifecycle,
        catalogue: PlaybookCatalogue,
        reference_lookup: ReferenceLookup,
        clock: Clock,
    ) -> None:
        self._actions = actions
        self._lifecycle = lifecycle
        self._catalogue = catalogue
        self._lookup = reference_lookup
        self._clock = clock

    async def execute(self, request: CreateActionRequest) -> Action:
        title = request.title.strip()
        if not title:
            raise ValidationError("An action needs a title.")

        playbook = None
        if request.issue_key is not None:
            touchpoints = {tp.reference: tp for tp in await self._lookup.list_touchpoints()}
            playbook = resolve(self._catalogue, request.issue_key, touchpoints)
            if playbook is None:
                raise ValidationError(
                    f"There is no playbook for the issue key {request.issue_key!r}."
                )

        if request.employer_ref is not None and (
            await self._lookup.find_employer(request.employer_ref) is None
        ):
            raise ValidationError(f"There is no employer {request.employer_ref!r}.")

        owner_team = request.owner_team or (playbook.owner_team if playbook else None)
        if not owner_team or not owner_team.strip():
            raise ValidationError(
                "An action needs an owner team, or an issue key to take one from."
            )

        step_texts = request.steps
        if step_texts is None:
            step_texts = playbook.steps if playbook else ()
        steps = steps_from(step_texts)

        evidence = request.evidence
        if evidence is None:
            evidence = f"{playbook.meaning} {playbook.why}" if playbook else ""

        priority = request.priority
        if priority is None:
            high = playbook is not None and playbook.severity is PlaybookSeverity.HIGH
            priority = Priority.HIGH if high else Priority.MEDIUM

        now = self._clock.now()
        owner = request.owner.strip() if request.owner and request.owner.strip() else None
        status = self._lifecycle.state(request.status or self._lifecycle.initial).code
        new = NewAction(
            title=title,
            source_kind=(
                playbook.source if playbook and playbook.source else ActionSourceKind.MANUAL
            ),
            source_detail=request.issue_key,
            issue_key=request.issue_key,
            evidence=evidence,
            # The prototype's composer takes the first step as the
            # recommendation. It is labelled one on the wire (C3a).
            recommendation=steps[0].text if steps else None,
            owner_team=owner_team.strip(),
            owner=owner,
            priority=priority,
            status=status,
            employer_ref=request.employer_ref,
            broker_ref=None,
            call_references=tuple(dict.fromkeys(request.call_references)),
            steps=steps,
            log=(LogEntry(at=now, text="Card created"),),
            created_at=now,
            assigned_on=now.date() if owner else None,
            due=request.due,
            seed_key=request.seed_key,
        )
        # A card created straight into monitoring or completed must carry
        # what those lanes require; it cannot, so this refuses it early.
        check_state(_as_action(new), self._lifecycle)
        return await self._actions.create(new)


class UpdateAction:
    def __init__(self, *, actions: ActionRepository, lifecycle: Lifecycle, clock: Clock) -> None:
        self._actions = actions
        self._lifecycle = lifecycle
        self._clock = clock

    async def execute(self, action_id: int, change: ActionChange) -> Action:
        action = await self._actions.get(action_id)
        if action is None:
            raise NotFoundError(f"There is no action {action_id}.")
        now = self._clock.now()
        updated = apply(action, change, self._lifecycle, now)
        if updated.owner and updated.assigned_on is None:
            updated = replace(updated, assigned_on=now.date())
        await self._actions.save(updated)
        return updated


class GetAction:
    def __init__(self, *, actions: ActionRepository) -> None:
        self._actions = actions

    async def execute(self, action_id: int) -> Action:
        action = await self._actions.get(action_id)
        if action is None:
            raise NotFoundError(f"There is no action {action_id}.")
        return action


class ListActions:
    def __init__(
        self,
        *,
        actions: ActionRepository,
        lifecycle: Lifecycle,
        catalogue: PlaybookCatalogue,
        clock: Clock,
    ) -> None:
        self._actions = actions
        self._lifecycle = lifecycle
        self._catalogue = catalogue
        self._clock = clock

    def _label(self, action: Action) -> str:
        """The action's name with no count in it.

        The playbook's own label where the action came from one, and the
        title otherwise -- a hand-raised action's title *is* its name, and
        there is nothing else to fall back to that would not be invented.
        """
        if action.issue_key is None:
            return action.title
        playbook = resolve(self._catalogue, action.issue_key, {})
        return playbook.label if playbook is not None else action.title

    async def execute(self, employer_ref: str | None = None) -> ActionBoard:
        """The board, or one account's share of it.

        The lanes are the same either way: they are the lifecycle's, not a
        summary of what happens to be on the board, so an account with
        nothing in progress still shows an empty In progress lane rather
        than losing the column.
        """
        actions = await self._actions.list(employer_ref)
        return ActionBoard(
            actions=actions,
            lifecycle=self._lifecycle,
            today=self._clock.now().date(),
            calls_on_account=(
                {} if employer_ref is None else await self._actions.calls_on_account(employer_ref)
            ),
            labels={action.id: self._label(action) for action in actions},
        )


def _as_action(new: NewAction) -> Action:
    """Enough of an `Action` to check its state before it has an id."""
    return Action(
        id=0,
        title=new.title,
        source_kind=new.source_kind,
        source_detail=new.source_detail,
        issue_key=new.issue_key,
        evidence=new.evidence,
        recommendation=new.recommendation,
        owner_team=new.owner_team,
        owner=new.owner,
        priority=new.priority,
        status=new.status,
        employer_ref=new.employer_ref,
        broker_ref=new.broker_ref,
        call_references=new.call_references,
        steps=new.steps,
        log=new.log,
        created_at=new.created_at,
    )
