"""Ingest every call from a `TranscriptSource`.

Resolves the agent against the 20 known agents and the caller against
Phase 1's reference data — never against the transcript's own header text
taken on faith. Every call is persisted regardless of outcome; nothing here
decides to drop one.
"""

from __future__ import annotations

from application.ports.call_repository import CallRepository, IngestCounts
from application.ports.reference_lookup import ReferenceLookup
from application.ports.transcript_source import RawCallRecord, TranscriptSource
from domain.entities.ingested_call import IngestedCall
from domain.entities.transcript import Transcript
from domain.value_objects.call_resolution_status import CallResolutionStatus
from domain.value_objects.caller_type import CallerType


class IngestTranscripts:
    def __init__(
        self, source: TranscriptSource, lookup: ReferenceLookup, repository: CallRepository
    ) -> None:
        self._source = source
        self._lookup = lookup
        self._repository = repository

    async def execute(self) -> IngestCounts:
        records = self._source.read()
        calls = tuple([await self._resolve(record) for record in records])
        return await self._repository.upsert_all(calls)

    async def _resolve(self, record: RawCallRecord) -> IngestedCall:
        if record.turns is None:
            return IngestedCall(
                reference=record.reference,
                caller_type=record.caller_type,
                caller_ref=record.caller_ref,
                agent_ref=record.agent_ref,
                transcript=None,
                resolution_status=CallResolutionStatus.SPEAKER_UNRESOLVED,
                resolution_reason=record.unresolved_reason,
                member_ref=None,
                employer_contact_ref=None,
                employer_ref=None,
            )

        transcript = Transcript(
            reference=record.reference,
            source=record.source,
            occurred_at=record.occurred_at,
            aht_seconds=record.aht_seconds,
            caller_type=record.caller_type,
            caller_ref=record.caller_ref,
            agent_ref=record.agent_ref,
            agent_name=record.agent_name,
            turns=record.turns,
        )

        agent = await self._lookup.find_agent(record.agent_ref)
        if agent is None:
            return IngestedCall(
                reference=record.reference,
                caller_type=record.caller_type,
                caller_ref=record.caller_ref,
                agent_ref=record.agent_ref,
                transcript=transcript,
                resolution_status=CallResolutionStatus.AGENT_UNKNOWN,
                resolution_reason=(
                    f"agent_ref {record.agent_ref!r} is not among the imported agents"
                ),
                member_ref=None,
                employer_contact_ref=None,
                employer_ref=None,
            )

        member_ref, contact_ref, employer_ref, reason = await self._resolve_caller(record)
        status = (
            CallResolutionStatus.RESOLVED
            if reason is None
            else CallResolutionStatus.CALLER_UNRESOLVED
        )
        return IngestedCall(
            reference=record.reference,
            caller_type=record.caller_type,
            caller_ref=record.caller_ref,
            agent_ref=record.agent_ref,
            transcript=transcript,
            resolution_status=status,
            resolution_reason=reason,
            member_ref=member_ref,
            employer_contact_ref=contact_ref,
            employer_ref=employer_ref,
        )

    async def _resolve_caller(
        self, record: RawCallRecord
    ) -> tuple[str | None, str | None, str | None, str | None]:
        """`(member_ref, employer_contact_ref, employer_ref, unresolved_reason)`."""
        if record.caller_type is CallerType.MEMBER:
            member = await self._lookup.find_member(record.caller_ref)
            if member is None:
                return None, None, None, f"caller_ref {record.caller_ref!r} is not a known member"
            return member.reference, None, member.employer_ref, None

        contact = await self._lookup.find_employer_contact(record.caller_ref)
        if contact is None:
            return (
                None,
                None,
                None,
                f"caller_ref {record.caller_ref!r} is not a known employer contact",
            )
        return None, contact.reference, contact.employer_ref, None
