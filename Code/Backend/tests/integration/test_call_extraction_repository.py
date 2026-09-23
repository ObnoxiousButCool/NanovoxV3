"""`SqlCallExtractionRepository` against a real (temporary) SQLite database."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from application.ports.call_extraction_repository import (
    L2Provenance,
    L2Save,
    L3Provenance,
    L3Save,
    L4Provenance,
    L4Save,
    RaisedMarker,
)
from domain.entities.ingested_call import IngestedCall
from domain.entities.score_marker import ScoreMarker
from domain.entities.transcript import Transcript
from domain.entities.turn import Turn
from domain.errors import NotFoundError
from domain.scoring.rubric_engine import RubricEngine
from domain.value_objects.broker_named_aloud import BrokerNamedAloud
from domain.value_objects.broker_sentiment import BrokerSentiment
from domain.value_objects.call_resolution_status import CallResolutionStatus
from domain.value_objects.call_source import CallSource
from domain.value_objects.caller_type import CallerType
from domain.value_objects.category import Category
from domain.value_objects.complaint import Complaint
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.escalation_trigger_type import EscalationTriggerType
from domain.value_objects.intent_statement import IntentStatement
from domain.value_objects.intent_type import IntentType
from domain.value_objects.knowledge_failure import KnowledgeFailure
from domain.value_objects.outcome import Outcome
from domain.value_objects.polarity import Polarity
from domain.value_objects.process_gap import ProcessGap, ProcessGapStatus, RaisedBy
from domain.value_objects.product_line import ProductLine
from domain.value_objects.score import ScoreStatus
from domain.value_objects.signal import Signal
from domain.value_objects.signal_type import SignalType
from domain.value_objects.speaker_role import SpeakerRole
from domain.value_objects.tier import Tier
from infrastructure.persistence.repositories.call_extraction_repository import (
    SqlCallExtractionRepository,
)
from infrastructure.persistence.repositories.call_repository import SqlCallRepository
from infrastructure.system_clock import SystemClock
from tests.support.rubric import dimension, marker, rubric

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


_L3_PROVENANCE = L3Provenance(
    provider="openai",
    model="gpt-4o-mini",
    prompt_version="1.0.0",
    rubric_version="test-1.0.0",
    completed_at=datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc),
)

_RUBRIC = rubric(dimension("empathy", negative=8, max_negative=24))


def _l3_save(**overrides: Any) -> L3Save:
    accepted = (marker("empathy"),)
    score_result = RubricEngine(_RUBRIC).score(list(accepted))
    defaults: dict[str, Any] = {
        "score_result": score_result,
        "markers": tuple(
            RaisedMarker(marker=item, verification_status="accepted") for item in accepted
        ),
        "knowledge_failure": KnowledgeFailure(present=False),
        "provenance": _L3_PROVENANCE,
    }
    defaults.update(overrides)
    return L3Save(**defaults)


class TestL3RoundTrip:
    async def test_a_saved_quality_result_is_read_back(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _seed_call(session_factory)
        repository = SqlCallExtractionRepository(session_factory)

        await repository.save_l3("C-0001", _l3_save())
        found = await repository.get("C-0001")

        assert found is not None
        assert found.quality_score is not None
        assert found.quality_score.value == 92
        assert found.quality_status is ScoreStatus.CONFIRMED
        assert found.quality_tier is Tier.GOOD

    async def test_accepted_markers_round_trip(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _seed_call(session_factory)
        repository = SqlCallExtractionRepository(session_factory)

        await repository.save_l3("C-0001", _l3_save())
        found = await repository.get("C-0001")

        assert found is not None
        assert len(found.markers) == 1
        assert found.markers[0].dimension == "empathy"
        assert found.markers[0].polarity is Polarity.NEGATIVE

    async def test_rejected_markers_are_stored_but_not_read_back_as_accepted(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        # The Data Model sheet: a refused marker stays visible, but only
        # accepted markers count toward CallExtraction.markers.
        await _seed_call(session_factory)
        repository = SqlCallExtractionRepository(session_factory)
        rejected = ScoreMarker(
            polarity=Polarity.NEGATIVE,
            dimension="empathy",
            description="invented",
            quote="never said",
            turn_seq=0,
        )

        await repository.save_l3(
            "C-0001",
            _l3_save(
                markers=(RaisedMarker(marker=rejected, verification_status="quote_not_in_turn"),)
            ),
        )
        found = await repository.get("C-0001")

        assert found is not None
        assert found.markers == ()

    async def test_a_knowledge_failure_round_trips(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _seed_call(session_factory)
        repository = SqlCallExtractionRepository(session_factory)
        failure = KnowledgeFailure(
            present=True, rule_id="C-01", correct_statement="Orthodontia needs the PPO design."
        )

        await repository.save_l3("C-0001", _l3_save(knowledge_failure=failure))
        found = await repository.get("C-0001")

        assert found is not None
        assert found.knowledge_failure == failure

    async def test_l2_and_l3_coexist_on_the_same_extraction(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _seed_call(session_factory)
        repository = SqlCallExtractionRepository(session_factory)

        await repository.save_l2("C-0001", _save())
        await repository.save_l3("C-0001", _l3_save())
        found = await repository.get("C-0001")

        assert found is not None
        assert found.outcome is Outcome.RESOLVED
        assert found.quality_score is not None

    async def test_a_second_l3_save_replaces_its_markers_rather_than_appending(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _seed_call(session_factory)
        repository = SqlCallExtractionRepository(session_factory)

        await repository.save_l3("C-0001", _l3_save())
        await repository.save_l3("C-0001", _l3_save())
        found = await repository.get("C-0001")

        assert found is not None
        assert len(found.markers) == 1

    async def test_marking_provisional_leaves_the_score_and_markers_untouched(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _seed_call(session_factory)
        repository = SqlCallExtractionRepository(session_factory)
        await repository.save_l3("C-0001", _l3_save())

        await repository.mark_l3_provisional("C-0001")
        found = await repository.get("C-0001")

        assert found is not None
        assert found.quality_status is ScoreStatus.PROVISIONAL
        assert found.quality_score is not None
        assert found.quality_score.value == 92
        assert len(found.markers) == 1

    async def test_marking_an_unanalysed_call_provisional_is_refused(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        repository = SqlCallExtractionRepository(session_factory)

        with pytest.raises(NotFoundError, match="C-9999"):
            await repository.mark_l3_provisional("C-9999")


_L4_PROVENANCE = L4Provenance(
    provider="openai",
    model="gpt-4o-mini",
    prompt_version="1.0.0",
    completed_at=datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc),
)

_ABSENT_GAP = ProcessGap(present=False)


def _l4_save(**overrides: Any) -> L4Save:
    defaults: dict[str, Any] = {
        "signals": (Signal(type=SignalType.PROCESS_BREAKDOWN, quote="not applied", turn_seq=1),),
        "escalation_handled": False,
        "escalation_trigger_type": None,
        "process_gap": _ABSENT_GAP,
        "touchpoint": None,
        "provenance": _L4_PROVENANCE,
    }
    defaults.update(overrides)
    return L4Save(**defaults)


class TestL4RoundTrip:
    async def test_signals_round_trip(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _seed_call(session_factory)
        repository = SqlCallExtractionRepository(session_factory)

        await repository.save_l4("C-0001", _l4_save())
        found = await repository.get("C-0001")

        assert found is not None
        assert found.signals == (
            Signal(type=SignalType.PROCESS_BREAKDOWN, quote="not applied", turn_seq=1),
        )

    async def test_an_escalation_trigger_type_round_trips(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _seed_call(session_factory)
        repository = SqlCallExtractionRepository(session_factory)

        await repository.save_l4(
            "C-0001",
            _l4_save(
                escalation_handled=True,
                escalation_trigger_type=EscalationTriggerType.AUTHORITY_LIMIT,
            ),
        )
        found = await repository.get("C-0001")

        assert found is not None
        assert found.escalation_handled is True
        assert found.escalation_trigger_type is EscalationTriggerType.AUTHORITY_LIMIT

    async def test_a_process_gap_round_trips(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _seed_call(session_factory)
        repository = SqlCallExtractionRepository(session_factory)
        gap = ProcessGap(
            present=True,
            gap_type="portal submission not applied",
            touchpoint="portal_submission",
            proposed_change="Alert operations after 48 hours unapplied.",
            raised_by=RaisedBy.CALLER,
            status=ProcessGapStatus.UNVALIDATED,
        )

        await repository.save_l4("C-0001", _l4_save(process_gap=gap))
        found = await repository.get("C-0001")

        assert found is not None
        assert found.process_gap == gap

    async def test_a_non_empty_l4_touchpoint_overwrites_l2s_first_pass(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _seed_call(session_factory)
        repository = SqlCallExtractionRepository(session_factory)

        await repository.save_l2("C-0001", _save(touchpoint="enrolment_meeting"))
        await repository.save_l4("C-0001", _l4_save(touchpoint="denial_letter"))
        found = await repository.get("C-0001")

        assert found is not None
        assert found.touchpoint == "denial_letter"

    async def test_an_empty_l4_touchpoint_leaves_l2s_first_pass_untouched(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _seed_call(session_factory)
        repository = SqlCallExtractionRepository(session_factory)

        await repository.save_l2("C-0001", _save(touchpoint="enrolment_meeting"))
        await repository.save_l4("C-0001", _l4_save(touchpoint=None))
        found = await repository.get("C-0001")

        assert found is not None
        assert found.touchpoint == "enrolment_meeting"

    async def test_a_second_l4_save_replaces_its_signals_rather_than_appending(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _seed_call(session_factory)
        repository = SqlCallExtractionRepository(session_factory)

        await repository.save_l4("C-0001", _l4_save())
        await repository.save_l4("C-0001", _l4_save())
        found = await repository.get("C-0001")

        assert found is not None
        assert len(found.signals) == 1

    async def test_l3_and_l4_coexist_on_the_same_extraction(
        self, engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        await _seed_call(session_factory)
        repository = SqlCallExtractionRepository(session_factory)

        await repository.save_l3("C-0001", _l3_save())
        await repository.save_l4("C-0001", _l4_save())
        found = await repository.get("C-0001")

        assert found is not None
        assert found.quality_score is not None
        assert found.signals != ()
