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

from datetime import datetime

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from infrastructure.persistence.models import Base


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


class CallRow(Base):
    """The fact table (Data Model sheet) — one row per ingested call,
    resolved or not. Never absent because resolution failed; see plan §8
    Phase 2's rules and `domain/entities/ingested_call.py`.
    """

    __tablename__ = "calls"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(nullable=False, unique=True, index=True)  # C-0001
    source: Mapped[str] = mapped_column(nullable=False)  # CallSource.value
    occurred_at: Mapped[datetime | None] = mapped_column(nullable=True)
    aht_seconds: Mapped[int | None] = mapped_column(nullable=True)
    caller_type: Mapped[str] = mapped_column(nullable=False)  # CallerType.value
    caller_ref: Mapped[str] = mapped_column(nullable=False)
    agent_ref: Mapped[str] = mapped_column(nullable=False)

    resolution_status: Mapped[str] = mapped_column(nullable=False)  # CallResolutionStatus.value
    resolution_reason: Mapped[str | None] = mapped_column(nullable=True)

    # Null exactly when that half of the join didn't resolve — never a
    # guess standing in for a missing join.
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"), nullable=True)
    employer_contact_id: Mapped[int | None] = mapped_column(
        ForeignKey("employer_contacts.id"), nullable=True
    )
    employer_id: Mapped[int | None] = mapped_column(ForeignKey("employers.id"), nullable=True)

    # selectin: async-safe eager loading. The default lazy="select" would
    # try to lazy-load this collection outside of an awaited context the
    # moment the repository touches `row.turns`, and raise MissingGreenlet.
    turns: Mapped[list[CallTurnRow]] = relationship(
        back_populates="call",
        cascade="all, delete-orphan",
        order_by="CallTurnRow.sequence",
        lazy="selectin",
    )


class CallTurnRow(Base):
    """Separate from `CallRow`, like signals and rubric markers (Data Model
    sheet): one call raises many turns, and normalising them lets a turn be
    queried and quoted on its own — the same reason marker-level evidence is
    kept auditable rather than folded into one blob.
    """

    __tablename__ = "call_turns"

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id"), nullable=False)
    sequence: Mapped[int] = mapped_column(nullable=False)
    role: Mapped[str] = mapped_column(nullable=False)  # SpeakerRole.value
    text: Mapped[str] = mapped_column(nullable=False)

    call: Mapped[CallRow] = relationship(back_populates="turns")


class IngestJobRow(Base):
    """Generic across sources (plan §6.4) — not a PDF-specific job table.

    One row per ingestion run. `result_call_reference` is populated only
    for a job that ingests exactly one call (a future single-call source —
    paste, audio); a bulk PDF batch import leaves it null, since "result"
    would mean nothing for a hundred calls at once.
    """

    __tablename__ = "ingest_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(nullable=False)  # e.g. "corpus_pdf"
    status: Mapped[str] = mapped_column(nullable=False)  # RUNNING / COMPLETED / FAILED
    message: Mapped[str | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime] = mapped_column(nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)
    result_call_reference: Mapped[str | None] = mapped_column(nullable=True)


class StageCacheEntryRow(Base):
    """One extraction layer's cached raw completion (plan §7's stage cache).

    ``output_text`` is the layer's raw completion text, not a parsed
    value — see ``application/ports/stage_cache.py`` for why. The unique
    constraint is the whole cache key; a repeat write for the same key
    replaces rather than duplicates (`SqlStageCache` upserts by it).
    """

    __tablename__ = "stage_cache_entries"
    __table_args__ = (
        UniqueConstraint(
            "transcript_hash", "layer", "prompt_version", "model", name="uq_stage_cache_key"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    transcript_hash: Mapped[str] = mapped_column(nullable=False, index=True)
    layer: Mapped[str] = mapped_column(nullable=False)  # Layer.value
    prompt_version: Mapped[str] = mapped_column(nullable=False)
    model: Mapped[str] = mapped_column(nullable=False)
    output_text: Mapped[str] = mapped_column(nullable=False)
    cached_at: Mapped[datetime] = mapped_column(nullable=False)
