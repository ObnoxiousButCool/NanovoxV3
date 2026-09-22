"""ORM table definitions.

Imported for its side effect: importing this module registers every table on
``Base.metadata``, which is what lets Alembic's autogenerate and
``Base.metadata.create_all`` see the schema.

Integer surrogate primary keys throughout; business references (``BRK-12``,
``EMP-1030``, ``CB-7700205``, ``CON-101``, ``AGT-01``, ``P-14``) are unique,
indexed, non-null columns — the natural key everything joins on in the
domain layer, kept separate from the surrogate key every foreign key here
actually uses (plan §8 Phase 1).
"""

from __future__ import annotations

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.persistence.models import Base

_REFERENCE_LENGTH = 32
_NAME_LENGTH = 256
_SHORT_LENGTH = 64


class BrokerRow(Base):
    __tablename__ = "brokers"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(nullable=False, unique=True, index=True)  # BRK-nn
    name: Mapped[str] = mapped_column(nullable=False)
    agency: Mapped[str] = mapped_column(nullable=False)
    region: Mapped[str] = mapped_column(nullable=False)
    groups_in_book: Mapped[int] = mapped_column(nullable=False)
    signal_profile: Mapped[str] = mapped_column(nullable=False)

    employers: Mapped[list[EmployerRow]] = relationship(back_populates="broker")


class EmployerRow(Base):
    __tablename__ = "employers"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(nullable=False, unique=True, index=True)  # EMP-nnnn
    name: Mapped[str] = mapped_column(nullable=False)
    industry: Mapped[str] = mapped_column(nullable=False)
    # Stored, never read by any calculation — see domain/entities/employer.py
    # and tests/unit/test_no_circular_scoring.py.
    design_churn_profile: Mapped[str] = mapped_column(nullable=False)
    eligible: Mapped[int] = mapped_column(nullable=False)
    enrolled: Mapped[int] = mapped_column(nullable=False)
    region: Mapped[str] = mapped_column(nullable=False)
    renewal_month: Mapped[str] = mapped_column(nullable=False)
    broker_id: Mapped[int] = mapped_column(ForeignKey("brokers.id"), nullable=False)
    dental_sponsorship: Mapped[str] = mapped_column(nullable=False)
    lines_held: Mapped[str] = mapped_column(nullable=False)
    planned_calls: Mapped[int] = mapped_column(nullable=False)
    planned_member_calls: Mapped[int] = mapped_column(nullable=False)
    planned_employer_calls: Mapped[int] = mapped_column(nullable=False)

    # --- derived (domain/reference_derivations.py) ---
    participation: Mapped[float | None] = mapped_column(nullable=True)
    fee_band: Mapped[int] = mapped_column(nullable=False)
    annual_fee: Mapped[int] = mapped_column(nullable=False)
    annual_premium: Mapped[float | None] = mapped_column(nullable=True)
    cobra_regime: Mapped[str] = mapped_column(nullable=False)
    calls_per_100: Mapped[float | None] = mapped_column(nullable=True)

    broker: Mapped[BrokerRow] = relationship(back_populates="employers")
    members: Mapped[list[MemberRow]] = relationship(back_populates="employer")
    contacts: Mapped[list[EmployerContactRow]] = relationship(back_populates="employer")


class MemberRow(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(nullable=False, unique=True, index=True)  # CB-nnnnnnn
    name: Mapped[str] = mapped_column(nullable=False)
    age: Mapped[int] = mapped_column(nullable=False)
    # No broker column, deliberately — inherited through employer_id. See
    # domain/entities/member.py.
    employer_id: Mapped[int] = mapped_column(ForeignKey("employers.id"), nullable=False)
    primary_line: Mapped[str] = mapped_column(nullable=False)
    planned_calls: Mapped[int] = mapped_column(nullable=False)
    repeat_caller: Mapped[bool] = mapped_column(nullable=False)

    employer: Mapped[EmployerRow] = relationship(back_populates="members")


class EmployerContactRow(Base):
    __tablename__ = "employer_contacts"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(nullable=False, unique=True, index=True)  # CON-nnn
    name: Mapped[str] = mapped_column(nullable=False)
    role: Mapped[str] = mapped_column(nullable=False)
    authority: Mapped[str] = mapped_column(nullable=False)  # Authority.value
    employer_id: Mapped[int] = mapped_column(ForeignKey("employers.id"), nullable=False)
    planned_calls: Mapped[int] = mapped_column(nullable=False)

    employer: Mapped[EmployerRow] = relationship(back_populates="contacts")


class AgentRow(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(nullable=False, unique=True, index=True)  # AGT-nn
    name: Mapped[str] = mapped_column(nullable=False)
    band: Mapped[str] = mapped_column(nullable=False)
    planned_calls: Mapped[int] = mapped_column(nullable=False)
    expected_score: Mapped[float | None] = mapped_column(nullable=True)
    score_variance: Mapped[float | None] = mapped_column(nullable=True)
    dominant_pattern: Mapped[str] = mapped_column(nullable=False)


class RuleRow(Base):
    __tablename__ = "rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(
        nullable=False, unique=True, index=True
    )  # P-14, A-09, C-12
    layer: Mapped[str] = mapped_column(nullable=False)  # RuleLayer.value
    area: Mapped[str] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(nullable=False)
    commonly_confused_with: Mapped[str] = mapped_column(nullable=False)
    source: Mapped[str] = mapped_column(nullable=False)
    confidence: Mapped[str] = mapped_column(nullable=False)  # RuleConfidence.value
    call_scenarios: Mapped[str | None] = mapped_column(nullable=True)


class TouchpointRow(Base):
    __tablename__ = "touchpoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(
        nullable=False, unique=True, index=True
    )  # enrolment_meeting, ...
    owner: Mapped[str] = mapped_column(nullable=False)
    controls: Mapped[str] = mapped_column(nullable=False)
