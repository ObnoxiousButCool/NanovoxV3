"""`ClassifyCallL2` orchestration, with every port faked."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from application.dto.l2_response import (
    BrokerNamedAloudResponse,
    ComplaintResponse,
    IntentStatementResponse,
    L2Response,
)
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
from application.use_cases.classify_call_l2 import ClassifyCallL2
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
from domain.errors import ValidationError
from domain.value_objects.call_resolution_status import CallResolutionStatus
from domain.value_objects.call_source import CallSource
from domain.value_objects.caller_type import CallerType
from domain.value_objects.control_exception_type import ControlExceptionType
from domain.value_objects.speaker_role import SpeakerRole
from infrastructure.llm.prompt_source import FilePromptSource
from infrastructure.llm.prompts import PromptLibrary
from tests.support.llm import FakeProvider

_NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)

_MARCUS_TRENT = Broker(
    reference="BRK-02",
    name="Marcus Trent",
    agency="Trent Benefits",
    region="Orange County",
    groups_in_book=6,
    signal_profile="Stable",
)
_KAREN_LINDQVIST = Broker(
    reference="BRK-05",
    name="Karen Lindqvist",
    agency="Lindqvist Group",
    region="Bay Area",
    groups_in_book=9,
    signal_profile="Watch",
)
_EMPLOYER = Employer(
    reference="EMP-1001",
    name="Cedar Point Workforce Partners",
    industry="Staffing & Recruitment",
    design_churn_profile="High",
    eligible=420,
    enrolled=315,
    region="Orange County",
    renewal_month="Jan",
    broker_ref="BRK-02",
    dental_sponsorship="ER",
    lines_held="Dental",
    planned_calls=36,
    planned_member_calls=24,
    planned_employer_calls=12,
    participation=0.75,
    fee_band=50,
    annual_fee=600,
    annual_premium=153090.0,
    cobra_regime="Federal COBRA",
    calls_per_100=11.43,
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
        Turn(role=SpeakerRole.CALLER, text="Leon Castellano. CB-7700205."),
        Turn(role=SpeakerRole.CALLER, text="By email to Marcus Trent, our broker."),
    ),
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


def _response(**overrides: object) -> L2Response:
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
    def __init__(
        self,
        brokers: tuple[Broker, ...] = (),
        employers: tuple[Employer, ...] = (),
        rules: tuple[Rule, ...] = (),
    ) -> None:
        self._brokers = brokers
        self._employers = {employer.reference: employer for employer in employers}
        self._rules = rules

    async def find_agent(self, reference: str) -> Agent | None:
        return None

    async def find_member(self, reference: str) -> Member | None:
        return None

    async def find_employer_contact(self, reference: str) -> EmployerContact | None:
        return None

    async def find_employer(self, reference: str) -> Employer | None:
        return self._employers.get(reference)

    async def list_brokers(self) -> tuple[Broker, ...]:
        return self._brokers

    async def list_rules(self) -> tuple[Rule, ...]:
        return self._rules

    async def list_touchpoints(self) -> tuple[Touchpoint, ...]:
        return ()


class _FakeStageCache(StageCache):
    def __init__(self) -> None:
        self.store: dict[StageCacheKey, str] = {}

    async def get(self, key: StageCacheKey) -> str | None:
        return self.store.get(key)

    async def put(self, key: StageCacheKey, value: str) -> None:
        self.store[key] = value


class _FakeExtractions(CallExtractionRepository):
    def __init__(self) -> None:
        self.saved: dict[str, L2Save] = {}

    async def get(self, call_reference: str) -> CallExtraction | None:
        raise NotImplementedError

    async def save_l2(self, call_reference: str, result: L2Save) -> None:
        self.saved[call_reference] = result

    async def save_l3(self, call_reference: str, result: L3Save) -> None:
        raise NotImplementedError

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
    stage_cache: StageCache | None = None,
    extractions: CallExtractionRepository | None = None,
) -> tuple[ClassifyCallL2, _FakeStageCache, _FakeExtractions]:
    cache = stage_cache or _FakeStageCache()
    store = extractions or _FakeExtractions()
    use_case = ClassifyCallL2(
        calls=calls,
        reference_lookup=lookup,
        prompts=_prompts(),
        stage_cache=cache,
        extractions=store,
        clock=FixedClock(),
    )
    assert isinstance(cache, _FakeStageCache)
    assert isinstance(store, _FakeExtractions)
    return use_case, cache, store


class TestBasicClassification:
    async def test_a_call_is_classified_and_persisted(self) -> None:
        calls = _FakeCalls((_call(),))
        lookup = _FakeLookup(employers=(_EMPLOYER,))
        use_case, _, extractions = _use_case(calls=calls, lookup=lookup)
        provider = FakeProvider(_response())

        result = await use_case.execute("C-0001", provider)

        assert result.classification.outcome.value == "RESOLVED"
        assert "C-0001" in extractions.saved
        assert extractions.saved["C-0001"].outcome.value == "RESOLVED"

    async def test_l1s_control_exceptions_are_saved_with_the_classification(self) -> None:
        """L1 runs inside L2 and has no save of its own, so what it found in
        the greeting has to travel with L2's — otherwise metric 7 has
        nothing to score."""
        calls = _FakeCalls((_call(),))
        lookup = _FakeLookup(employers=(_EMPLOYER,))
        use_case, _, extractions = _use_case(calls=calls, lookup=lookup)

        await use_case.execute("C-0001", FakeProvider(_response()))

        # "Choice Administrators, Sarah speaking." — no recording notice and
        # no request to verify the caller.
        assert extractions.saved["C-0001"].control_exceptions == {
            ControlExceptionType.NO_RECORDING_DISCLOSURE,
            ControlExceptionType.DISCLOSURE_BEFORE_VERIFICATION,
        }

    async def test_an_unknown_call_reference_is_refused(self) -> None:
        use_case, _, _ = _use_case(calls=_FakeCalls(), lookup=_FakeLookup())

        with pytest.raises(ValidationError, match="no ingested call"):
            await use_case.execute("C-9999", FakeProvider(_response()))

    async def test_a_call_with_no_transcript_is_refused(self) -> None:
        calls = _FakeCalls(
            (_call(transcript=None, resolution_status=CallResolutionStatus.SPEAKER_UNRESOLVED),)
        )
        use_case, _, _ = _use_case(calls=calls, lookup=_FakeLookup())

        with pytest.raises(ValidationError, match="no usable transcript"):
            await use_case.execute("C-0001", FakeProvider(_response()))


class TestIntentEvidence:
    async def test_a_genuine_quote_is_accepted(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, _, _ = _use_case(calls=calls, lookup=_FakeLookup())
        response = _response(
            intent=[
                IntentStatementResponse(
                    type="market_test", quote="Marcus Trent, our broker", turn_seq=2
                )
            ]
        )

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert len(result.classification.intent) == 1
        assert not result.rejected_intent.has_rejections

    async def test_an_invented_quote_is_rejected_not_persisted(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, _, extractions = _use_case(calls=calls, lookup=_FakeLookup())
        response = _response(
            intent=[
                IntentStatementResponse(type="cancellation", quote="never said this", turn_seq=1)
            ]
        )

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert result.classification.intent == ()
        assert result.rejected_intent.has_rejections
        assert extractions.saved["C-0001"].intent == ()


class TestBrokerMentionValidation:
    async def test_a_broker_matching_l1s_own_candidate_is_accepted(self) -> None:
        # The transcript names "Marcus Trent" — L1 will independently spot
        # BRK-02 from that same text.
        calls = _FakeCalls((_call(),))
        lookup = _FakeLookup(brokers=(_MARCUS_TRENT,), employers=(_EMPLOYER,))
        use_case, _, _ = _use_case(calls=calls, lookup=lookup)
        response = _response(
            broker_named_aloud=BrokerNamedAloudResponse(
                present=True, broker_ref="BRK-02", sentiment="ADVERSE"
            )
        )

        result = await use_case.execute("C-0001", FakeProvider(response))

        mention = result.classification.broker_named_aloud
        assert mention.present
        assert mention.broker_ref == "BRK-02"
        assert mention.matches_employer_of_record is True  # EMP-1001's own broker is BRK-02

    async def test_a_mismatch_with_the_employers_broker_of_record_is_flagged_not_hidden(
        self,
    ) -> None:
        calls = _FakeCalls((_call(),))
        # Employer's broker of record is BRK-02, but the transcript names a
        # different broker — flagged, not silently corrected either way.
        lookup = _FakeLookup(brokers=(_MARCUS_TRENT, _KAREN_LINDQVIST), employers=(_EMPLOYER,))
        transcript = Transcript(
            reference="C-0001",
            source=CallSource.CORPUS_PDF,
            occurred_at=None,
            aht_seconds=300,
            caller_type=CallerType.MEMBER,
            caller_ref="CB-7700205",
            agent_ref="AGT-01",
            agent_name="Sarah Whitlock",
            turns=(
                Turn(role=SpeakerRole.CALLER, text="Self ID."),
                Turn(role=SpeakerRole.CALLER, text="Karen Lindqvist set this up wrong."),
            ),
        )
        calls = _FakeCalls((_call(transcript=transcript),))
        use_case, _, _ = _use_case(calls=calls, lookup=lookup)
        response = _response(
            broker_named_aloud=BrokerNamedAloudResponse(
                present=True, broker_ref="BRK-05", sentiment="ADVERSE"
            )
        )

        result = await use_case.execute("C-0001", FakeProvider(response))

        mention = result.classification.broker_named_aloud
        assert mention.present
        assert mention.broker_ref == "BRK-05"
        assert mention.matches_employer_of_record is False

    async def test_a_broker_ref_l1_never_spotted_is_rejected_as_a_hallucination(self) -> None:
        # The model claims BRK-05 was named, but nothing in the transcript
        # says "Lindqvist" — L1 found no such candidate.
        calls = _FakeCalls((_call(),))
        lookup = _FakeLookup(brokers=(_MARCUS_TRENT, _KAREN_LINDQVIST), employers=(_EMPLOYER,))
        use_case, _, _ = _use_case(calls=calls, lookup=lookup)
        response = _response(
            broker_named_aloud=BrokerNamedAloudResponse(
                present=True, broker_ref="BRK-05", sentiment="ADVERSE"
            )
        )

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert not result.classification.broker_named_aloud.present

    async def test_an_unknown_broker_ref_is_rejected(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, _, _ = _use_case(calls=calls, lookup=_FakeLookup(employers=(_EMPLOYER,)))
        response = _response(
            broker_named_aloud=BrokerNamedAloudResponse(
                present=True, broker_ref="BRK-99", sentiment="ADVERSE"
            )
        )

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert not result.classification.broker_named_aloud.present

    async def test_present_true_with_sentiment_none_is_treated_as_absent(self) -> None:
        # An internally inconsistent answer must not crash the pipeline.
        calls = _FakeCalls((_call(),))
        lookup = _FakeLookup(brokers=(_MARCUS_TRENT,), employers=(_EMPLOYER,))
        use_case, _, _ = _use_case(calls=calls, lookup=lookup)
        response = _response(
            broker_named_aloud=BrokerNamedAloudResponse(
                present=True, broker_ref="BRK-02", sentiment="NONE"
            )
        )

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert not result.classification.broker_named_aloud.present


class TestComplaintValidation:
    async def test_present_true_with_attribution_none_is_treated_as_absent(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, _, _ = _use_case(calls=calls, lookup=_FakeLookup())
        response = _response(complaint=ComplaintResponse(present=True, attributed_to="NONE"))

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert not result.classification.complaint.present


class TestImpactScopeAndIssues:
    async def test_primary_and_secondary_issues_are_saved_as_given(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, _, extractions = _use_case(calls=calls, lookup=_FakeLookup())
        response = _response(primary_issue="claims & eob", secondary_issues=["id card"])

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert result.classification.primary_issue == "claims & eob"
        assert result.classification.secondary_issues == ("id card",)
        assert extractions.saved["C-0001"].primary_issue == "claims & eob"
        assert extractions.saved["C-0001"].secondary_issues == ("id card",)

    async def test_an_empty_primary_issue_is_normalised_to_none(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, _, _ = _use_case(calls=calls, lookup=_FakeLookup())
        response = _response(primary_issue="")

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert result.classification.primary_issue is None

    async def test_a_bucket_needing_a_count_with_one_given_is_accepted(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, _, extractions = _use_case(calls=calls, lookup=_FakeLookup())
        response = _response(impact_scope="n_employees", impact_scope_count=11)

        result = await use_case.execute("C-0001", FakeProvider(response))

        scope = result.classification.impact_scope
        assert scope is not None
        assert scope.bucket.value == "n_employees"
        assert scope.count == 11
        assert extractions.saved["C-0001"].impact_scope == scope

    async def test_a_singular_bucket_with_no_count_is_accepted(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, _, _ = _use_case(calls=calls, lookup=_FakeLookup())
        response = _response(impact_scope="1_group", impact_scope_count=0)

        result = await use_case.execute("C-0001", FakeProvider(response))

        scope = result.classification.impact_scope
        assert scope is not None
        assert scope.bucket.value == "1_group"
        assert scope.count is None

    async def test_a_bucket_needing_a_count_with_none_given_is_dropped_not_crashed(self) -> None:
        """An internally inconsistent answer — a plural bucket with no count
        — must not crash the pipeline: it is treated as no usable impact
        scope at all, the same way every other malformed L2 answer is."""
        calls = _FakeCalls((_call(),))
        use_case, _, extractions = _use_case(calls=calls, lookup=_FakeLookup())
        response = _response(impact_scope="n_employees", impact_scope_count=0)

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert result.classification.impact_scope is None
        assert extractions.saved["C-0001"].impact_scope is None

    async def test_a_singular_bucket_with_a_count_is_dropped_not_crashed(self) -> None:
        """The reverse inconsistency: a bucket that carries no count given
        one anyway."""
        calls = _FakeCalls((_call(),))
        use_case, _, _ = _use_case(calls=calls, lookup=_FakeLookup())
        response = _response(impact_scope="1_member", impact_scope_count=5)

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert result.classification.impact_scope is None


class TestStageCache:
    async def test_a_second_call_with_the_same_key_does_not_call_the_provider_again(self) -> None:
        calls = _FakeCalls((_call(),))
        cache = _FakeStageCache()
        use_case, _, _ = _use_case(calls=calls, lookup=_FakeLookup(), stage_cache=cache)
        provider = FakeProvider(_response())

        await use_case.execute("C-0001", provider)
        await use_case.execute("C-0001", provider)

        assert len(provider.requests) == 1

    async def test_a_cache_hit_still_persists_the_result(self) -> None:
        calls = _FakeCalls((_call(),))
        cache = _FakeStageCache()
        use_case, _, extractions = _use_case(calls=calls, lookup=_FakeLookup(), stage_cache=cache)
        provider = FakeProvider(_response())

        await use_case.execute("C-0001", provider)
        extractions.saved.clear()
        await use_case.execute("C-0001", provider)

        assert "C-0001" in extractions.saved
