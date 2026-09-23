"""SQLAlchemy implementation of `CallExtractionRepository`.

Upsert by call, like the other repositories: select the existing row for
this call's id (there is at most one — `call_id` is unique), then update
it in place or insert a new one.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports.call_extraction_repository import (
    CallExtractionRepository,
    L2Save,
)
from domain.entities.call_extraction import CallExtraction
from domain.errors import NotFoundError
from domain.value_objects.broker_named_aloud import BrokerNamedAloud
from domain.value_objects.broker_sentiment import BrokerSentiment
from domain.value_objects.category import Category
from domain.value_objects.complaint import Complaint
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.intent_statement import IntentStatement
from domain.value_objects.intent_type import IntentType
from domain.value_objects.outcome import Outcome
from domain.value_objects.product_line import ProductLine
from infrastructure.persistence.tables import CallExtractionRow, CallRow


class SqlCallExtractionRepository(CallExtractionRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get(self, call_reference: str) -> CallExtraction | None:
        async with self._session_factory() as session:
            row = await self._find(session, call_reference)
            if row is None:
                return None
            return _to_domain(call_reference, row)

    async def save_l2(self, call_reference: str, result: L2Save) -> None:
        async with self._session_factory() as session, session.begin():
            call_id = (
                await session.execute(select(CallRow.id).where(CallRow.reference == call_reference))
            ).scalar_one_or_none()
            if call_id is None:
                raise NotFoundError(f"There is no call {call_reference!r} to analyse.")

            row = (
                await session.execute(
                    select(CallExtractionRow).where(CallExtractionRow.call_id == call_id)
                )
            ).scalar_one_or_none()
            if row is None:
                row = CallExtractionRow(call_id=call_id)
                session.add(row)

            row.outcome = result.outcome.value
            row.category = result.category.value
            row.product_lines = [line.value for line in result.product_lines]
            row.complaint_present = result.complaint.present
            row.complaint_attributed_to = (
                result.complaint.attributed_to.value
                if result.complaint.attributed_to is not None
                else None
            )
            row.intent = [
                {"type": item.type.value, "quote": item.quote, "turn_seq": item.turn_seq}
                for item in result.intent
            ]
            row.escalation_triggered = result.escalation_triggered
            row.escalation_requested_by_caller = result.escalation_requested_by_caller
            row.broker_named_aloud_present = result.broker_named_aloud.present
            row.broker_named_aloud_broker_ref = result.broker_named_aloud.broker_ref
            row.broker_named_aloud_sentiment = (
                result.broker_named_aloud.sentiment.value
                if result.broker_named_aloud.sentiment is not None
                else None
            )
            row.broker_named_aloud_matches_employer_of_record = (
                result.broker_named_aloud.matches_employer_of_record
            )
            row.touchpoint = result.touchpoint
            row.summary = result.summary
            row.l2_provider = result.provenance.provider
            row.l2_model = result.provenance.model
            row.l2_prompt_version = result.provenance.prompt_version
            row.l2_completed_at = result.provenance.completed_at

    async def _find(self, session: AsyncSession, call_reference: str) -> CallExtractionRow | None:
        return (
            await session.execute(
                select(CallExtractionRow)
                .join(CallRow, CallExtractionRow.call_id == CallRow.id)
                .where(CallRow.reference == call_reference)
            )
        ).scalar_one_or_none()


def _to_domain(call_reference: str, row: CallExtractionRow) -> CallExtraction:
    complaint = None
    if row.complaint_present is not None:
        complaint = Complaint(
            present=row.complaint_present,
            attributed_to=(
                ComplaintAttribution(row.complaint_attributed_to)
                if row.complaint_attributed_to is not None
                else None
            ),
        )

    broker_named_aloud = None
    if row.broker_named_aloud_present is not None:
        broker_named_aloud = BrokerNamedAloud(
            present=row.broker_named_aloud_present,
            broker_ref=row.broker_named_aloud_broker_ref,
            sentiment=(
                BrokerSentiment(row.broker_named_aloud_sentiment)
                if row.broker_named_aloud_sentiment is not None
                else None
            ),
            matches_employer_of_record=row.broker_named_aloud_matches_employer_of_record,
        )

    return CallExtraction(
        call_reference=call_reference,
        outcome=Outcome(row.outcome) if row.outcome is not None else None,
        category=Category(row.category) if row.category is not None else None,
        product_lines=tuple(ProductLine(line) for line in (row.product_lines or ())),
        complaint=complaint,
        intent=tuple(
            IntentStatement(
                type=IntentType(item["type"]),
                quote=str(item["quote"]),
                turn_seq=int(item["turn_seq"]),
            )
            for item in (row.intent or ())
        ),
        escalation_triggered=row.escalation_triggered,
        escalation_requested_by_caller=row.escalation_requested_by_caller,
        broker_named_aloud=broker_named_aloud,
        touchpoint=row.touchpoint,
        summary=row.summary,
    )
