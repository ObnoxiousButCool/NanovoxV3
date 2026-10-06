"""`SqlActionRepository` against a real database."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from application.ports.action_repository import NewAction
from domain.actions import LogEntry, MeasurementWindow, Priority, steps_from
from domain.entities.ingested_call import IngestedCall
from domain.errors import NotFoundError, ValidationError
from domain.value_objects.action_source_kind import ActionSourceKind
from domain.value_objects.call_resolution_status import CallResolutionStatus
from domain.value_objects.caller_type import CallerType
from infrastructure.persistence.repositories.action_repository import SqlActionRepository
from infrastructure.persistence.repositories.call_repository import SqlCallRepository
from infrastructure.system_clock import SystemClock

_AT = datetime(2026, 9, 25, 9, 0, tzinfo=UTC)


def _call(reference: str) -> IngestedCall:
    return IngestedCall(
        reference=reference,
        caller_type=CallerType.MEMBER,
        caller_ref="CB-7700205",
        agent_ref="AGT-01",
        transcript=None,
        resolution_status=CallResolutionStatus.RESOLVED,
        resolution_reason=None,
        member_ref=None,
        employer_contact_ref=None,
        employer_ref=None,
    )


def _new(**overrides: object) -> NewAction:
    fields: dict[str, object] = {
        "title": "Rewrite the denial letter",
        "source_kind": ActionSourceKind.PROCESS_GAP,
        "source_detail": "denial_letter_eob",
        "issue_key": None,
        "evidence": "3 calls proposed a change here",
        "recommendation": "Validate the proposal.",
        "owner_team": "Claims Operations",
        "owner": None,
        "priority": Priority.HIGH,
        "status": "needs_action",
        "employer_ref": None,
        "broker_ref": None,
        "call_references": ("C-0002", "C-0001"),
        "steps": steps_from(["Read the calls.", "Draft the change."]),
        "log": (LogEntry(at=_AT, text="Seeded"),),
        "created_at": _AT,
    }
    fields.update(overrides)
    return NewAction(**fields)  # type: ignore[arg-type]


@pytest.fixture
async def repository(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> SqlActionRepository:
    await SqlCallRepository(session_factory, SystemClock()).upsert_all(
        (_call("C-0001"), _call("C-0002"))
    )
    return SqlActionRepository(session_factory)


async def test_a_created_action_reads_back_whole(repository: SqlActionRepository) -> None:
    created = await repository.create(_new())

    found = await repository.get(created.id)

    assert found == created
    assert found.call_references == ("C-0002", "C-0001")
    assert [step.text for step in found.steps] == ["Read the calls.", "Draft the change."]
    assert [entry.text for entry in found.log] == ["Seeded"]
    assert found.owner is None and found.due is None and found.measurement is None


async def test_linking_a_call_that_was_never_ingested_is_refused(
    repository: SqlActionRepository,
) -> None:
    with pytest.raises(ValidationError, match="ingested"):
        await repository.create(_new(call_references=("C-9999",)))


async def test_saving_writes_fields_ticks_and_only_the_new_log_entries(
    repository: SqlActionRepository,
) -> None:
    created = await repository.create(_new())
    window = MeasurementWindow(start=date(2026, 10, 1), end=date(2026, 10, 28))
    edited = replace(
        created,
        owner="Rebekah Vance",
        status="monitoring",
        due=date(2026, 10, 9),
        action_taken="Rewrote it.",
        measurement=window,
        steps=(replace(created.steps[0], done=True), created.steps[1]),
        log=(*created.log, LogEntry(at=_AT, text="Moved to Monitoring")),
    )

    await repository.save(edited)
    await repository.save(edited)  # saving again appends nothing
    found = await repository.get(created.id)

    assert found is not None
    assert found.owner == "Rebekah Vance" and found.status == "monitoring"
    assert found.measurement == window
    assert [step.done for step in found.steps] == [True, False]
    assert [entry.text for entry in found.log] == ["Seeded", "Moved to Monitoring"]


async def test_saving_an_action_that_does_not_exist_is_refused(
    repository: SqlActionRepository,
) -> None:
    created = await repository.create(_new())

    with pytest.raises(NotFoundError):
        await repository.save(replace(created, id=999))


async def test_the_list_is_newest_first(repository: SqlActionRepository) -> None:
    first = await repository.create(_new(title="First"))
    second = await repository.create(_new(title="Second"))

    listed = await repository.list()

    assert [action.id for action in listed] == [second.id, first.id]


async def test_seed_keys_are_unique_and_reported(repository: SqlActionRepository) -> None:
    await repository.create(_new(seed_key="process_gap:denial_letter_eob"))
    await repository.create(_new())

    assert await repository.seed_keys() == {"process_gap:denial_letter_eob"}


async def test_an_unknown_action_is_none(repository: SqlActionRepository) -> None:
    assert await repository.get(404) is None


async def test_timezone_aware_timestamps_are_accepted(repository: SqlActionRepository) -> None:
    aware = datetime(2026, 9, 25, 9, 0, tzinfo=UTC)
    created = await repository.create(_new(created_at=aware, log=(LogEntry(aware, "x"),)))

    assert created.log[0].text == "x"
