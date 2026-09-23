"""`SqlCallExtractionRepository` against a real (temporary) SQLite database."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from application.ports.call_extraction_repository import L2Provenance, L2Save
from domain.entities.ingested_call import IngestedCall
from domain.entities.transcript import Transcript
from domain.entities.turn import Turn
from domain.errors import NotFoundError
from domain.value_objects.broker_named_aloud import BrokerNamedAloud
from domain.value_objects.broker_sentiment import BrokerSentiment
from domain.value_objects.call_resolution_status import CallResolutionStatus
from domain.value_objects.call_source import CallSource
from domain.value_objects.caller_type import CallerType
from domain.value_objects.category import Category
from domain.value_objects.complaint import Complaint
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.intent_statement import IntentStatement
from domain.value_objects.intent_type import IntentType
from domain.value_objects.outcome import Outcome
from domain.value_objects.product_line import ProductLine
from domain.value_objects.speaker_role import SpeakerRole
from infrastructure.persistence.repositories.call_extraction_repository import (
    SqlCallExtractionRepository,
)
from infrastructure.persistence.repositories.call_repository import SqlCallRepository
from infrastructure.system_clock import SystemClock

_TRANSCRIPT = Transcript(
    reference="C-0001",
    source=CallSource.CORPUS_PDF,
    occurred_at=datetime(2026, 7, 6, 9, 14, tzinfo=timezone.utc),
    aht_seconds=380,
    caller_type=CallerType.MEMBER,
    caller_ref="CB-7700205",
    agent_ref="AGT-01",
    agent_name="Sarah Whitlock",
    turns=(Turn(role=SpeakerRole.AGENT, text="Hello."), Turn(role=SpeakerRole.CALLER, text="Hi.")),
)

_INGESTED_CALL = IngestedCall(
    reference="C-0001",
    caller_type=CallerType.MEMBER,
    caller_ref="CB-7700205",
    agent_ref="AGT-01",
    transcript=_TRANSCRIPT,
    resolution_status=CallResolutionStatus.RESOLVED,
    resolution_reason=None,
    member_ref=None,
    employer_contact_ref=None,
    employer_ref=None,
)

_PROVENANCE = L2Provenance(
    provider="openai",
    model="gpt-4o-mini",
    prompt_version="1.0.0",
    completed_at=datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc),
)


_BASE_SAVE = L2Save(
    outcome=Outcome.RESOLVED,
    category=Category.CLAIMS_AND_EOB,
    product_lines=(ProductLine.DENTAL,),
    complaint=Complaint(present=False),
    intent=(),
    escalation_triggered=False,
    escalation_requested_by_caller=False,
    broker_named_aloud=BrokerNamedAloud(present=False),
    touchpoint=None,
    summary="The member's crown claim was explained and closed.",
    provenance=_PROVENANCE,
)


def _save(**overrides: Any) -> L2Save:
    return replace(_BASE_SAVE, **overrides)


async def _seed_call(session_factory: async_sessionmaker[AsyncSession]) -> None:
    await SqlCallRepository(session_factory, SystemClock()).upsert_all((_INGESTED_CALL,))


async def test_a_call_with_nothing_analysed_yet_returns_none(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed_call(session_factory)

    assert await SqlCallExtractionRepository(session_factory).get("C-0001") is None


async def test_saving_against_an_uningested_call_is_refused(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    repository = SqlCallExtractionRepository(session_factory)

    with pytest.raises(NotFoundError, match="C-9999"):
        await repository.save_l2("C-9999", _save())


class TestRoundTrip:
    async def test_a_saved_classification_is_read_back(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _seed_call(session_factory)
        repository = SqlCallExtractionRepository(session_factory)

        await repository.save_l2("C-0001", _save())
        found = await repository.get("C-0001")

        assert found is not None
        assert found.outcome is Outcome.RESOLVED
        assert found.category is Category.CLAIMS_AND_EOB
        assert found.product_lines == (ProductLine.DENTAL,)
        assert found.complaint == Complaint(present=False)

    async def test_a_complaint_round_trips_with_its_attribution(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _seed_call(session_factory)
        repository = SqlCallExtractionRepository(session_factory)

        await repository.save_l2(
            "C-0001",
            _save(complaint=Complaint(present=True, attributed_to=ComplaintAttribution.BROKER)),
        )
        found = await repository.get("C-0001")

        assert found is not None
        assert found.complaint == Complaint(present=True, attributed_to=ComplaintAttribution.BROKER)

    async def test_intent_statements_round_trip_in_order(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _seed_call(session_factory)
        repository = SqlCallExtractionRepository(session_factory)
        statements = (
            IntentStatement(type=IntentType.MARKET_TEST, quote="going out to bid", turn_seq=3),
            IntentStatement(type=IntentType.EXPANSION, quote="add vision", turn_seq=7),
        )

        await repository.save_l2("C-0001", _save(intent=statements))
        found = await repository.get("C-0001")

        assert found is not None
        assert found.intent == statements

    async def test_a_broker_mention_round_trips_with_the_employer_match_flag(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _seed_call(session_factory)
        repository = SqlCallExtractionRepository(session_factory)
        mention = BrokerNamedAloud(
            present=True,
            broker_ref="BRK-02",
            sentiment=BrokerSentiment.ADVERSE,
            matches_employer_of_record=False,
        )

        await repository.save_l2("C-0001", _save(broker_named_aloud=mention))
        found = await repository.get("C-0001")

        assert found is not None
        assert found.broker_named_aloud == mention

    async def test_a_second_save_replaces_rather_than_duplicates(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _seed_call(session_factory)
        repository = SqlCallExtractionRepository(session_factory)

        await repository.save_l2("C-0001", _save(outcome=Outcome.UNRESOLVED))
        await repository.save_l2("C-0001", _save(outcome=Outcome.RESOLVED))
        found = await repository.get("C-0001")

        assert found is not None
        assert found.outcome is Outcome.RESOLVED
