"""`SqlReferenceRepository` against a real (temporary) SQLite database:
idempotent upsert, foreign-key resolution, and a clear error when a row
names a business key nothing else in the same import provides.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from application.ports.reference_source import ReferenceDataset
from domain.entities.agent import Agent
from domain.entities.broker import Broker
from domain.entities.employer import Employer
from domain.entities.employer_contact import EmployerContact
from domain.entities.member import Member
from domain.entities.rule import Rule
from domain.entities.touchpoint import Touchpoint
from domain.errors import ReferenceIntegrityError
from domain.value_objects.authority import Authority
from domain.value_objects.rule_confidence import RuleConfidence
from domain.value_objects.rule_layer import RuleLayer
from infrastructure.persistence.repositories.reference_repository import SqlReferenceRepository
from infrastructure.persistence.tables import BrokerRow, EmployerRow

_BROKER = Broker(
    reference="BRK-01",
    name="Anthony Salerno",
    agency="Salerno Benefits Group",
    region="Orange County",
    groups_in_book=3,
    signal_profile="Adverse — responsiveness",
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
    broker_ref="BRK-01",
    dental_sponsorship="ER",
    lines_held="Dental + Vision + Chiro",
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

_MEMBER = Member(
    reference="CB-7700001",
    name="Omar Liu",
    age=52,
    employer_ref="EMP-1001",
    primary_line="Chiro",
    planned_calls=2,
    repeat_caller=False,
)

_CONTACT = EmployerContact(
    reference="CON-101",
    name="Quentin Thibault",
    role="Payroll Administrator",
    authority=Authority.CANNOT_BIND,
    employer_ref="EMP-1001",
    planned_calls=6,
)

_AGENT = Agent(
    reference="AGT-01",
    name="Sarah Whitlock",
    band="Senior",
    planned_calls=32,
    expected_score=88.0,
    score_variance=7.0,
    dominant_pattern="Strong — consistent",
)

_RULE = Rule(
    reference="P-01",
    layer=RuleLayer.PROGRAM,
    area="Group eligibility",
    text="Group size 2-500 eligible employees.",
    commonly_confused_with="Being small-group only.",
    source="Program Guidelines",
    confidence=RuleConfidence.VERIFIED,
)

_TOUCHPOINT = Touchpoint(
    reference="enrolment_meeting", owner="Broker Relations", controls="The broker, not Choice"
)


def _dataset(
    *,
    brokers: tuple[Broker, ...] = (_BROKER,),
    employers: tuple[Employer, ...] = (_EMPLOYER,),
    members: tuple[Member, ...] = (_MEMBER,),
    employer_contacts: tuple[EmployerContact, ...] = (_CONTACT,),
    agents: tuple[Agent, ...] = (_AGENT,),
    rules: tuple[Rule, ...] = (_RULE,),
    touchpoints: tuple[Touchpoint, ...] = (_TOUCHPOINT,),
) -> ReferenceDataset:
    return ReferenceDataset(
        brokers=brokers,
        employers=employers,
        members=members,
        employer_contacts=employer_contacts,
        agents=agents,
        rules=rules,
        touchpoints=touchpoints,
    )


async def test_upserts_every_kind_and_returns_counts(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    repository = SqlReferenceRepository(session_factory)

    counts = await repository.upsert(_dataset())

    assert counts.brokers == 1
    assert counts.employers == 1
    assert counts.members == 1
    assert counts.employer_contacts == 1
    assert counts.agents == 1
    assert counts.rules == 1
    assert counts.touchpoints == 1


async def test_resolves_the_employer_broker_id_foreign_key(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    repository = SqlReferenceRepository(session_factory)
    await repository.upsert(_dataset())

    async with session_factory() as session:
        broker = (
            await session.execute(select(BrokerRow).where(BrokerRow.reference == "BRK-01"))
        ).scalar_one()
        employer = (
            await session.execute(select(EmployerRow).where(EmployerRow.reference == "EMP-1001"))
        ).scalar_one()
        assert employer.broker_id == broker.id


async def test_re_importing_updates_in_place_without_duplicating(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    repository = SqlReferenceRepository(session_factory)
    await repository.upsert(_dataset())

    changed_broker = Broker(
        reference="BRK-01",
        name="Anthony Salerno",
        agency="Salerno Benefits Group",
        region="Orange County",
        groups_in_book=5,  # changed
        signal_profile="Watch",  # changed
    )
    await repository.upsert(_dataset(brokers=(changed_broker,)))

    async with session_factory() as session:
        total = (await session.execute(select(func.count()).select_from(BrokerRow))).scalar_one()
        row = (
            await session.execute(select(BrokerRow).where(BrokerRow.reference == "BRK-01"))
        ).scalar_one()
        assert total == 1
        assert row.groups_in_book == 5
        assert row.signal_profile == "Watch"


async def test_an_employer_naming_an_unimported_broker_raises(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    repository = SqlReferenceRepository(session_factory)
    orphaned = replace(_EMPLOYER, broker_ref="BRK-99")

    with pytest.raises(ReferenceIntegrityError, match="BRK-99"):
        await repository.upsert(_dataset(brokers=(), employers=(orphaned,)))


async def test_a_member_naming_an_unimported_employer_raises(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    repository = SqlReferenceRepository(session_factory)
    orphaned = replace(_MEMBER, employer_ref="EMP-9999")

    with pytest.raises(ReferenceIntegrityError, match="EMP-9999"):
        await repository.upsert(_dataset(employers=(), members=(orphaned,), employer_contacts=()))
