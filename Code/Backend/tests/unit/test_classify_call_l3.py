"""`ClassifyCallL3` orchestration, with every port faked."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from application.dto.l3_response import KnowledgeFailureResponse, L3Response, MarkerResponse
from application.ports.call_extraction_repository import (
    CallExtractionRepository,
    L2Save,
    L3Save,
    L4Save,
)
from application.ports.call_repository import CallRepository, IngestCounts
from application.ports.clock import Clock
from application.ports.prompts import PromptSource
from application.ports.reference_lookup import ReferenceLookup
from application.ports.stage_cache import StageCache, StageCacheKey
from application.use_cases.classify_call_l3 import ClassifyCallL3
from domain.entities.agent import Agent
from domain.entities.broker import Broker
from domain.entities.call_extraction import CallExtraction
from domain.entities.employer import Employer
from domain.entities.employer_contact import EmployerContact
from domain.entities.ingested_call import IngestedCall
from domain.entities.member import Member
from domain.entities.rule import Rule
from domain.entities.transcript import Transcript
from domain.entities.turn import Turn
from domain.errors import ValidationError
from domain.extraction.evidence import EvidenceRejection
from domain.value_objects.call_resolution_status import CallResolutionStatus
from domain.value_objects.call_source import CallSource
from domain.value_objects.caller_type import CallerType
from domain.value_objects.category import Category
from domain.value_objects.complaint import Complaint
from domain.value_objects.outcome import Outcome
from domain.value_objects.product_line import ProductLine
from domain.value_objects.rule_confidence import RuleConfidence
from domain.value_objects.rule_layer import RuleLayer
from domain.value_objects.score import ScoreStatus
from domain.value_objects.speaker_role import SpeakerRole
from infrastructure.llm.prompt_source import FilePromptSource
from infrastructure.llm.prompts import PromptLibrary
from tests.support.llm import FakeProvider
from tests.support.rubric import dimension, rubric

_NOW = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)

_DENTAL_RULE = Rule(
    reference="C-01",
    layer=RuleLayer.CARRIER,
    area="Ameritas — dental PPO",
    text="Orthodontia is covered only under the PPO design, not the DHMO.",
    commonly_confused_with="Assuming every plan carries orthodontia.",
    source="Ameritas EOC",
    confidence=RuleConfidence.VERIFIED,
)
_VISION_RULE = Rule(
    reference="C-02",
    layer=RuleLayer.CARRIER,
    area="EyeMed — vision",
    text="Frames are covered once every 24 months.",
    commonly_confused_with="Annual frame coverage.",
    source="EyeMed EOC",
    confidence=RuleConfidence.VERIFIED,
)

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
        Turn(role=SpeakerRole.CALLER, text="I had a crown done and it's not covered."),
        Turn(role=SpeakerRole.AGENT, text="Orthodontia needs the PPO design, not the DHMO."),
    ),
)

_L2_EXTRACTION = CallExtraction(
    call_reference="C-0001",
    outcome=Outcome.RESOLVED,
    category=Category.CLAIMS_AND_EOB,
    product_lines=(ProductLine.DENTAL,),
    complaint=Complaint(present=False),
)


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


def _response(**overrides: object) -> L3Response:
    defaults: dict[str, object] = {
        "markers": [],
        "knowledge_failure": KnowledgeFailureResponse(
            present=False, rule_id="", correct_statement=""
        ),
    }
    defaults.update(overrides)
    return L3Response(**defaults)  # type: ignore[arg-type]


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
    def __init__(self, rules: tuple[Rule, ...] = ()) -> None:
        self._rules = rules

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
        return self._rules


class _FakeStageCache(StageCache):
    def __init__(self) -> None:
        self.store: dict[StageCacheKey, str] = {}

    async def get(self, key: StageCacheKey) -> str | None:
        return self.store.get(key)

    async def put(self, key: StageCacheKey, value: str) -> None:
        self.store[key] = value


class _FakeExtractions(CallExtractionRepository):
    def __init__(self, l2: CallExtraction | None = _L2_EXTRACTION) -> None:
        self._l2 = l2
        self.saved: dict[str, L3Save] = {}

    async def get(self, call_reference: str) -> CallExtraction | None:
        return self._l2

    async def save_l2(self, call_reference: str, result: L2Save) -> None:
        raise NotImplementedError

    async def save_l3(self, call_reference: str, result: L3Save) -> None:
        self.saved[call_reference] = result

    async def save_l4(self, call_reference: str, result: L4Save) -> None:
        raise NotImplementedError

    async def mark_l3_provisional(self, call_reference: str) -> None:
        raise NotImplementedError


class FixedClock(Clock):
    def now(self) -> datetime:
        return _NOW


def _prompts() -> PromptSource:
    return FilePromptSource(PromptLibrary())


def _use_case(
    *,
    calls: CallRepository,
    lookup: ReferenceLookup,
    extractions: _FakeExtractions | None = None,
) -> tuple[ClassifyCallL3, _FakeExtractions]:
    store = extractions if extractions is not None else _FakeExtractions()
    use_case = ClassifyCallL3(
        calls=calls,
        reference_lookup=lookup,
        prompts=_prompts(),
        stage_cache=_FakeStageCache(),
        extractions=store,
        rubric=rubric(dimension("empathy", negative=8, max_negative=24)),
        clock=FixedClock(),
    )
    return use_case, store


class TestBasicScoring:
    async def test_a_call_with_no_markers_scores_the_base_and_persists(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, extractions = _use_case(calls=calls, lookup=_FakeLookup())

        result = await use_case.execute("C-0001", FakeProvider(_response()))

        assert result.quality.score_result.score.value == 100
        assert result.quality.score_result.status is ScoreStatus.CONFIRMED
        assert "C-0001" in extractions.saved
        assert extractions.saved["C-0001"].score_result.score.value == 100

    async def test_a_genuine_negative_marker_lowers_the_score(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, _ = _use_case(calls=calls, lookup=_FakeLookup())
        response = _response(
            markers=[
                MarkerResponse(
                    dimension="empathy",
                    polarity="NEGATIVE",
                    description="Dismissed the member's frustration.",
                    quote="it's not covered",
                    turn_seq=1,
                )
            ]
        )

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert result.quality.score_result.score.value == 92
        assert len(result.quality.markers) == 1

    async def test_an_unknown_call_reference_is_refused(self) -> None:
        use_case, _ = _use_case(calls=_FakeCalls(), lookup=_FakeLookup())

        with pytest.raises(ValidationError, match="no ingested call"):
            await use_case.execute("C-9999", FakeProvider(_response()))

    async def test_a_call_with_no_transcript_is_refused(self) -> None:
        calls = _FakeCalls(
            (_call(transcript=None, resolution_status=CallResolutionStatus.SPEAKER_UNRESOLVED),)
        )
        use_case, _ = _use_case(calls=calls, lookup=_FakeLookup())

        with pytest.raises(ValidationError, match="no usable transcript"):
            await use_case.execute("C-0001", FakeProvider(_response()))

    async def test_a_call_with_no_l2_classification_yet_is_refused(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, _ = _use_case(
            calls=calls, lookup=_FakeLookup(), extractions=_FakeExtractions(l2=None)
        )

        with pytest.raises(ValidationError, match="no L2 classification"):
            await use_case.execute("C-0001", FakeProvider(_response()))


class TestMarkerEvidence:
    async def test_a_dimension_outside_the_rubric_refuses_the_marker_not_the_call(self) -> None:
        """Refuse the marker, score the rest — the Call Quality Framework's
        own handling ("Refused, zero points").

        Not reachable from a hallucination: `MarkerResponse.dimension` is a
        Literal of the six, so an invented name fails schema validation at
        the provider boundary. It is reachable from *drift*. The rubric is
        data — `config/rubric.yaml`, versioned, "weights are data, not
        code" — and the DTO's Literal is code, so a rubric that drops or
        renames a dimension still admits it through the schema and then
        hits `Rubric.dimension()`, which raises. That failed the whole L3
        pass for the call. This rubric defines only `empathy`, which is
        exactly that situation.
        """
        calls = _FakeCalls((_call(),))
        use_case, extractions = _use_case(calls=calls, lookup=_FakeLookup())
        response = _response(
            markers=[
                MarkerResponse(
                    dimension="accuracy",
                    polarity="NEGATIVE",
                    description="Valid in the DTO, absent from this rubric.",
                    quote="it's not covered",
                    turn_seq=1,
                ),
                MarkerResponse(
                    dimension="empathy",
                    polarity="NEGATIVE",
                    description="Dismissed the member's frustration.",
                    quote="it's not covered",
                    turn_seq=1,
                ),
            ]
        )

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert [m.dimension for m in result.quality.markers] == ["empathy"]
        assert result.rejected_markers.has_rejections
        rejected = result.rejected_markers.rejected[0]
        assert rejected.reason is EvidenceRejection.UNKNOWN_DIMENSION
        assert "does not define" in rejected.explanation
        # Both are stored, refused one included — the Data Model sheet keeps
        # markers at marker level "so a refused marker is visible".
        assert len(extractions.saved["C-0001"].markers) == 2

    async def test_every_marker_naming_an_unknown_dimension_is_not_a_quiet_call(self) -> None:
        """`all_rejected` has to see refusals made before the transcript was
        consulted. A call whose every marker named a dimension this rubric
        does not define is a call nobody has evidenced, not a call with
        nothing to report — and the framework scores those two very
        differently.
        """
        calls = _FakeCalls((_call(),))
        use_case, _ = _use_case(calls=calls, lookup=_FakeLookup())
        response = _response(
            markers=[
                MarkerResponse(
                    dimension="accuracy",
                    polarity="NEGATIVE",
                    description="Valid in the DTO, absent from this rubric.",
                    quote="it's not covered",
                    turn_seq=1,
                )
            ]
        )

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert result.rejected_markers.all_rejected is True

    async def test_an_invented_quote_is_rejected_not_scored(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, extractions = _use_case(calls=calls, lookup=_FakeLookup())
        response = _response(
            markers=[
                MarkerResponse(
                    dimension="empathy",
                    polarity="NEGATIVE",
                    description="Invented.",
                    quote="never said this at all",
                    turn_seq=1,
                )
            ]
        )

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert result.quality.markers == ()
        assert result.quality.score_result.score.value == 100
        assert result.rejected_markers.has_rejections
        # Refused markers are still stored, per the Data Model sheet.
        assert len(extractions.saved["C-0001"].markers) == 1
        assert extractions.saved["C-0001"].markers[0].verification_status != "accepted"

    async def test_every_marker_rejected_leaves_the_score_provisional(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, _ = _use_case(calls=calls, lookup=_FakeLookup())
        response = _response(
            markers=[
                MarkerResponse(
                    dimension="empathy",
                    polarity="NEGATIVE",
                    description="Invented.",
                    quote="never said this at all",
                    turn_seq=1,
                )
            ]
        )

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert result.quality.score_result.is_provisional


class TestKnowledgeFailure:
    async def test_a_rule_id_within_the_scoped_set_is_accepted(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, _ = _use_case(calls=calls, lookup=_FakeLookup(rules=(_DENTAL_RULE,)))
        response = _response(
            knowledge_failure=KnowledgeFailureResponse(
                present=True,
                rule_id="C-01",
                correct_statement="Orthodontia needs the PPO design.",
            )
        )

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert result.quality.knowledge_failure.present
        assert result.quality.knowledge_failure.rule_id == "C-01"

    async def test_a_rule_id_outside_the_scoped_set_is_rejected_as_a_hallucination(self) -> None:
        # The call is dental-only; C-02 is a vision rule and was never
        # shown to the model.
        calls = _FakeCalls((_call(),))
        use_case, _ = _use_case(calls=calls, lookup=_FakeLookup(rules=(_DENTAL_RULE,)))
        response = _response(
            knowledge_failure=KnowledgeFailureResponse(
                present=True,
                rule_id="C-02",
                correct_statement="Frames every 24 months.",
            )
        )

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert not result.quality.knowledge_failure.present

    async def test_present_true_with_no_correct_statement_is_treated_as_absent(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, _ = _use_case(calls=calls, lookup=_FakeLookup(rules=(_DENTAL_RULE,)))
        response = _response(
            knowledge_failure=KnowledgeFailureResponse(
                present=True, rule_id="C-01", correct_statement=""
            )
        )

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert not result.quality.knowledge_failure.present


class TestRuleScoping:
    async def test_only_rules_for_the_calls_own_product_lines_reach_the_prompt(self) -> None:
        # _L2_EXTRACTION's call touches dental only.
        calls = _FakeCalls((_call(),))
        provider = FakeProvider(_response())
        use_case, _ = _use_case(calls=calls, lookup=_FakeLookup(rules=(_DENTAL_RULE, _VISION_RULE)))

        await use_case.execute("C-0001", provider)

        prompt_text = provider.requests[0].prompt
        assert "C-01" in prompt_text
        assert "C-02" not in prompt_text


class TestStageCache:
    async def test_a_second_call_with_the_same_key_does_not_call_the_provider_again(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, _ = _use_case(calls=calls, lookup=_FakeLookup())
        provider = FakeProvider(_response())

        await use_case.execute("C-0001", provider)
        await use_case.execute("C-0001", provider)

        assert len(provider.requests) == 1
