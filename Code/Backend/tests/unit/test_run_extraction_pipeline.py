"""`ExtractionPipeline` orchestration: L1 -> L2 -> (L3 || L4), with every
port faked and a provider that can be made to fail one layer at a time —
the seam the essential/degradable tests need.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from pydantic import BaseModel

from application.dto.l2_response import (
    BrokerNamedAloudResponse,
    ComplaintResponse,
    L2Response,
)
from application.dto.l3_response import KnowledgeFailureResponse, L3Response, MarkerResponse
from application.dto.l4_response import L4Response, ProcessGapResponse
from application.ports.call_extraction_repository import (
    CallExtractionRepository,
    L2Save,
    L3Save,
    L4Save,
)
from application.ports.call_repository import CallRepository, IngestCounts
from application.ports.clock import Clock
from application.ports.llm_provider import (
    LLMProvider,
    LlmRequest,
    ProviderStatus,
    StructuredResult,
    TModel,
)
from application.ports.prompts import PromptSource
from application.ports.reference_lookup import ReferenceLookup
from application.ports.stage_cache import StageCache, StageCacheKey
from application.use_cases.classify_call_l2 import ClassifyCallL2
from application.use_cases.classify_call_l3 import ClassifyCallL3
from application.use_cases.classify_call_l4 import ClassifyCallL4
from application.use_cases.run_extraction_pipeline import ExtractionPipeline
from domain.entities.agent import Agent
from domain.entities.broker import Broker
from domain.entities.call_extraction import CallExtraction
from domain.entities.employer import Employer
from domain.entities.employer_contact import EmployerContact
from domain.entities.ingested_call import IngestedCall
from domain.entities.member import Member
from domain.entities.rule import Rule
from domain.entities.touchpoint import Touchpoint
from domain.entities.transcript import Transcript
from domain.entities.turn import Turn
from domain.errors import NotFoundError, ProviderUnavailableError
from domain.layers import Layer
from domain.value_objects.call_resolution_status import CallResolutionStatus
from domain.value_objects.call_source import CallSource
from domain.value_objects.caller_type import CallerType
from domain.value_objects.score import ScoreStatus
from domain.value_objects.speaker_role import SpeakerRole
from domain.value_objects.token_usage import TokenUsage
from infrastructure.llm.prompt_source import FilePromptSource
from infrastructure.llm.prompts import PromptLibrary
from tests.support.rubric import dimension, rubric

_NOW = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)

_TRANSCRIPT = Transcript(
    reference="C-0001",
    source=CallSource.CORPUS_PDF,
    occurred_at=None,
    aht_seconds=300,
    caller_type=CallerType.MEMBER,
    caller_ref="CB-7700205",
    agent_ref="AGT-01",
    agent_name="Sarah Whitlock",
    turns=(
        Turn(role=SpeakerRole.AGENT, text="Choice Administrators, Sarah speaking."),
        Turn(role=SpeakerRole.CALLER, text="I've had chest pains since this morning."),
        Turn(role=SpeakerRole.AGENT, text="I'll get you to urgent care guidance right away."),
    ),
)

_RUBRIC = rubric(dimension("empathy"))


def _call(**overrides: object) -> IngestedCall:
    defaults: dict[str, object] = {
        "reference": "C-0001",
        "caller_type": CallerType.MEMBER,
        "caller_ref": "CB-7700205",
        "agent_ref": "AGT-01",
        "transcript": _TRANSCRIPT,
        "resolution_status": CallResolutionStatus.RESOLVED,
        "resolution_reason": None,
        "member_ref": "CB-7700205",
        "employer_contact_ref": None,
        "employer_ref": "EMP-1001",
    }
    defaults.update(overrides)
    return IngestedCall(**defaults)  # type: ignore[arg-type]


def _l2_response(**overrides: object) -> L2Response:
    defaults: dict[str, object] = {
        "outcome": "RESOLVED",
        "category": "Claims & EOB",
        "product_lines": ["dental"],
        "complaint": ComplaintResponse(present=False, attributed_to="NONE"),
        "intent": [],
        "escalation_triggered": False,
        "escalation_requested_by_caller": False,
        "broker_named_aloud": BrokerNamedAloudResponse(
            present=False, broker_ref="", sentiment="NONE"
        ),
        "touchpoint": "",
        "summary": "The member's crown claim was explained and closed.",
        "primary_issue": "claims & eob",
        "secondary_issues": [],
        "impact_scope": "1_member",
        "impact_scope_count": 0,
    }
    defaults.update(overrides)
    return L2Response(**defaults)  # type: ignore[arg-type]


def _l3_response(**overrides: object) -> L3Response:
    defaults: dict[str, object] = {
        "markers": [],
        "knowledge_failure": KnowledgeFailureResponse(
            present=False, rule_id="", correct_statement=""
        ),
    }
    defaults.update(overrides)
    return L3Response(**defaults)  # type: ignore[arg-type]


def _l4_response(**overrides: object) -> L4Response:
    defaults: dict[str, object] = {
        "signals": [],
        "escalation_handled": False,
        "escalation_trigger_type": "NONE",
        "process_gap": ProcessGapResponse(
            present=False,
            gap_type="",
            touchpoint="",
            proposed_change="",
            raised_by="NONE",
            status="NONE",
        ),
        "touchpoint": "",
    }
    defaults.update(overrides)
    return L4Response(**defaults)  # type: ignore[arg-type]


class _FakeCalls(CallRepository):
    def __init__(self, calls: tuple[IngestedCall, ...] = ()) -> None:
        self._calls = {call.reference: call for call in calls}

    async def upsert_all(self, calls: tuple[IngestedCall, ...]) -> IngestCounts:
        raise NotImplementedError

    async def get(self, reference: str) -> IngestedCall | None:
        return self._calls.get(reference)

    async def list_references(self) -> tuple[str, ...]:
        return tuple(self._calls)


class _FakeLookup(ReferenceLookup):
    async def find_agent(self, reference: str) -> Agent | None:
        return None

    async def find_member(self, reference: str) -> Member | None:
        return None

    async def find_employer_contact(self, reference: str) -> EmployerContact | None:
        return None

    async def find_employer(self, reference: str) -> Employer | None:
        return None

    async def list_brokers(self) -> tuple[Broker, ...]:
        return ()

    async def list_rules(self) -> tuple[Rule, ...]:
        return ()

    async def list_touchpoints(self) -> tuple[Touchpoint, ...]:
        return ()


class _FakeStageCache(StageCache):
    def __init__(self) -> None:
        self.store: dict[StageCacheKey, str] = {}

    async def get(self, key: StageCacheKey) -> str | None:
        return self.store.get(key)

    async def put(self, key: StageCacheKey, value: str) -> None:
        self.store[key] = value


class FixedClock(Clock):
    def now(self) -> datetime:
        return _NOW


@dataclass
class _Stored:
    l2: L2Save | None = None
    quality_status: ScoreStatus | None = None


class _FakeExtractions(CallExtractionRepository):
    """Enough of a real extraction store for L3/L4 to read L2 back, and for
    the pipeline's suspension step to have something to update."""

    def __init__(self) -> None:
        self._store: dict[str, _Stored] = {}
        self.l3_saves: dict[str, L3Save] = {}
        self.l4_saves: dict[str, L4Save] = {}
        self.provisional_calls: list[str] = []

    async def get(self, call_reference: str) -> CallExtraction | None:
        entry = self._store.get(call_reference)
        if entry is None or entry.l2 is None:
            return None
        l2 = entry.l2
        return CallExtraction(
            call_reference=call_reference,
            outcome=l2.outcome,
            category=l2.category,
            product_lines=l2.product_lines,
            complaint=l2.complaint,
            intent=l2.intent,
            escalation_triggered=l2.escalation_triggered,
            escalation_requested_by_caller=l2.escalation_requested_by_caller,
            broker_named_aloud=l2.broker_named_aloud,
            touchpoint=l2.touchpoint,
            summary=l2.summary,
        )

    async def save_l2(self, call_reference: str, result: L2Save) -> None:
        self._store.setdefault(call_reference, _Stored()).l2 = result

    async def save_l3(self, call_reference: str, result: L3Save) -> None:
        self.l3_saves[call_reference] = result
        self._store.setdefault(
            call_reference, _Stored()
        ).quality_status = result.score_result.status

    async def save_l4(self, call_reference: str, result: L4Save) -> None:
        self.l4_saves[call_reference] = result

    async def mark_l3_provisional(self, call_reference: str) -> None:
        self.provisional_calls.append(call_reference)
        entry = self._store.get(call_reference)
        if entry is None:
            raise NotFoundError(f"There is no call {call_reference!r} to analyse.")
        entry.quality_status = ScoreStatus.PROVISIONAL

    def quality_status_for(self, call_reference: str) -> ScoreStatus | None:
        entry = self._store.get(call_reference)
        return entry.quality_status if entry is not None else None


class _RoutingProvider(LLMProvider):
    """One canned response per requested response model — or a raised
    error for exactly one, the seam the essential/degradable tests use to
    fail a single layer without touching its business logic."""

    def __init__(
        self,
        *,
        l2: L2Response,
        l3: L3Response,
        l4: L4Response,
        fail_for: type[BaseModel] | None = None,
    ) -> None:
        self._responses: dict[type[BaseModel], BaseModel] = {
            L2Response: l2,
            L3Response: l3,
            L4Response: l4,
        }
        self._fail_for = fail_for
        self.requests: list[LlmRequest[BaseModel]] = []

    @property
    def name(self) -> str:
        return "fake"

    @property
    def model(self) -> str:
        return "fake-model"

    async def complete(self, request: LlmRequest[TModel]) -> StructuredResult[TModel]:
        self.requests.append(request)  # type: ignore[arg-type]
        if request.response_model is self._fail_for:
            raise ProviderUnavailableError("simulated provider failure")
        value = request.response_model.model_validate(
            self._responses[request.response_model].model_dump()
        )
        return StructuredResult(
            value=value,
            provider=self.name,
            model=self.model,
            prompt_id=request.prompt_id,
            prompt_version=request.prompt_version,
            usage=TokenUsage(input_tokens=1, output_tokens=1),
            latency_ms=0.1,
            attempts=1,
        )

    async def status(self) -> ProviderStatus:
        return ProviderStatus(name=self.name, model=self.model, reachable=True)


def _prompts() -> PromptSource:
    return FilePromptSource(PromptLibrary())


def _pipeline(
    *, essential_layers: frozenset[Layer] | None = None
) -> tuple[ExtractionPipeline, _FakeExtractions]:
    calls = _FakeCalls((_call(),))
    lookup = _FakeLookup()
    prompts = _prompts()
    stage_cache = _FakeStageCache()
    extractions = _FakeExtractions()
    clock = FixedClock()

    l2 = ClassifyCallL2(
        calls=calls,
        reference_lookup=lookup,
        prompts=prompts,
        stage_cache=stage_cache,
        extractions=extractions,
        clock=clock,
    )
    l3 = ClassifyCallL3(
        calls=calls,
        reference_lookup=lookup,
        prompts=prompts,
        stage_cache=stage_cache,
        extractions=extractions,
        rubric=_RUBRIC,
        clock=clock,
    )
    l4 = ClassifyCallL4(
        calls=calls,
        reference_lookup=lookup,
        prompts=prompts,
        stage_cache=stage_cache,
        extractions=extractions,
        clock=clock,
    )
    kwargs: dict[str, object] = {"l2": l2, "l3": l3, "l4": l4, "extractions": extractions}
    if essential_layers is not None:
        kwargs["essential_layers"] = essential_layers
    return ExtractionPipeline(**kwargs), extractions  # type: ignore[arg-type]


class TestGoldenPath:
    async def test_every_layer_runs_and_saves(self) -> None:
        pipeline, extractions = _pipeline()
        provider = _RoutingProvider(l2=_l2_response(), l3=_l3_response(), l4=_l4_response())

        result = await pipeline.execute("C-0001", provider)

        assert result.l3 is not None
        assert result.l4 is not None
        assert result.degraded == ()
        assert "C-0001" in extractions.l3_saves
        assert "C-0001" in extractions.l4_saves
        assert extractions.provisional_calls == []


class TestClinicalRiskSuspension:
    async def test_a_clinical_trigger_suspends_l3s_already_saved_score(self) -> None:
        pipeline, extractions = _pipeline()
        provider = _RoutingProvider(
            l2=_l2_response(escalation_triggered=True),
            l3=_l3_response(),
            l4=_l4_response(escalation_trigger_type="clinical_or_safety_risk"),
        )

        await pipeline.execute("C-0001", provider)

        assert extractions.provisional_calls == ["C-0001"]
        assert extractions.quality_status_for("C-0001") is ScoreStatus.PROVISIONAL

    async def test_a_non_clinical_trigger_does_not_suspend(self) -> None:
        pipeline, extractions = _pipeline()
        provider = _RoutingProvider(
            l2=_l2_response(escalation_triggered=True),
            l3=_l3_response(),
            l4=_l4_response(escalation_trigger_type="authority_limit"),
        )

        await pipeline.execute("C-0001", provider)

        assert extractions.provisional_calls == []

    async def test_an_already_provisional_l3_is_not_marked_again(self) -> None:
        # Every marker rejected (an invented quote) already left L3
        # PROVISIONAL on its own — the pipeline has nothing to add.
        pipeline, extractions = _pipeline()
        provider = _RoutingProvider(
            l2=_l2_response(escalation_triggered=True),
            l3=_l3_response(
                markers=[
                    MarkerResponse(
                        dimension="empathy",
                        polarity="NEGATIVE",
                        description="invented",
                        quote="never said this",
                        turn_seq=0,
                    )
                ]
            ),
            l4=_l4_response(escalation_trigger_type="clinical_or_safety_risk"),
        )

        await pipeline.execute("C-0001", provider)

        assert extractions.provisional_calls == []


class TestEssentialVsDegradable:
    async def test_an_essential_layers_failure_propagates(self) -> None:
        pipeline, _ = _pipeline()
        provider = _RoutingProvider(
            l2=_l2_response(), l3=_l3_response(), l4=_l4_response(), fail_for=L3Response
        )

        with pytest.raises(ProviderUnavailableError):
            await pipeline.execute("C-0001", provider)

    async def test_a_non_essential_layers_failure_is_recorded_not_raised(self) -> None:
        pipeline, extractions = _pipeline(
            essential_layers=frozenset({Layer.L1, Layer.L2, Layer.L4})
        )
        provider = _RoutingProvider(
            l2=_l2_response(), l3=_l3_response(), l4=_l4_response(), fail_for=L3Response
        )

        result = await pipeline.execute("C-0001", provider)

        assert result.l3 is None
        assert result.l4 is not None
        assert result.degraded == (Layer.L3,)
        assert "C-0001" not in extractions.l3_saves
        assert "C-0001" in extractions.l4_saves
