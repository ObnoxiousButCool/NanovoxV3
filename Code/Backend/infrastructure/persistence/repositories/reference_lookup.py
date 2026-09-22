"""SQLAlchemy implementation of `ReferenceLookup`.

Reads the rows Phase 1's importer wrote and maps them back onto the same
domain entities it imported them from — the reverse of
`SqlReferenceRepository`'s upsert direction.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports.reference_lookup import ReferenceLookup
from domain.entities.agent import Agent
from domain.entities.employer_contact import EmployerContact
from domain.entities.member import Member
from domain.value_objects.authority import Authority
from infrastructure.persistence.tables import AgentRow, EmployerContactRow, EmployerRow, MemberRow


class SqlReferenceLookup(ReferenceLookup):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def find_agent(self, reference: str) -> Agent | None:
        async with self._session_factory() as session:
            row = (
                await session.execute(select(AgentRow).where(AgentRow.reference == reference))
            ).scalar_one_or_none()
            if row is None:
                return None
            return Agent(
                reference=row.reference,
                name=row.name,
                band=row.band,
                planned_calls=row.planned_calls,
                expected_score=row.expected_score,
                score_variance=row.score_variance,
                dominant_pattern=row.dominant_pattern,
            )

    async def find_member(self, reference: str) -> Member | None:
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(MemberRow, EmployerRow.reference)
                    .join(EmployerRow, MemberRow.employer_id == EmployerRow.id)
                    .where(MemberRow.reference == reference)
                )
            ).first()
            if row is None:
                return None
            member_row, employer_reference = row
            return Member(
                reference=member_row.reference,
                name=member_row.name,
                age=member_row.age,
                employer_ref=employer_reference,
                primary_line=member_row.primary_line,
                planned_calls=member_row.planned_calls,
                repeat_caller=member_row.repeat_caller,
            )

    async def find_employer_contact(self, reference: str) -> EmployerContact | None:
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(EmployerContactRow, EmployerRow.reference)
                    .join(EmployerRow, EmployerContactRow.employer_id == EmployerRow.id)
                    .where(EmployerContactRow.reference == reference)
                )
            ).first()
            if row is None:
                return None
            contact_row, employer_reference = row
            return EmployerContact(
                reference=contact_row.reference,
                name=contact_row.name,
                role=contact_row.role,
                authority=Authority(contact_row.authority),
                employer_ref=employer_reference,
                planned_calls=contact_row.planned_calls,
            )
