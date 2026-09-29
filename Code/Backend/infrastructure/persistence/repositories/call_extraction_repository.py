"""SQLAlchemy implementation of `CallExtractionRepository`.

Upsert by call, like the other repositories: select the existing row for
this call's id (there is at most one — `call_id` is unique), then update
it in place or insert a new one.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports.call_extraction_repository import (
    CallExtractionRepository,
    L2Save,
    L3Save,
    L4Save,
)
from domain.entities.call_extraction import CallExtraction
from domain.entities.score_marker import ScoreMarker
from domain.errors import NotFoundError
from domain.value_objects.broker_named_aloud import BrokerNamedAloud
from domain.value_objects.broker_sentiment import BrokerSentiment
from domain.value_objects.category import Category
from domain.value_objects.complaint import Complaint
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.control_exception_type import ControlExceptionType
from domain.value_objects.escalation_trigger_type import EscalationTriggerType
from domain.value_objects.impact_scope import ImpactScope, ImpactScopeBucket
from domain.value_objects.intent_statement import IntentStatement
from domain.value_objects.intent_type import IntentType
from domain.value_objects.knowledge_failure import KnowledgeFailure
from domain.value_objects.layer_run import LayerRun
from domain.value_objects.outcome import Outcome
from domain.value_objects.polarity import Polarity
from domain.value_objects.preventable import Preventable
from domain.value_objects.process_gap import ProcessGap, ProcessGapStatus, RaisedBy
from domain.value_objects.product_line import ProductLine
from domain.value_objects.root_cause_owner import RootCauseOwner
from domain.value_objects.score import Score, ScoreStatus
from domain.value_objects.signal import Signal
from domain.value_objects.signal_type import SignalType
from domain.value_objects.tier import Tier
from infrastructure.persistence.tables import (
    CallExtractionRow,
    CallRow,
    ScoreMarkerRow,
    SignalRow,
)

_ACCEPTED = "accepted"


class SqlCallExtractionRepository(CallExtractionRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get(self, call_reference: str) -> CallExtraction | None:
        async with self._session_factory() as session:
            row = await self._find(session, call_reference)
            if row is None:
                return None
            accepted_markers = (
                (
                    await session.execute(
                        select(ScoreMarkerRow).where(
                            ScoreMarkerRow.call_id == row.call_id,
                            ScoreMarkerRow.verification_status == _ACCEPTED,
                        )
                    )
                )
                .scalars()
                .all()
            )
            signals = (
                (await session.execute(select(SignalRow).where(SignalRow.call_id == row.call_id)))
                .scalars()
                .all()
            )
            return _to_domain(call_reference, row, accepted_markers, signals)

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

            row.control_exceptions = sorted(item.value for item in result.control_exceptions)
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
            row.primary_issue = result.primary_issue
            row.secondary_issues = list(result.secondary_issues)
            row.impact_scope_bucket = (
                result.impact_scope.bucket.value if result.impact_scope is not None else None
            )
            row.impact_scope_count = (
                result.impact_scope.count if result.impact_scope is not None else None
            )
            row.l2_provider = result.provenance.provider
            row.l2_model = result.provenance.model
            row.l2_prompt_version = result.provenance.prompt_version
            row.l2_completed_at = result.provenance.completed_at

    async def save_l3(self, call_reference: str, result: L3Save) -> None:
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

            row.quality_score = result.score_result.score.value
            row.quality_status = result.score_result.status.value
            row.quality_tier = result.score_result.tier.value
            row.rubric_version = result.provenance.rubric_version
            row.knowledge_failure_present = result.knowledge_failure.present
            row.knowledge_failure_rule_id = result.knowledge_failure.rule_id
            row.knowledge_failure_correct_statement = result.knowledge_failure.correct_statement
            row.l3_provider = result.provenance.provider
            row.l3_model = result.provenance.model
            row.l3_prompt_version = result.provenance.prompt_version
            row.l3_completed_at = result.provenance.completed_at

            # Deleted and re-inserted via plain statements, not the ORM
            # relationship collection — same MissingGreenlet reason as
            # CallRow.turns (infrastructure/persistence/repositories/call_repository.py).
            await session.execute(delete(ScoreMarkerRow).where(ScoreMarkerRow.call_id == call_id))
            session.add_all(
                ScoreMarkerRow(
                    call_id=call_id,
                    dimension=raised.marker.dimension,
                    polarity=raised.marker.polarity.value,
                    description=raised.marker.description,
                    quote=raised.marker.quote,
                    turn_seq=raised.marker.turn_seq,
                    verification_status=raised.verification_status,
                )
                for raised in result.markers
            )

    async def save_l4(self, call_reference: str, result: L4Save) -> None:
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

            row.escalation_handled = result.escalation_handled
            row.escalation_trigger_type = (
                result.escalation_trigger_type.value
                if result.escalation_trigger_type is not None
                else None
            )
            row.process_gap_present = result.process_gap.present
            row.process_gap_gap_type = result.process_gap.gap_type
            row.process_gap_touchpoint = result.process_gap.touchpoint
            row.process_gap_proposed_change = result.process_gap.proposed_change
            row.process_gap_raised_by = (
                result.process_gap.raised_by.value
                if result.process_gap.raised_by is not None
                else None
            )
            row.process_gap_status = (
                result.process_gap.status.value if result.process_gap.status is not None else None
            )
            # L4 confirms or revises L2's first pass; an empty touchpoint
            # means "nothing to add", not "clear what L2 found".
            if result.touchpoint:
                row.touchpoint = result.touchpoint
            row.root_cause_owner = result.root_cause_owner.value
            row.preventable = result.preventable.value
            row.l4_provider = result.provenance.provider
            row.l4_model = result.provenance.model
            row.l4_prompt_version = result.provenance.prompt_version
            row.l4_completed_at = result.provenance.completed_at

            await session.execute(delete(SignalRow).where(SignalRow.call_id == call_id))
            session.add_all(
                SignalRow(
                    call_id=call_id,
                    type=signal.type.value,
                    quote=signal.quote,
                    turn_seq=signal.turn_seq,
                )
                for signal in result.signals
            )

    async def mark_l3_provisional(self, call_reference: str) -> None:
        async with self._session_factory() as session, session.begin():
            row = await self._find(session, call_reference)
            if row is None:
                raise NotFoundError(f"There is no call {call_reference!r} to analyse.")
            row.quality_status = ScoreStatus.PROVISIONAL.value

    async def _find(self, session: AsyncSession, call_reference: str) -> CallExtractionRow | None:
        return (
            await session.execute(
                select(CallExtractionRow)
                .join(CallRow, CallExtractionRow.call_id == CallRow.id)
                .where(CallRow.reference == call_reference)
            )
        ).scalar_one_or_none()


def _to_domain(
    call_reference: str,
    row: CallExtractionRow,
    accepted_markers: Sequence[ScoreMarkerRow] = (),
    signals: Sequence[SignalRow] = (),
) -> CallExtraction:
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

    impact_scope = None
    if row.impact_scope_bucket is not None:
        impact_scope = ImpactScope(
            bucket=ImpactScopeBucket(row.impact_scope_bucket),
            count=row.impact_scope_count,
        )

    return CallExtraction(
        call_reference=call_reference,
        l2_run=_run(row.l2_provider, row.l2_model, row.l2_prompt_version, row.l2_completed_at),
        l3_run=_run(
            row.l3_provider,
            row.l3_model,
            row.l3_prompt_version,
            row.l3_completed_at,
            rubric_version=row.rubric_version,
        ),
        l4_run=_run(row.l4_provider, row.l4_model, row.l4_prompt_version, row.l4_completed_at),
        control_exceptions=(
            frozenset(ControlExceptionType(item) for item in row.control_exceptions)
            if row.control_exceptions is not None
            else None
        ),
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
        primary_issue=row.primary_issue,
        secondary_issues=tuple(row.secondary_issues or ()),
        impact_scope=impact_scope,
        quality_score=Score(row.quality_score) if row.quality_score is not None else None,
        quality_status=ScoreStatus(row.quality_status) if row.quality_status is not None else None,
        quality_tier=Tier(row.quality_tier) if row.quality_tier is not None else None,
        markers=tuple(
            ScoreMarker(
                polarity=Polarity(marker_row.polarity),
                dimension=marker_row.dimension,
                description=marker_row.description,
                quote=marker_row.quote,
                turn_seq=marker_row.turn_seq,
            )
            for marker_row in accepted_markers
        ),
        knowledge_failure=(
            KnowledgeFailure(
                present=row.knowledge_failure_present,
                rule_id=row.knowledge_failure_rule_id,
                correct_statement=row.knowledge_failure_correct_statement,
            )
            if row.knowledge_failure_present is not None
            else None
        ),
        signals=tuple(
            Signal(
                type=SignalType(signal_row.type),
                quote=signal_row.quote,
                turn_seq=signal_row.turn_seq,
            )
            for signal_row in signals
        ),
        escalation_handled=row.escalation_handled,
        escalation_trigger_type=(
            EscalationTriggerType(row.escalation_trigger_type)
            if row.escalation_trigger_type is not None
            else None
        ),
        process_gap=(
            ProcessGap(
                present=row.process_gap_present,
                gap_type=row.process_gap_gap_type,
                touchpoint=row.process_gap_touchpoint,
                proposed_change=row.process_gap_proposed_change,
                raised_by=(
                    RaisedBy(row.process_gap_raised_by)
                    if row.process_gap_raised_by is not None
                    else None
                ),
                status=(
                    ProcessGapStatus(row.process_gap_status)
                    if row.process_gap_status is not None
                    else None
                ),
            )
            if row.process_gap_present is not None
            else None
        ),
        root_cause_owner=(
            RootCauseOwner(row.root_cause_owner) if row.root_cause_owner is not None else None
        ),
        preventable=(Preventable(row.preventable) if row.preventable is not None else None),
    )


def _run(
    provider: str | None,
    model: str | None,
    prompt_version: str | None,
    completed_at: datetime | None,
    *,
    rubric_version: str | None = None,
) -> LayerRun | None:
    """A layer's provenance, or `None` if that layer has not run.

    All four columns are written in one statement, so in practice they are
    all set or all null. The check is on `completed_at` alone anyway: it is
    the one that answers the question being asked, and a row half-written
    by some future partial save should read as "not run" rather than as a
    run with blanks where the model name goes.
    """
    if completed_at is None or provider is None or model is None or prompt_version is None:
        return None
    return LayerRun(
        provider=provider,
        model=model,
        prompt_version=prompt_version,
        completed_at=completed_at,
        rubric_version=rubric_version,
    )
