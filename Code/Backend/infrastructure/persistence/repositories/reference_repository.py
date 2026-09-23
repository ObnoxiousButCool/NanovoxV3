"""SQLAlchemy implementation of the reference-data repository.

Upsert is select-then-write rather than a dialect-specific `ON CONFLICT`, so
the same code runs against SQLite (development) and Postgres (decision D9)
without a database-specific branch. Reference-data volume is small (under a
thousand rows across every sheet at v9), so the extra round trip per row
costs nothing that matters.

Order matters: brokers before employers (employers hold `broker_id`),
employers before members and contacts (both hold `employer_id`) — enforced
by the single `upsert()` entry point, not left to the caller to get right.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.ports.reference_repository import ImportCounts, ReferenceRepository
from application.ports.reference_source import ReferenceDataset
from domain.entities.agent import Agent
from domain.entities.broker import Broker
from domain.entities.employer import Employer
from domain.entities.employer_contact import EmployerContact
from domain.entities.member import Member
from domain.entities.rule import Rule
from domain.entities.touchpoint import Touchpoint
from domain.errors import ReferenceIntegrityError
from infrastructure.persistence.tables import (
    AgentRow,
    BrokerRow,
    EmployerContactRow,
    EmployerRow,
    MemberRow,
    RuleRow,
    TouchpointRow,
)

_Row = TypeVar("_Row")


class SqlReferenceRepository(ReferenceRepository):
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def upsert(self, dataset: ReferenceDataset) -> ImportCounts:
        async with self._session_factory() as session, session.begin():
            broker_ids = await self._upsert_brokers(session, dataset.brokers)
            employer_ids = await self._upsert_employers(session, dataset.employers, broker_ids)
            member_count = await self._upsert_members(session, dataset.members, employer_ids)
            contact_count = await self._upsert_employer_contacts(
                session, dataset.employer_contacts, employer_ids
            )
            agent_count = await self._upsert_agents(session, dataset.agents)
            rule_count = await self._upsert_rules(session, dataset.rules)
            touchpoint_count = await self._upsert_touchpoints(session, dataset.touchpoints)

        return ImportCounts(
            brokers=len(broker_ids),
            employers=len(employer_ids),
            members=member_count,
            employer_contacts=contact_count,
            agents=agent_count,
            rules=rule_count,
            touchpoints=touchpoint_count,
        )

    async def _get_or_create(
        self, session: AsyncSession, row_type: type[_Row], reference: str
    ) -> _Row:
        result = await session.execute(
            select(row_type).where(row_type.reference == reference)  # type: ignore[attr-defined]
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = row_type(reference=reference)  # type: ignore[call-arg]
            session.add(row)
        return row

    async def _upsert_brokers(
        self, session: AsyncSession, brokers: Iterable[Broker]
    ) -> dict[str, int]:
        ids: dict[str, int] = {}
        for broker in brokers:
            row = await self._get_or_create(session, BrokerRow, broker.reference)
            row.name = broker.name
            row.agency = broker.agency
            row.region = broker.region
            row.groups_in_book = broker.groups_in_book
            row.signal_profile = broker.signal_profile
            await session.flush()
            ids[broker.reference] = row.id
        return ids

    async def _upsert_employers(
        self,
        session: AsyncSession,
        employers: Iterable[Employer],
        broker_ids: dict[str, int],
    ) -> dict[str, int]:
        ids: dict[str, int] = {}
        for employer in employers:
            broker_id = broker_ids.get(employer.broker_ref)
            if broker_id is None:
                raise ReferenceIntegrityError(
                    f"employer {employer.reference} names broker of record "
                    f"{employer.broker_ref!r}, which wasn't imported"
                )
            row = await self._get_or_create(session, EmployerRow, employer.reference)
            row.name = employer.name
            row.industry = employer.industry
            row.design_churn_profile = employer.design_churn_profile
            row.eligible = employer.eligible
            row.enrolled = employer.enrolled
            row.region = employer.region
            row.renewal_month = employer.renewal_month
            row.broker_id = broker_id
            row.dental_sponsorship = employer.dental_sponsorship
            row.lines_held = employer.lines_held
            row.planned_calls = employer.planned_calls
            row.planned_member_calls = employer.planned_member_calls
            row.planned_employer_calls = employer.planned_employer_calls
            row.participation = employer.participation
            row.fee_band = employer.fee_band
            row.annual_fee = employer.annual_fee
            row.annual_premium = employer.annual_premium
            row.cobra_regime = employer.cobra_regime
            row.calls_per_100 = employer.calls_per_100
            await session.flush()
            ids[employer.reference] = row.id
        return ids

    async def _upsert_members(
        self,
        session: AsyncSession,
        members: Iterable[Member],
        employer_ids: dict[str, int],
    ) -> int:
        count = 0
        for member in members:
            employer_id = employer_ids.get(member.employer_ref)
            if employer_id is None:
                raise ReferenceIntegrityError(
                    f"member {member.reference} belongs to employer "
                    f"{member.employer_ref!r}, which wasn't imported"
                )
            row = await self._get_or_create(session, MemberRow, member.reference)
            row.name = member.name
            row.age = member.age
            row.employer_id = employer_id
            row.primary_line = member.primary_line
            row.planned_calls = member.planned_calls
            row.repeat_caller = member.repeat_caller
            count += 1
        return count

    async def _upsert_employer_contacts(
        self,
        session: AsyncSession,
        contacts: Iterable[EmployerContact],
        employer_ids: dict[str, int],
    ) -> int:
        count = 0
        for contact in contacts:
            employer_id = employer_ids.get(contact.employer_ref)
            if employer_id is None:
                raise ReferenceIntegrityError(
                    f"contact {contact.reference} belongs to employer "
                    f"{contact.employer_ref!r}, which wasn't imported"
                )
            row = await self._get_or_create(session, EmployerContactRow, contact.reference)
            row.name = contact.name
            row.role = contact.role
            row.authority = contact.authority.value
            row.employer_id = employer_id
            row.planned_calls = contact.planned_calls
            count += 1
        return count

    async def _upsert_agents(self, session: AsyncSession, agents: Iterable[Agent]) -> int:
        count = 0
        for agent in agents:
            row = await self._get_or_create(session, AgentRow, agent.reference)
            row.name = agent.name
            row.band = agent.band
            row.planned_calls = agent.planned_calls
            row.expected_score = agent.expected_score
            row.score_variance = agent.score_variance
            row.dominant_pattern = agent.dominant_pattern
            count += 1
        return count

    async def _upsert_rules(self, session: AsyncSession, rules: Iterable[Rule]) -> int:
        count = 0
        for rule in rules:
            row = await self._get_or_create(session, RuleRow, rule.reference)
            row.layer = rule.layer.value
            row.area = rule.area
            row.text = rule.text
            row.commonly_confused_with = rule.commonly_confused_with
            row.source = rule.source
            row.confidence = rule.confidence.value
            row.call_scenarios = rule.call_scenarios
            count += 1
        return count

    async def _upsert_touchpoints(
        self, session: AsyncSession, touchpoints: Iterable[Touchpoint]
    ) -> int:
        count = 0
        for touchpoint in touchpoints:
            row = await self._get_or_create(session, TouchpointRow, touchpoint.reference)
            row.owner = touchpoint.owner
            row.controls = touchpoint.controls
            count += 1
        return count
