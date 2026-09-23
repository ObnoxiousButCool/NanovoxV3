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
from domain.entities.ground_truth import GroundTruth
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

    row.imported_at = imported_at
