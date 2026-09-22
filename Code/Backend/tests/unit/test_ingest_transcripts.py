"""`IngestTranscripts` orchestration, with every port faked."""

from __future__ import annotations

from application.ports.call_repository import CallRepository, IngestCounts
from application.ports.reference_lookup import ReferenceLookup
from application.ports.transcript_source import RawCallRecord, TranscriptSource
from application.use_cases.ingest_transcripts import IngestTranscripts
from domain.entities.agent import Agent
from domain.entities.employer_contact import EmployerContact
from domain.entities.ingested_call import IngestedCall
from domain.entities.member import Member
from domain.entities.turn import Turn
from domain.value_objects.authority import Authority
from domain.value_objects.call_resolution_status import CallResolutionStatus
from domain.value_objects.call_source import CallSource
from domain.value_objects.caller_type import CallerType
from domain.value_objects.speaker_role import SpeakerRole

_AGENT = Agent(
    reference="AGT-01",
    name="Sarah Whitlock",
    band="Senior",
    planned_calls=32,
    expected_score=88.0,
    score_variance=7.0,
    dominant_pattern="Strong",
)
_MEMBER = Member(
    reference="CB-7700205",
    name="Leon Castellano",
    age=41,
    employer_ref="EMP-1001",
    primary_line="Dental",
    planned_calls=2,
    repeat_caller=False,
)
_CONTACT = EmployerContact(
    reference="CON-101",
    name="Quentin Thibault",
    role="Payroll Administrator",
    authority=Authority.CANNOT_BIND,
    employer_ref="EMP-1002",
    planned_calls=6,
)


def _resolved_record(reference: str, caller_ref: str) -> RawCallRecord:
    return RawCallRecord(
        reference=reference,
        source=CallSource.CORPUS_PDF,
        occurred_at=None,
        aht_seconds=100,
        caller_type=CallerType.MEMBER,
        caller_ref=caller_ref,
        agent_ref="AGT-01",
        agent_name="Sarah Whitlock",
        turns=(Turn(role=SpeakerRole.AGENT, text="hi"),),
        unresolved_reason=None,
    )


class _FakeSource(TranscriptSource):
    def __init__(self, records: tuple[RawCallRecord, ...]) -> None:
        self._records = records

    def read(self) -> tuple[RawCallRecord, ...]:
        return self._records


class _FakeLookup(ReferenceLookup):
    async def find_agent(self, reference: str) -> Agent | None:
        return _AGENT if reference == "AGT-01" else None

    async def find_member(self, reference: str) -> Member | None:
        return _MEMBER if reference == _MEMBER.reference else None

    async def find_employer_contact(self, reference: str) -> EmployerContact | None:
        return _CONTACT if reference == _CONTACT.reference else None


class _FakeRepository(CallRepository):
    def __init__(self) -> None:
        self.received: tuple[IngestedCall, ...] | None = None

    async def upsert_all(self, calls: tuple[IngestedCall, ...]) -> IngestCounts:
        self.received = calls
        return IngestCounts(
            total=len(calls), resolved=0, caller_unresolved=0, agent_unknown=0, speaker_unresolved=0
        )


async def test_a_fully_resolvable_call_is_marked_resolved_with_its_employer() -> None:
    source = _FakeSource((_resolved_record("C-0001", "CB-7700205"),))
    repository = _FakeRepository()
    use_case = IngestTranscripts(source=source, lookup=_FakeLookup(), repository=repository)

    await use_case.execute()

    (call,) = repository.received or ()
    assert call.resolution_status is CallResolutionStatus.RESOLVED
    assert call.member_ref == "CB-7700205"
    assert call.employer_ref == "EMP-1001"
    assert call.transcript is not None


async def test_an_unknown_caller_is_flagged_but_still_persisted() -> None:
    source = _FakeSource((_resolved_record("C-0002", "CB-9999999"),))
    repository = _FakeRepository()
    use_case = IngestTranscripts(source=source, lookup=_FakeLookup(), repository=repository)

    await use_case.execute()

    (call,) = repository.received or ()
    assert call.resolution_status is CallResolutionStatus.CALLER_UNRESOLVED
    assert call.member_ref is None
    assert call.employer_ref is None
    assert call.resolution_reason is not None
    assert "CB-9999999" in call.resolution_reason
    assert call.transcript is not None  # still usable, just not employer-linked


async def test_a_call_with_no_resolved_speakers_carries_no_transcript() -> None:
    unresolvable = RawCallRecord(
        reference="C-0003",
        source=CallSource.CORPUS_PDF,
        occurred_at=None,
        aht_seconds=None,
        caller_type=CallerType.MEMBER,
        caller_ref="CB-7700205",
        agent_ref="AGT-01",
        agent_name="Sarah Whitlock",
        turns=None,
        unresolved_reason="expected exactly two speakers, found 1: ['Sarah']",
    )
    source = _FakeSource((unresolvable,))
    repository = _FakeRepository()
    use_case = IngestTranscripts(source=source, lookup=_FakeLookup(), repository=repository)

    await use_case.execute()

    (call,) = repository.received or ()
    assert call.resolution_status is CallResolutionStatus.SPEAKER_UNRESOLVED
    assert call.transcript is None
    assert call.resolution_reason == unresolvable.unresolved_reason


async def test_an_unrecognised_agent_is_flagged() -> None:
    record = RawCallRecord(
        reference="C-0004",
        source=CallSource.CORPUS_PDF,
        occurred_at=None,
        aht_seconds=None,
        caller_type=CallerType.MEMBER,
        caller_ref="CB-7700205",
        agent_ref="AGT-99",
        agent_name="Nobody Known",
        turns=(Turn(role=SpeakerRole.AGENT, text="hi"),),
        unresolved_reason=None,
    )
    source = _FakeSource((record,))
    repository = _FakeRepository()
    use_case = IngestTranscripts(source=source, lookup=_FakeLookup(), repository=repository)

    await use_case.execute()

    (call,) = repository.received or ()
    assert call.resolution_status is CallResolutionStatus.AGENT_UNKNOWN
    assert call.member_ref is None


async def test_an_employer_caller_resolves_through_the_contact() -> None:
    record = RawCallRecord(
        reference="C-0005",
        source=CallSource.CORPUS_PDF,
        occurred_at=None,
        aht_seconds=None,
        caller_type=CallerType.EMPLOYER,
        caller_ref="CON-101",
        agent_ref="AGT-01",
        agent_name="Sarah Whitlock",
        turns=(Turn(role=SpeakerRole.AGENT, text="hi"),),
        unresolved_reason=None,
    )
    source = _FakeSource((record,))
    repository = _FakeRepository()
    use_case = IngestTranscripts(source=source, lookup=_FakeLookup(), repository=repository)

    await use_case.execute()

    (call,) = repository.received or ()
    assert call.resolution_status is CallResolutionStatus.RESOLVED
    assert call.employer_contact_ref == "CON-101"
    assert call.employer_ref == "EMP-1002"
