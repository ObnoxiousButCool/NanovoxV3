"""SQL implementation of `ActionRepository`."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports.action_repository import ActionRepository, NewAction
from domain.actions import Action, ChecklistStep, LogEntry, MeasurementWindow, Priority
from domain.errors import NotFoundError, ValidationError
from domain.value_objects.action_source_kind import ActionSourceKind
from infrastructure.persistence.tables import (
    ActionCallRow,
    ActionLogRow,
    ActionRow,
    ActionStepRow,
    CallRow,
    EmployerRow,
)


def _belongs_to(employer_ref: str) -> ColumnElement[bool]:
    """Whether an action is this account's.

    Either it names the employer, or it cites one of that employer's calls.
    **Both halves are needed and neither is redundant**: the seeded
    signal-wide actions carry no `employer_ref` at all and reach an account
    only through their calls, while an action raised against an account
    before any call is cited has the reference and nothing else.

    The call half is a join through `action_calls` to `calls`, which is
    where the employer actually lives -- an action stores call ids, not
    employers, so there is no denormalised column to read instead.
    """
    return or_(
        ActionRow.employer_ref == employer_ref,
        ActionRow.id.in_(
            select(ActionCallRow.action_id)
            .join(CallRow, CallRow.id == ActionCallRow.call_id)
            .join(EmployerRow, EmployerRow.id == CallRow.employer_id)
            .where(EmployerRow.reference == employer_ref)
        ),
    )


class SqlActionRepository(ActionRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, action: NewAction) -> Action:
        async with self._session_factory() as session, session.begin():
            call_ids = await _call_ids(session, action.call_references)
            row = ActionRow(
                title=action.title,
                source_kind=action.source_kind.value,
                source_detail=action.source_detail,
                issue_key=action.issue_key,
                evidence=action.evidence,
                recommendation=action.recommendation,
                owner_team=action.owner_team,
                owner=action.owner,
                priority=action.priority.value,
                status=action.status,
                employer_ref=action.employer_ref,
                broker_ref=action.broker_ref,
                created_at=action.created_at,
                assigned_on=action.assigned_on,
                due=action.due,
                seed_key=action.seed_key,
            )
            session.add(row)
            await session.flush()
            session.add_all(
                ActionCallRow(action_id=row.id, call_id=call_id, position=position)
                for position, call_id in enumerate(call_ids)
            )
            _add_steps(session, row.id, action.steps)
            session.add_all(
                ActionLogRow(action_id=row.id, at=entry.at, text=entry.text) for entry in action.log
            )
            action_id = row.id

        created = await self.get(action_id)
        if created is None:  # pragma: no cover - written in the transaction above
            raise NotFoundError(f"Action {action_id} vanished after it was created.")
        return created

    async def get(self, action_id: int) -> Action | None:
        async with self._session_factory() as session:
            row = await session.get(ActionRow, action_id)
            if row is None:
                return None
            return (await _hydrate(session, [row]))[0]

    async def list(self, employer_ref: str | None = None) -> tuple[Action, ...]:
        async with self._session_factory() as session:
            query = select(ActionRow).order_by(ActionRow.id.desc())
            if employer_ref is not None:
                query = query.where(_belongs_to(employer_ref))
            rows = (await session.execute(query)).scalars().all()
            return tuple(await _hydrate(session, list(rows)))

    async def calls_on_account(self, employer_ref: str) -> dict[int, int]:
        async with self._session_factory() as session:
            rows = await session.execute(
                select(ActionCallRow.action_id, func.count(ActionCallRow.call_id))
                .join(CallRow, CallRow.id == ActionCallRow.call_id)
                .join(EmployerRow, EmployerRow.id == CallRow.employer_id)
                .where(EmployerRow.reference == employer_ref)
                .group_by(ActionCallRow.action_id)
            )
            return dict(rows.all())  # type: ignore[arg-type]

    async def save(self, action: Action) -> None:
        async with self._session_factory() as session, session.begin():
            row = await session.get(ActionRow, action.id)
            if row is None:
                raise NotFoundError(f"There is no action {action.reference}.")
            row.owner = action.owner
            row.status = action.status
            row.due = action.due
            row.assigned_on = action.assigned_on
            row.action_taken = action.action_taken
            row.outcome = action.outcome
            row.measurement_start = action.measurement.start if action.measurement else None
            row.measurement_end = action.measurement.end if action.measurement else None

            steps = (
                (
                    await session.execute(
                        select(ActionStepRow)
                        .where(ActionStepRow.action_id == action.id)
                        .order_by(ActionStepRow.position)
                    )
                )
                .scalars()
                .all()
            )
            for step_row, step in zip(steps, action.steps, strict=True):
                step_row.done = step.done

            stored = (
                await session.execute(
                    select(func.count())
                    .select_from(ActionLogRow)
                    .where(ActionLogRow.action_id == action.id)
                )
            ).scalar_one()
            session.add_all(
                ActionLogRow(action_id=action.id, at=entry.at, text=entry.text)
                for entry in action.log[stored:]
            )

    async def seed_keys(self) -> frozenset[str]:
        async with self._session_factory() as session:
            keys = (
                await session.execute(
                    select(ActionRow.seed_key).where(ActionRow.seed_key.is_not(None))
                )
            ).scalars()
            return frozenset(key for key in keys if key is not None)


def _add_steps(session: AsyncSession, action_id: int, steps: tuple[ChecklistStep, ...]) -> None:
    session.add_all(
        ActionStepRow(action_id=action_id, position=position, text=step.text, done=step.done)
        for position, step in enumerate(steps)
    )


async def _call_ids(session: AsyncSession, references: tuple[str, ...]) -> list[int]:
    if not references:
        return []
    found = dict(
        (
            await session.execute(
                select(CallRow.reference, CallRow.id).where(CallRow.reference.in_(references))
            )
        )
        .tuples()
        .all()
    )
    unknown = [reference for reference in references if reference not in found]
    if unknown:
        raise ValidationError(
            "An action can only link calls that have been ingested.",
            detail=f"unknown: {unknown}",
        )
    return [found[reference] for reference in dict.fromkeys(references)]


async def _hydrate(session: AsyncSession, rows: list[ActionRow]) -> list[Action]:
    ids = [row.id for row in rows]
    calls: dict[int, list[str]] = defaultdict(list)
    for action_id, reference in (
        await session.execute(
            select(ActionCallRow.action_id, CallRow.reference)
            .join(CallRow, CallRow.id == ActionCallRow.call_id)
            .where(ActionCallRow.action_id.in_(ids))
            .order_by(ActionCallRow.action_id, ActionCallRow.position)
        )
    ).tuples():
        calls[action_id].append(reference)

    steps: dict[int, list[ChecklistStep]] = defaultdict(list)
    for step in (
        (
            await session.execute(
                select(ActionStepRow)
                .where(ActionStepRow.action_id.in_(ids))
                .order_by(ActionStepRow.action_id, ActionStepRow.position)
            )
        )
        .scalars()
        .all()
    ):
        steps[step.action_id].append(ChecklistStep(text=step.text, done=step.done))

    log: dict[int, list[LogEntry]] = defaultdict(list)
    for entry in (
        (
            await session.execute(
                select(ActionLogRow)
                .where(ActionLogRow.action_id.in_(ids))
                .order_by(ActionLogRow.action_id, ActionLogRow.id)
            )
        )
        .scalars()
        .all()
    ):
        log[entry.action_id].append(LogEntry(at=_utc(entry.at), text=entry.text))

    return [
        Action(
            id=row.id,
            title=row.title,
            source_kind=ActionSourceKind(row.source_kind),
            source_detail=row.source_detail,
            issue_key=row.issue_key,
            evidence=row.evidence,
            recommendation=row.recommendation,
            owner_team=row.owner_team,
            owner=row.owner,
            priority=Priority(row.priority),
            status=row.status,
            employer_ref=row.employer_ref,
            broker_ref=row.broker_ref,
            call_references=tuple(calls[row.id]),
            steps=tuple(steps[row.id]),
            log=tuple(log[row.id]),
            created_at=_utc(row.created_at),
            assigned_on=row.assigned_on,
            due=row.due,
            action_taken=row.action_taken,
            outcome=row.outcome,
            measurement=(
                MeasurementWindow(start=row.measurement_start, end=row.measurement_end)
                if row.measurement_start is not None and row.measurement_end is not None
                else None
            ),
        )
        for row in rows
    ]


def _utc(value: datetime) -> datetime:
    """SQLite stores no zone, and the clock only ever writes UTC. Read back
    as UTC so a stored timestamp serialises the same as a fresh one."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
