"""`ClassifyCallL4` orchestration, with every port faked."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from application.dto.l4_response import L4Response, ProcessGapResponse, SignalResponse
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
from application.use_cases.classify_call_l4 import ClassifyCallL4
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
from domain.value_objects.category import Category
from domain.value_objects.complaint import Complaint
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.escalation import Escalation
from domain.value_objects.escalation_trigger_type import EscalationTriggerType
from domain.value_objects.preventable import Preventable
from domain.value_objects.process_gap import ProcessGapStatus, RaisedBy
from domain.value_objects.product_line import ProductLine
from domain.value_objects.root_cause_owner import RootCauseOwner
from domain.value_objects.signal_type import SignalType
from domain.value_objects.speaker_role import SpeakerRole
from infrastructure.llm.prompt_source import FilePromptSource
from infrastructure.llm.prompts import PromptLibrary
from tests.support.llm import FakeProvider

_NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)

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
        Turn(role=SpeakerRole.CALLER, text="Nobody ever applied my portal submission."),
        Turn(role=SpeakerRole.AGENT, text="I'll raise that with operations today."),
    ),
)


def _l2(**overrides: object) -> CallExtraction:
    defaults: dict[str, object] = {
        "call_reference": "C-0001",
        "outcome": None,
        "category": Category.CLAIMS_AND_EOB,
        "product_lines": (ProductLine.DENTAL,),
        "complaint": Complaint(present=False),
        "escalation_triggered": False,
        "escalation_requested_by_caller": False,
        "touchpoint": None,
    }
    defaults.update(overrides)
    return CallExtraction(**defaults)  # type: ignore[arg-type]


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


def _response(**overrides: object) -> L4Response:
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
    def __init__(self, l2: CallExtraction | None) -> None:
        self._l2 = l2
        self.saved: dict[str, L4Save] = {}

    async def get(self, call_reference: str) -> CallExtraction | None:
        return self._l2

    async def save_l2(self, call_reference: str, result: L2Save) -> None:
        raise NotImplementedError

    async def save_l3(self, call_reference: str, result: L3Save) -> None:
        raise NotImplementedError

    async def save_l4(self, call_reference: str, result: L4Save) -> None:
        self.saved[call_reference] = result

    async def mark_l3_provisional(self, call_reference: str) -> None:
        raise NotImplementedError


class FixedClock(Clock):
    def now(self) -> datetime:
        return _NOW


def _prompts() -> PromptSource:
    return FilePromptSource(PromptLibrary())


_UNSET = _l2()


def _use_case(
    *, calls: CallRepository, lookup: ReferenceLookup, l2: CallExtraction | None = _UNSET
) -> tuple[ClassifyCallL4, _FakeExtractions]:
    store = _FakeExtractions(l2=l2)
    use_case = ClassifyCallL4(
        calls=calls,
        reference_lookup=lookup,
        prompts=_prompts(),
        stage_cache=_FakeStageCache(),
        extractions=store,
        clock=FixedClock(),
    )
    return use_case, store


class TestBasics:
    async def test_a_quiet_call_persists_no_signals_and_no_gap(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, extractions = _use_case(calls=calls, lookup=_FakeLookup())

        result = await use_case.execute("C-0001", FakeProvider(_response()))

        assert result.findings.signals == ()
        assert not result.findings.process_gap.present
        assert extractions.saved["C-0001"].signals == ()

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
        use_case, _ = _use_case(calls=calls, lookup=_FakeLookup(), l2=None)

        with pytest.raises(ValidationError, match="no L2 classification"):
            await use_case.execute("C-0001", FakeProvider(_response()))


class TestSignalEvidence:
    async def test_a_genuine_quote_is_accepted(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, _ = _use_case(calls=calls, lookup=_FakeLookup())
        response = _response(
            signals=[
                SignalResponse(
                    type="process_breakdown",
                    quote="Nobody ever applied my portal submission",
                    turn_seq=1,
                )
            ]
        )

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert len(result.findings.signals) == 1
        assert result.findings.signals[0].type is SignalType.PROCESS_BREAKDOWN

    async def test_an_invented_quote_is_rejected_not_persisted(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, extractions = _use_case(calls=calls, lookup=_FakeLookup())
        response = _response(
            signals=[SignalResponse(type="billing_defect", quote="never said this", turn_seq=1)]
        )

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert result.findings.signals == ()
        assert result.rejected_signals.has_rejections
        assert extractions.saved["C-0001"].signals == ()


class TestEscalationTriggerType:
    async def test_a_trigger_type_is_classified_when_l2_found_one(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, _ = _use_case(
            calls=calls, lookup=_FakeLookup(), l2=_l2(escalation_triggered=True)
        )
        response = _response(escalation_trigger_type="authority_limit")

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert result.findings.escalation_trigger_type is EscalationTriggerType.AUTHORITY_LIMIT

    async def test_a_trigger_type_is_ignored_when_l2_found_none(self) -> None:
        # L2 says untriggered; a model naming a type anyway is disagreeing
        # with L2, not classifying something L2 confirmed exists.
        calls = _FakeCalls((_call(),))
        use_case, _ = _use_case(
            calls=calls, lookup=_FakeLookup(), l2=_l2(escalation_triggered=False)
        )
        response = _response(escalation_trigger_type="authority_limit")

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert result.findings.escalation_trigger_type is None


class TestEscalationHandled:
    async def test_handled_is_kept_when_l2_found_an_escalation(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, _ = _use_case(
            calls=calls, lookup=_FakeLookup(), l2=_l2(escalation_triggered=True)
        )
        response = _response(escalation_handled=True)

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert result.findings.escalation_handled is True

    async def test_handled_is_refused_when_l2_found_no_escalation(self) -> None:
        """ "Handled" is a property of an escalation, not of a call.

        Asked on a call that never escalated, a model answers yes — nothing
        went wrong — and the answer stores as "never triggered, but
        handled". `Escalation` refuses to construct that, so it reached
        production as a 500 on every insights endpoint once real extractions
        existed. Thirty-eight rows of it.
        """
        calls = _FakeCalls((_call(),))
        use_case, _ = _use_case(
            calls=calls, lookup=_FakeLookup(), l2=_l2(escalation_triggered=False)
        )
        response = _response(escalation_handled=True)

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert result.findings.escalation_handled is False

    async def test_what_is_stored_can_always_be_read_back(self) -> None:
        """The invariant the reader enforces, asserted where it is produced."""
        calls = _FakeCalls((_call(),))
        use_case, _ = _use_case(
            calls=calls, lookup=_FakeLookup(), l2=_l2(escalation_triggered=False)
        )
        response = _response(escalation_handled=True, escalation_trigger_type="authority_limit")

        result = await use_case.execute("C-0001", FakeProvider(response))

        Escalation(
            triggered=False,
            trigger_type=(
                result.findings.escalation_trigger_type.value
                if result.findings.escalation_trigger_type
                else None
            ),
            handled=result.findings.escalation_handled,
        )


class TestProcessGap:
    async def test_a_complete_process_gap_is_accepted(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, _ = _use_case(calls=calls, lookup=_FakeLookup())
        response = _response(
            process_gap=ProcessGapResponse(
                present=True,
                gap_type="portal submission not applied",
                touchpoint="portal_submission",
                proposed_change="Alert operations when a submission sits unapplied for 48 hours.",
                raised_by="CALLER",
                status="UNVALIDATED",
            )
        )

        result = await use_case.execute("C-0001", FakeProvider(response))

        gap = result.findings.process_gap
        assert gap.present
        assert gap.raised_by is RaisedBy.CALLER
        assert gap.status is ProcessGapStatus.UNVALIDATED

    async def test_present_true_with_a_none_raised_by_is_treated_as_absent(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, _ = _use_case(calls=calls, lookup=_FakeLookup())
        response = _response(
            process_gap=ProcessGapResponse(
                present=True,
                gap_type="something",
                touchpoint="",
                proposed_change="something",
                raised_by="NONE",
                status="UNVALIDATED",
            )
        )

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert not result.findings.process_gap.present

    @pytest.mark.parametrize("blank", ["gap_type", "proposed_change"])
    async def test_present_true_with_a_blank_required_field_is_treated_as_absent(
        self, blank: str
    ) -> None:
        """A gap with no type or no proposed change is not a finding, so the
        answer is dropped rather than failing the whole L4 pass."""
        calls = _FakeCalls((_call(),))
        use_case, _ = _use_case(calls=calls, lookup=_FakeLookup())
        fields = {
            "present": True,
            "gap_type": "portal submission not applied",
            "touchpoint": "portal_submission",
            "proposed_change": "Alert operations when a submission sits unapplied.",
            "raised_by": "CALLER",
            "status": "UNVALIDATED",
            blank: "  ",
        }
        response = _response(process_gap=ProcessGapResponse.model_validate(fields))

        result = await use_case.execute("C-0001", FakeProvider(response))

        assert not result.findings.process_gap.present


class TestRuleScoping:
    async def test_only_rules_for_the_calls_own_product_lines_reach_the_prompt(self) -> None:
        from domain.value_objects.rule_confidence import RuleConfidence
        from domain.value_objects.rule_layer import RuleLayer

        dental = Rule(
            reference="C-01",
            layer=RuleLayer.CARRIER,
            area="Ameritas — dental PPO",
            text="Dental rule text.",
            commonly_confused_with="",
            source="Test",
            confidence=RuleConfidence.VERIFIED,
        )
        vision = Rule(
            reference="C-02",
            layer=RuleLayer.CARRIER,
            area="EyeMed — vision",
            text="Vision rule text.",
            commonly_confused_with="",
            source="Test",
            confidence=RuleConfidence.VERIFIED,
        )
        calls = _FakeCalls((_call(),))
        use_case, _ = _use_case(calls=calls, lookup=_FakeLookup(rules=(dental, vision)))
        provider = FakeProvider(_response())

        await use_case.execute("C-0001", provider)

        prompt_text = provider.requests[0].prompt
        assert "C-01" in prompt_text
        assert "C-02" not in prompt_text


class TestRootCauseOwnerAndPreventable:
    async def test_a_complaints_attribution_is_saved_as_the_owner(self) -> None:
        """Computed, not extracted — see `domain/derivations/root_cause.py`.
        The complaint comes from L2's own saved classification, never from
        anything L4's model answers."""
        calls = _FakeCalls((_call(),))
        l2 = _l2(
            complaint=Complaint(present=True, attributed_to=ComplaintAttribution.BROKER),
        )
        use_case, extractions = _use_case(calls=calls, lookup=_FakeLookup(), l2=l2)

        await use_case.execute("C-0001", FakeProvider(_response()))

        assert extractions.saved["C-0001"].root_cause_owner is RootCauseOwner.BROKER
        assert extractions.saved["C-0001"].preventable is Preventable.PARTLY

    async def test_a_blameless_call_still_gets_an_owner_and_a_preventable_value(self) -> None:
        """§9's own gap statement: a third of calls carried no owner at all
        — `MEMBER_MISUNDERSTANDING` closes it, on every call, not only
        complaint calls (`Corpus-v10-Decisions.md` item A)."""
        calls = _FakeCalls((_call(),))
        use_case, extractions = _use_case(calls=calls, lookup=_FakeLookup(), l2=_l2())

        await use_case.execute("C-0001", FakeProvider(_response()))

        owner = RootCauseOwner.MEMBER_MISUNDERSTANDING
        assert extractions.saved["C-0001"].root_cause_owner is owner
        assert extractions.saved["C-0001"].preventable is Preventable.PARTLY

    async def test_the_most_severe_owned_signal_wins_with_no_complaint(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, extractions = _use_case(calls=calls, lookup=_FakeLookup(), l2=_l2())
        response = _response(
            signals=[
                SignalResponse(
                    type="broker_conduct_adverse",
                    quote="Nobody ever applied my portal submission",
                    turn_seq=1,
                )
            ]
        )

        await use_case.execute("C-0001", FakeProvider(response))

        assert extractions.saved["C-0001"].root_cause_owner is RootCauseOwner.BROKER
        assert extractions.saved["C-0001"].preventable is Preventable.PARTLY


class TestStageCache:
    async def test_a_second_call_with_the_same_key_does_not_call_the_provider_again(self) -> None:
        calls = _FakeCalls((_call(),))
        use_case, _ = _use_case(calls=calls, lookup=_FakeLookup())
        provider = FakeProvider(_response())

        await use_case.execute("C-0001", provider)
        await use_case.execute("C-0001", provider)

        assert len(provider.requests) == 1
