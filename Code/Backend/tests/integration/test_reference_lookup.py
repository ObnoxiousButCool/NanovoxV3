"""`SqlReferenceLookup` against a real (temporary) SQLite database, seeded
through `SqlReferenceRepository` — the reverse direction of Phase 1's own
repository test.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from application.ports.reference_source import ReferenceDataset
from domain.entities.agent import Agent
from domain.entities.broker import Broker
from domain.entities.employer import Employer
from domain.entities.employer_contact import EmployerContact
from domain.entities.member import Member
from domain.value_objects.authority import Authority
from infrastructure.persistence.repositories.reference_lookup import SqlReferenceLookup
from infrastructure.persistence.repositories.reference_repository import SqlReferenceRepository

_BROKER = Broker(
    reference="BRK-01",
    name="Anthony Salerno",
    agency="Salerno Benefits Group",
    region="Orange County",
    groups_in_book=3,
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
    broker_ref="BRK-01",
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
    dominant_pattern="Strong",
)


async def _seed(session_factory: async_sessionmaker[AsyncSession]) -> None:
    await SqlReferenceRepository(session_factory).upsert(
        ReferenceDataset(
            brokers=(_BROKER,),
            employers=(_EMPLOYER,),
            members=(_MEMBER,),
            employer_contacts=(_CONTACT,),
        )
    )


async def test_finds_a_known_agent(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await SqlReferenceRepository(session_factory).upsert(ReferenceDataset(agents=(_AGENT,)))

    agent = await SqlReferenceLookup(session_factory).find_agent("AGT-01")

    assert agent is not None
    assert agent.name == "Sarah Whitlock"


async def test_unknown_agent_resolves_to_none(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    agent = await SqlReferenceLookup(session_factory).find_agent("AGT-99")

    assert agent is None


async def test_finds_a_known_member_with_its_employer_ref(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed(session_factory)

    member = await SqlReferenceLookup(session_factory).find_member("CB-7700205")

    assert member is not None
    assert member.name == "Leon Castellano"
    assert member.employer_ref == "EMP-1001"


async def test_unknown_member_resolves_to_none(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed(session_factory)

    member = await SqlReferenceLookup(session_factory).find_member("CB-9999999")

    assert member is None


async def test_finds_a_known_employer_contact_with_its_employer_ref(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _seed(session_factory)

    contact = await SqlReferenceLookup(session_factory).find_employer_contact("CON-101")

    assert contact is not None
    assert contact.authority is Authority.CANNOT_BIND
    assert contact.employer_ref == "EMP-1001"
