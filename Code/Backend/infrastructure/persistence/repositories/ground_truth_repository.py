"""SQLAlchemy implementation of `GroundTruthRepository`.

Upsert by call, like the other repositories: resolve the call reference to
its surrogate id, then update the existing row in place or insert a new one.
`call_id` is unique, so there is at most one row to find.

A tracker row whose call has not been ingested is collected and returned in
`GroundTruthCounts.unmatched` rather than written or raised. It cannot be
written — the row hangs off `calls.id` — and raising would abort an import
that is otherwise entirely good. The count travels back to the caller, which
reports it.

Answer-key material: no extraction code may import this module, per the
import-linter contract in `pyproject.toml`.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports.clock import Clock
from application.ports.ground_truth_repository import GroundTruthCounts, GroundTruthRepository
from domain.entities.ground_truth import GroundTruth, GroundTruthSignal
from domain.value_objects.category import Category
from domain.value_objects.outcome import Outcome
from domain.value_objects.preventable import Preventable
from domain.value_objects.root_cause_owner import RootCauseOwner
from infrastructure.persistence.tables import CallRow, GroundTruthRow


class SqlGroundTruthRepository(GroundTruthRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession], clock: Clock) -> None:
        self._session_factory = session_factory
        self._clock = clock

    async def upsert(self, rows: tuple[GroundTruth, ...]) -> GroundTruthCounts:
        if not rows:
            return GroundTruthCounts(written=0, unmatched=())

        imported_at = self._clock.now()
        async with self._session_factory() as session, session.begin():
            # One round trip for every call id, rather than one per row: the
            # tracker is read whole and this runs over all 100 at once.
            references = [row.reference for row in rows]
            found = (
                await session.execute(
                    select(CallRow.reference, CallRow.id).where(CallRow.reference.in_(references))
                )
            ).all()
            call_ids: dict[str, int] = {row.reference: row.id for row in found}

            existing = {
                row.call_id: row
                for row in (
                    await session.execute(
                        select(GroundTruthRow).where(GroundTruthRow.call_id.in_(call_ids.values()))
                    )
                )
                .scalars()
                .all()
            }

            written = 0
            unmatched: list[str] = []
            for truth in rows:
                call_id = call_ids.get(truth.reference)
                if call_id is None:
                    unmatched.append(truth.reference)
                    continue

                row = existing.get(call_id)
                if row is None:
                    row = GroundTruthRow(call_id=call_id)
                    session.add(row)
                _apply(row, truth, imported_at)
                written += 1

        return GroundTruthCounts(written=written, unmatched=tuple(unmatched))

    async def all(self) -> tuple[GroundTruth, ...]:
        async with self._session_factory() as session:
            rows = (
                await session.execute(
                    select(GroundTruthRow, CallRow.reference)
                    .join(CallRow, GroundTruthRow.call_id == CallRow.id)
                    .order_by(CallRow.reference)
                )
            ).all()
            return tuple(_to_domain(row, reference) for row, reference in rows)


def _apply(row: GroundTruthRow, truth: GroundTruth, imported_at: datetime) -> None:
    """Copy every answer onto the row. Enum values are stored by `.value`."""
    row.category = truth.category.value if truth.category else None
    row.archetype = truth.archetype
    row.rule_refs = list(truth.rule_refs)
    row.outcome = truth.outcome.value if truth.outcome else None
    row.score = truth.score

    row.product_line = truth.product_line
    row.touchpoint = truth.touchpoint
    row.aht_seconds = truth.aht_seconds

    row.complaint_present = truth.complaint_present
    row.complaint_attributed_to = truth.complaint_attributed_to

    row.signals = [asdict(signal) for signal in truth.signals]
    row.control_exceptions = list(truth.control_exceptions)

    row.escalation_triggered = truth.escalation_triggered
    row.escalation_type = truth.escalation_type
    row.escalation_requested_by_caller = truth.escalation_requested_by_caller
    row.escalation_handled = truth.escalation_handled

    row.knowledge_failure_present = truth.knowledge_failure_present
    row.knowledge_failure_rule_ref = truth.knowledge_failure_rule_ref
    row.knowledge_failure_statement = truth.knowledge_failure_statement

    row.intent_type = truth.intent_type
    row.intent_evidence = truth.intent_evidence

    row.process_gap_present = truth.process_gap_present
    row.process_gap_description = truth.process_gap_description

    row.broker_named_present = truth.broker_named_present
    row.broker_named_broker_ref = truth.broker_named_broker_ref
    row.broker_named_sentiment = truth.broker_named_sentiment

    row.repeat_of_reference = truth.repeat_of_reference
    row.repeat_of_note = truth.repeat_of_note

    row.root_cause_owner = truth.root_cause_owner.value if truth.root_cause_owner else None
    row.preventable = truth.preventable.value if truth.preventable else None
    row.primary_issue = truth.primary_issue
    row.secondary_issues = list(truth.secondary_issues)
    row.impact_scope = truth.impact_scope

    row.imported_at = imported_at


def _to_domain(row: GroundTruthRow, reference: str) -> GroundTruth:
    """Read one stored answer back.

    The reference comes from the joined call rather than from the answer
    row, because `ground_truth` keys on `calls.id` — the business reference
    lives on the call and is not duplicated here.
    """
    return GroundTruth(
        reference=reference,
        category=Category(row.category) if row.category else None,
        archetype=row.archetype or "",
        rule_refs=tuple(row.rule_refs or ()),
        outcome=Outcome(row.outcome) if row.outcome else None,
        score=row.score,
        product_line=row.product_line or "",
        touchpoint=row.touchpoint or "",
        aht_seconds=row.aht_seconds,
        complaint_present=row.complaint_present,
        complaint_attributed_to=row.complaint_attributed_to,
        signals=tuple(GroundTruthSignal(**signal) for signal in (row.signals or ())),
        control_exceptions=tuple(row.control_exceptions or ()),
        escalation_triggered=row.escalation_triggered,
        escalation_type=row.escalation_type,
        escalation_requested_by_caller=row.escalation_requested_by_caller,
        escalation_handled=row.escalation_handled,
        knowledge_failure_present=row.knowledge_failure_present,
        knowledge_failure_rule_ref=row.knowledge_failure_rule_ref,
        knowledge_failure_statement=row.knowledge_failure_statement,
        intent_type=row.intent_type,
        intent_evidence=row.intent_evidence,
        process_gap_present=row.process_gap_present,
        process_gap_description=row.process_gap_description,
        broker_named_present=row.broker_named_present,
        broker_named_broker_ref=row.broker_named_broker_ref,
        broker_named_sentiment=row.broker_named_sentiment,
        repeat_of_reference=row.repeat_of_reference,
        repeat_of_note=row.repeat_of_note,
        root_cause_owner=(RootCauseOwner(row.root_cause_owner) if row.root_cause_owner else None),
        preventable=(Preventable(row.preventable) if row.preventable else None),
        primary_issue=row.primary_issue or "",
        secondary_issues=tuple(row.secondary_issues or ()),
        impact_scope=row.impact_scope or "",
    )
