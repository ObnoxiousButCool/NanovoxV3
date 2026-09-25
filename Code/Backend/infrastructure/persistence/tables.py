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

from datetime import date, datetime

from sqlalchemy import JSON, ForeignKey, UniqueConstraint, text
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
    # The header's own agent name, alongside agent_ref — needed to
    # reconstruct a Transcript when a call is read back for extraction
    # (plan §8 Phase 4). Empty when there is no transcript to reconstruct
    # (SPEAKER_UNRESOLVED).
    agent_name: Mapped[str] = mapped_column(nullable=False, default="", server_default=text("''"))

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
    # Read-only from this side (no back_populates): these three exist so a
    # call can be read back with its business references resolved, without
    # a second round of by-reference lookups. selectin for the same reason
    # as `turns` above.
    member: Mapped[MemberRow | None] = relationship(foreign_keys=[member_id], lazy="selectin")
    employer_contact: Mapped[EmployerContactRow | None] = relationship(
        foreign_keys=[employer_contact_id], lazy="selectin"
    )
    employer: Mapped[EmployerRow | None] = relationship(foreign_keys=[employer_id], lazy="selectin")


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


class CallExtractionRow(Base):
    """The pipeline's own output for one call — the Call Tag Schema's
    sixteen fields, filled in as L1 → L2 → (L3 ∥ L4) run (plan §7, §8
    Phase 4). One row per call (Data Model sheet: the call is the fact
    table); separate from `CallRow`, which is Phase 2's ingestion record
    and never touched again once a call is resolved.

    Only L2's columns are non-null yet — L1 is pure and recomputed on
    demand rather than stored, and L3/L4's columns arrive with those
    commits. A call with no row here simply hasn't been analysed.
    """

    __tablename__ = "call_extractions"

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id"), nullable=False, unique=True)

    # --- L1 — deterministic, saved with L2 --------------------------------
    control_exceptions: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True
    )  # ControlExceptionType.value, sorted

    # --- L2 — classification -------------------------------------------
    outcome: Mapped[str | None] = mapped_column(nullable=True)  # Outcome.value
    category: Mapped[str | None] = mapped_column(nullable=True)  # Category.value
    product_lines: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    complaint_present: Mapped[bool | None] = mapped_column(nullable=True)
    complaint_attributed_to: Mapped[str | None] = mapped_column(nullable=True)
    # Each item: {"type", "quote", "turn_seq"}.
    intent: Mapped[list[dict[str, str | int]] | None] = mapped_column(JSON, nullable=True)
    escalation_triggered: Mapped[bool | None] = mapped_column(nullable=True)
    escalation_requested_by_caller: Mapped[bool | None] = mapped_column(nullable=True)
    broker_named_aloud_present: Mapped[bool | None] = mapped_column(nullable=True)
    broker_named_aloud_broker_ref: Mapped[str | None] = mapped_column(nullable=True)
    broker_named_aloud_sentiment: Mapped[str | None] = mapped_column(nullable=True)
    broker_named_aloud_matches_employer_of_record: Mapped[bool | None] = mapped_column(
        nullable=True
    )
    touchpoint: Mapped[str | None] = mapped_column(nullable=True)
    summary: Mapped[str | None] = mapped_column(nullable=True)

    l2_provider: Mapped[str | None] = mapped_column(nullable=True)
    l2_model: Mapped[str | None] = mapped_column(nullable=True)
    l2_prompt_version: Mapped[str | None] = mapped_column(nullable=True)
    l2_completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # --- L3 — quality & knowledge ---------------------------------------
    quality_score: Mapped[int | None] = mapped_column(nullable=True)
    quality_status: Mapped[str | None] = mapped_column(nullable=True)  # ScoreStatus.value
    quality_tier: Mapped[str | None] = mapped_column(nullable=True)  # Tier.value
    rubric_version: Mapped[str | None] = mapped_column(nullable=True)
    knowledge_failure_present: Mapped[bool | None] = mapped_column(nullable=True)
    knowledge_failure_rule_id: Mapped[str | None] = mapped_column(nullable=True)
    knowledge_failure_correct_statement: Mapped[str | None] = mapped_column(nullable=True)

    l3_provider: Mapped[str | None] = mapped_column(nullable=True)
    l3_model: Mapped[str | None] = mapped_column(nullable=True)
    l3_prompt_version: Mapped[str | None] = mapped_column(nullable=True)
    l3_completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # --- L4 — signals & gaps ---------------------------------------------
    escalation_handled: Mapped[bool | None] = mapped_column(nullable=True)
    escalation_trigger_type: Mapped[str | None] = mapped_column(nullable=True)
    process_gap_present: Mapped[bool | None] = mapped_column(nullable=True)
    process_gap_gap_type: Mapped[str | None] = mapped_column(nullable=True)
    process_gap_touchpoint: Mapped[str | None] = mapped_column(nullable=True)
    process_gap_proposed_change: Mapped[str | None] = mapped_column(nullable=True)
    process_gap_raised_by: Mapped[str | None] = mapped_column(nullable=True)
    process_gap_status: Mapped[str | None] = mapped_column(nullable=True)

    l4_provider: Mapped[str | None] = mapped_column(nullable=True)
    l4_model: Mapped[str | None] = mapped_column(nullable=True)
    l4_prompt_version: Mapped[str | None] = mapped_column(nullable=True)
    l4_completed_at: Mapped[datetime | None] = mapped_column(nullable=True)


class ScoreMarkerRow(Base):
    """One rubric observation (Data Model sheet: "Rubric marker" — kept at
    marker level, separate from the call, "so a refused marker is
    visible. A score with no marker trail is not auditable.").

    Every marker the model raised is stored, not just the ones that
    survived evidence checking — `verification_status` is "accepted" or
    an `EvidenceRejection` value (`domain/extraction/evidence.py`).
    """

    __tablename__ = "score_markers"

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id"), nullable=False, index=True)
    dimension: Mapped[str] = mapped_column(nullable=False)
    polarity: Mapped[str] = mapped_column(nullable=False)  # Polarity.value
    description: Mapped[str] = mapped_column(nullable=False)
    quote: Mapped[str] = mapped_column(nullable=False)
    turn_seq: Mapped[int] = mapped_column(nullable=False)
    verification_status: Mapped[str] = mapped_column(nullable=False)


class SignalRow(Base):
    """One raised signal (Data Model sheet: "Signal" — separate from the
    call so one call can raise several, and so signal density counts
    distinct types rather than occurrences).

    Only signals that survived evidence checking are stored — severity is
    never persisted here; it's derived from `type` on read
    (`domain.value_objects.signal_type.severity_of`), so it can't drift
    from the taxonomy.
    """

    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(nullable=False)  # SignalType.value
    quote: Mapped[str] = mapped_column(nullable=False)
    turn_seq: Mapped[int] = mapped_column(nullable=False)


class RunRow(Base):
    """One run of the extraction pipeline over a set of calls (plan §8
    Phase 3, "run orchestration... resumability"). Like `IngestJobRow`,
    one row per run makes the run itself a queryable record; unlike an
    ingest job, a run's outcome is a status per call, not a single
    message, so its per-item detail lives in `RunItemRow`.
    """

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(nullable=False)  # RunStatus.value
    provider: Mapped[str] = mapped_column(nullable=False)
    model: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(nullable=True)

    items: Mapped[list[RunItemRow]] = relationship(back_populates="run")


class RunItemRow(Base):
    """One call's place within a run. `error` is the failure's message,
    kept for the operator running the CLI or watching the endpoint — not
    a substitute for the pipeline's own error logging.
    """

    __tablename__ = "run_items"
    __table_args__ = (UniqueConstraint("run_id", "call_reference", name="uq_run_item"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False, index=True)
    call_reference: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(nullable=False)  # RunItemStatus.value
    error: Mapped[str | None] = mapped_column(nullable=True)

    # What this call cost (plan §8 Phase 5: "token cost of the last run").
    # `usage_reported` is not redundant with zero tokens: a stage answered
    # from the cache is genuinely free, while a provider that declined to
    # report spent tokens nobody counted — and any total containing one of
    # those is a floor rather than a cost.
    input_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    usage_reported: Mapped[bool] = mapped_column(nullable=False, default=True)
    duration_ms: Mapped[float | None] = mapped_column(nullable=True)

    run: Mapped[RunRow] = relationship(back_populates="items")


class GroundTruthRow(Base):
    """The Transcript Tracker's answer for one call (plan §8 Phase 2).

    Answer-key material, and the only table that is. Phase 5 scores
    `call_extractions` against this row by row, which is why the column
    names deliberately mirror `CallExtractionRow`'s rather than the
    tracker's spreadsheet headings: two records that name the same field
    differently are a comparison waiting to be written wrong.

    One row per call, hanging off `calls.id` like `call_extractions` does. A
    tracker row naming a call that has not been ingested is reported by the
    importer as unmatched, never written — there is nowhere to hang it, and
    inventing a call to hold an answer would put a fabricated row in the
    fact table.

    Lists are JSON columns, following `CallExtractionRow.product_lines` and
    `.intent`: the answer key is read whole and compared whole, never
    queried a member at a time.
    """

    __tablename__ = "ground_truth"

    id: Mapped[int] = mapped_column(primary_key=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id"), nullable=False, unique=True)

    # --- the five the corpus PDF's header also carries -------------------
    category: Mapped[str | None] = mapped_column(nullable=True)  # Category.value
    archetype: Mapped[str] = mapped_column(nullable=False, default="")
    rule_refs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    outcome: Mapped[str | None] = mapped_column(nullable=True)  # Outcome.value
    score: Mapped[int | None] = mapped_column(nullable=True)

    # --- the nineteen only the tracker carries ---------------------------
    product_line: Mapped[str] = mapped_column(nullable=False, default="")
    touchpoint: Mapped[str] = mapped_column(nullable=False, default="")
    aht_seconds: Mapped[int | None] = mapped_column(nullable=True)

    complaint_present: Mapped[bool | None] = mapped_column(nullable=True)
    complaint_attributed_to: Mapped[str | None] = mapped_column(nullable=True)

    # Each item: {"code", "severity", "owner_team"}.
    signals: Mapped[list[dict[str, str]]] = mapped_column(JSON, nullable=False, default=list)
    control_exceptions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    escalation_triggered: Mapped[bool | None] = mapped_column(nullable=True)
    escalation_type: Mapped[str | None] = mapped_column(nullable=True)
    escalation_requested_by_caller: Mapped[bool | None] = mapped_column(nullable=True)
    escalation_handled: Mapped[bool | None] = mapped_column(nullable=True)

    knowledge_failure_present: Mapped[bool | None] = mapped_column(nullable=True)
    knowledge_failure_rule_ref: Mapped[str | None] = mapped_column(nullable=True)
    knowledge_failure_statement: Mapped[str | None] = mapped_column(nullable=True)

    intent_type: Mapped[str | None] = mapped_column(nullable=True)
    intent_evidence: Mapped[str | None] = mapped_column(nullable=True)

    process_gap_present: Mapped[bool | None] = mapped_column(nullable=True)
    process_gap_description: Mapped[str | None] = mapped_column(nullable=True)

    broker_named_present: Mapped[bool | None] = mapped_column(nullable=True)
    broker_named_broker_ref: Mapped[str | None] = mapped_column(nullable=True)
    broker_named_sentiment: Mapped[str | None] = mapped_column(nullable=True)

    repeat_of_reference: Mapped[str | None] = mapped_column(nullable=True)
    repeat_of_note: Mapped[str | None] = mapped_column(nullable=True)

    imported_at: Mapped[datetime] = mapped_column(nullable=False)


class ActionRow(Base):
    """One action somebody works (Revised plan Phase 4, D6) — not a finding.

    `domain.aggregation.actions` derives findings on every read and stores
    nothing; this is the record with a status, an owner and a history. The
    status codes are `config/action_lifecycle.yaml`'s, so they are stored as
    plain strings rather than an enum the database would have to migrate.
    """

    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False)
    source_kind: Mapped[str] = mapped_column(nullable=False)  # ActionSourceKind.value
    source_detail: Mapped[str | None] = mapped_column(nullable=True)
    issue_key: Mapped[str | None] = mapped_column(nullable=True)
    evidence: Mapped[str] = mapped_column(nullable=False)
    recommendation: Mapped[str | None] = mapped_column(nullable=True)
    owner_team: Mapped[str] = mapped_column(nullable=False)
    owner: Mapped[str | None] = mapped_column(nullable=True)
    priority: Mapped[str] = mapped_column(nullable=False)  # Priority.value
    status: Mapped[str] = mapped_column(nullable=False, index=True)
    employer_ref: Mapped[str | None] = mapped_column(nullable=True, index=True)
    broker_ref: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False)
    assigned_on: Mapped[date | None] = mapped_column(nullable=True)
    due: Mapped[date | None] = mapped_column(nullable=True)
    action_taken: Mapped[str | None] = mapped_column(nullable=True)
    outcome: Mapped[str | None] = mapped_column(nullable=True)
    measurement_start: Mapped[date | None] = mapped_column(nullable=True)
    measurement_end: Mapped[date | None] = mapped_column(nullable=True)
    #: Set only on seeded actions, so reseeding does not duplicate one.
    seed_key: Mapped[str | None] = mapped_column(nullable=True, unique=True)


class ActionCallRow(Base):
    """The calls behind an action. Many to many: a call can sit behind
    several actions, and an action behind several calls."""

    __tablename__ = "action_calls"
    __table_args__ = (UniqueConstraint("action_id", "call_id", name="uq_action_call"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    action_id: Mapped[int] = mapped_column(ForeignKey("actions.id"), nullable=False, index=True)
    call_id: Mapped[int] = mapped_column(ForeignKey("calls.id"), nullable=False)
    position: Mapped[int] = mapped_column(nullable=False)


class ActionStepRow(Base):
    """One checklist step, in order."""

    __tablename__ = "action_steps"
    __table_args__ = (UniqueConstraint("action_id", "position", name="uq_action_step"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    action_id: Mapped[int] = mapped_column(ForeignKey("actions.id"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(nullable=False)
    done: Mapped[bool] = mapped_column(nullable=False, default=False)


class ActionLogRow(Base):
    """The activity timeline. Append-only: an entry is never edited."""

    __tablename__ = "action_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    action_id: Mapped[int] = mapped_column(ForeignKey("actions.id"), nullable=False, index=True)
    at: Mapped[datetime] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(nullable=False)
