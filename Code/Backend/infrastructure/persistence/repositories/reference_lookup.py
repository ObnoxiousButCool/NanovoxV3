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
from domain.entities.broker import Broker
from domain.entities.employer import Employer
from domain.entities.employer_contact import EmployerContact
from domain.entities.member import Member
from domain.entities.rule import Rule
from domain.entities.touchpoint import Touchpoint
from domain.value_objects.authority import Authority
from domain.value_objects.rule_confidence import RuleConfidence
from domain.value_objects.rule_layer import RuleLayer
from infrastructure.persistence.tables import (
    AgentRow,
    BrokerRow,
    EmployerContactRow,
    EmployerRow,
    MemberRow,
    RuleRow,
    TouchpointRow,
)


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

    async def find_employer(self, reference: str) -> Employer | None:
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    select(EmployerRow, BrokerRow.reference)
                    .join(BrokerRow, EmployerRow.broker_id == BrokerRow.id)
                    .where(EmployerRow.reference == reference)
                )
            ).first()
            if row is None:
                return None
            employer_row, broker_reference = row
            return Employer(
                reference=employer_row.reference,
                name=employer_row.name,
                industry=employer_row.industry,
                design_churn_profile=employer_row.design_churn_profile,
                eligible=employer_row.eligible,
                enrolled=employer_row.enrolled,
                region=employer_row.region,
                renewal_month=employer_row.renewal_month,
                broker_ref=broker_reference,
                dental_sponsorship=employer_row.dental_sponsorship,
                lines_held=employer_row.lines_held,
                planned_calls=employer_row.planned_calls,
                planned_member_calls=employer_row.planned_member_calls,
                planned_employer_calls=employer_row.planned_employer_calls,
                participation=employer_row.participation,
                fee_band=employer_row.fee_band,
                annual_fee=employer_row.annual_fee,
                annual_premium=employer_row.annual_premium,
                cobra_regime=employer_row.cobra_regime,
                calls_per_100=employer_row.calls_per_100,
            )

    async def list_brokers(self) -> tuple[Broker, ...]:
        async with self._session_factory() as session:
            rows = (await session.execute(select(BrokerRow))).scalars().all()
            return tuple(
                Broker(
                    reference=row.reference,
                    name=row.name,
                    agency=row.agency,
                    region=row.region,
                    groups_in_book=row.groups_in_book,
                    signal_profile=row.signal_profile,
                )
                for row in rows
            )

    async def list_rules(self) -> tuple[Rule, ...]:
        async with self._session_factory() as session:
            rows = (await session.execute(select(RuleRow))).scalars().all()
            return tuple(
                Rule(
                    reference=row.reference,
                    layer=RuleLayer(row.layer),
                    area=row.area,
                    text=row.text,
                    commonly_confused_with=row.commonly_confused_with,
                    source=row.source,
                    confidence=RuleConfidence(row.confidence),
                    call_scenarios=row.call_scenarios,
                )
                for row in rows
            )

    async def list_touchpoints(self) -> tuple[Touchpoint, ...]:
        async with self._session_factory() as session:
            rows = (
                (await session.execute(select(TouchpointRow).order_by(TouchpointRow.reference)))
                .scalars()
                .all()
            )
            return tuple(
                Touchpoint(reference=row.reference, owner=row.owner, controls=row.controls)
                for row in rows
            )
