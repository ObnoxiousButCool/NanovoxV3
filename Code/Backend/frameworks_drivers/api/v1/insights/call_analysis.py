"""One call's pipeline output, grouped into the panels the drawer opens.

**Four panels, four layers** — the ones the Call Tag Schema's "Emitted by"
column names, with nothing beyond L4 anywhere in the workbook (plan §7 says
so, and `domain/layers.py` has four members).

Schema fields 17-18, `rootCauseOwner` and `preventable`, sit on the L4
panel. They are **computed in code and never sent to a model**
(`domain/derivations/root_cause.py`), which is a real distinction and is
stated on the field rather than by a panel of their own — they are written
in the same transaction as L4 and have no run, no prompt and no provenance
to separate them by. A panel holding two computed values beside four
layers read as a fifth layer, which they are not.

## Why the grouping lives on the server

`CallExtraction` already knows which layer writes which tag — that is the
schema sheet's own column, not a rendering choice — so the client is sent
the grouping rather than a flat bag it would have to regroup. Two copies
of "field 8 comes from L3" is the kind of duplication that survives right
up until one of them is edited.

## `ran` is not `has values`

Every panel says whether its layer ran, separately from what it found. L3
and L4 are not pipeline-critical (plan §7): either can fail on one call
and be recorded unavailable while the rest of the record stands. A panel
showing "no signals raised" for a layer that never ran would be reporting
a clean call, which is the withheld-is-not-zero mistake the figures make
impossible everywhere else. `notRunBecause` carries the words for it.

## D7, on the L3 and L4 panels

`knowledge_failure` (schema field 8, L3) and the `knowledge_error` signal
(L4) are different things, rendered in different panels, with no
arithmetic between them. Field 8 is organisational — the rule that was
stated wrongly — and **is never attributed to the agent who took the
call**, here or anywhere. The signal is the agent-conduct event. D7 is
open with Karim on exactly this distinction and nothing in code may
reconcile them, so each panel states its own field and neither mentions
the other's count.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import Field

from domain.value_objects.signal_type import SEVERITY_ORDER, owner_team_of, severity_of
from frameworks_drivers.api.camel import CamelModel
from frameworks_drivers.api.v1.insights.labels import CodedValue, coded, touchpoint_label

if TYPE_CHECKING:
    from domain.entities.call_extraction import CallExtraction
    from domain.value_objects.layer_run import LayerRun

#: Why a panel has nothing in it. Two sentences, because the situations
#: differ in what the reader should conclude: a missing L2 means there is
#: no analysis at all, whereas a missing L3 or L4 leaves the rest standing.
NOT_RUN = "The pipeline has not run on this call yet."
NOT_RUN_OPTIONAL = (
    "This layer has not run on this call. It is not required for a call to have "
    "an analysis, so the other panels still stand."
)


class LayerRunResponse(CamelModel):
    """Which model produced a layer's output, and when (plan §7)."""

    provider: str
    model: str
    prompt_version: str
    completed_at: datetime
    rubric_version: str | None = Field(
        default=None, description="L3 only. Null on layers that score nothing."
    )


class EvidencedItem(CamelModel):
    """Something a layer found, with the line it found it on.

    Every quote here survived evidence checking against the transcript: an
    item whose quote could not be located is rejected and never stored
    (plan §7, "Evidence validation, every LLM layer"). `turnSeq` indexes
    the `turns` on the same response, so the drawer can point at the line.
    """

    type: CodedValue
    quote: str
    turn_seq: int
    severity: CodedValue | None = Field(
        default=None,
        description="Signals only. Fixed per type by the Signal Taxonomy sheet.",
    )
    owner_team: str | None = Field(
        default=None,
        description=(
            "Signals only. The team the Signal Taxonomy sheet makes answerable for "
            "this type -- fixed per type like `severity`, never decided per call."
        ),
    )


class MarkerResponse(CamelModel):
    """One rubric observation behind a quality score."""

    dimension: str
    polarity: CodedValue
    description: str
    quote: str
    turn_seq: int


class L1PanelResponse(CamelModel):
    """Deterministic extraction. Code, no model — the same transcript gives
    the same answer every time, which is why it has no provenance."""

    ran: bool
    not_run_because: str | None = None
    caller_ref: str
    control_exceptions: list[CodedValue] = Field(
        default_factory=list,
        description=(
            "Schema field 7. Never carries missing_benefit_disclosure: metric 7 is "
            "deterministic and a greeting check cannot prove that one."
        ),
    )


class L2PanelResponse(CamelModel):
    """Classification. What the call was about, and how it ended."""

    ran: bool
    not_run_because: str | None = None
    run: LayerRunResponse | None = None
    outcome: CodedValue | None = None
    category: str | None = Field(
        default=None, description="The workbook's own wording, so it is not re-labelled."
    )
    product_lines: list[CodedValue] = Field(default_factory=list)
    complaint_present: bool | None = None
    complaint_attributed_to: CodedValue | None = None
    intent: list[EvidencedItem] = Field(default_factory=list)
    escalation_triggered: bool | None = None
    escalation_requested_by_caller: bool | None = None
    broker_named_aloud: bool | None = None
    broker_ref: str | None = None
    broker_sentiment: CodedValue | None = None
    broker_matches_employer_of_record: bool | None = Field(
        default=None,
        description=(
            "Whether the broker named aloud is the employer's broker of record. Null "
            "when no broker was named, or when the employer has none on file."
        ),
    )
    touchpoint: str | None = None
    summary: str | None = None
    primary_issue: str | None = None
    secondary_issues: list[str] = Field(default_factory=list)
    impact_scope: CodedValue | None = None
    impact_scope_count: int | None = Field(
        default=None,
        description=(
            "The N the caller stated. Null for the two buckets that are one person "
            "by definition. This is the caller's claim, never our count."
        ),
    )


class L3PanelResponse(CamelModel):
    """Quality and knowledge."""

    ran: bool
    not_run_because: str | None = None
    run: LayerRunResponse | None = None
    quality_score: int | None = None
    quality_status: CodedValue | None = None
    quality_tier: CodedValue | None = None
    markers: list[MarkerResponse] = Field(
        default_factory=list,
        description=(
            "Markers that survived evidence checking. A score with no marker trail "
            "is not auditable, so the trail travels with the score."
        ),
    )
    knowledge_failure_present: bool | None = None
    knowledge_failure_rule_id: str | None = None
    knowledge_failure_correct_statement: str | None = None


class L4PanelResponse(CamelModel):
    """Signals and gaps."""

    ran: bool
    not_run_because: str | None = None
    run: LayerRunResponse | None = None
    signals: list[EvidencedItem] = Field(
        default_factory=list,
        description=(
            "Distinct types, worst severity first. Five instances of one problem is "
            "one problem; three different problems is an account coming apart."
        ),
    )
    escalation_handled: bool | None = None
    escalation_trigger_type: CodedValue | None = None
    process_gap_present: bool | None = None
    process_gap_type: str | None = None
    process_gap_touchpoint: str | None = Field(
        default=None,
        description=(
            "Words, not the Touchpoints-sheet reference -- the same `touchpoint_label` "
            "the calls table and the risk screen's drivers panel use, so one reader "
            "never meets `denial_letter_eob` on one screen and the sheet's own words "
            "on the next."
        ),
    )
    process_gap_proposed_change: str | None = None
    process_gap_raised_by: CodedValue | None = None
    process_gap_status: CodedValue | None = None
    root_cause_owner: CodedValue | None = Field(
        default=None,
        description=(
            "Call Tag Schema field 17. Computed in code from complaint and signals, "
            "never asked of a model."
        ),
    )
    preventable: str | None = Field(
        default=None,
        description=(
            "Call Tag Schema field 18. Computed in code, like field 17. Yes, Partly or "
            "No — already the words a reader wants, so it carries no label."
        ),
    )


class CallAnalysisResponse(CamelModel):
    """Four panels for one call."""

    l1: L1PanelResponse
    l2: L2PanelResponse
    l3: L3PanelResponse
    l4: L4PanelResponse


def _run(run: LayerRun | None) -> LayerRunResponse | None:
    if run is None:
        return None
    return LayerRunResponse(
        provider=run.provider,
        model=run.model,
        prompt_version=run.prompt_version,
        completed_at=run.completed_at,
        rubric_version=run.rubric_version,
    )


def analysis_response(
    extraction: CallExtraction | None, *, caller_ref: str
) -> CallAnalysisResponse:
    """The four panels for one call.

    A call with no extraction row at all still gets four panels rather than
    a null: the reader asked what we know about this call, and "nothing has
    run" is the answer to that question. A null would render as a missing
    section, which reads as a loading failure.
    """
    l2_ran = extraction is not None and extraction.l2_run is not None
    l3_ran = extraction is not None and extraction.l3_run is not None
    l4_ran = extraction is not None and extraction.l4_run is not None

    return CallAnalysisResponse(
        l1=_l1(extraction, caller_ref=caller_ref, ran=l2_ran),
        l2=_l2(extraction) if l2_ran else L2PanelResponse(ran=False, not_run_because=NOT_RUN),
        l3=(
            _l3(extraction)
            if l3_ran
            else L3PanelResponse(ran=False, not_run_because=NOT_RUN_OPTIONAL)
        ),
        l4=(
            _l4(extraction)
            if l4_ran
            else L4PanelResponse(ran=False, not_run_because=NOT_RUN_OPTIONAL)
        ),
    )


def _l1(extraction: CallExtraction | None, *, caller_ref: str, ran: bool) -> L1PanelResponse:
    """L1's panel.

    `ran` is L2's, deliberately. L1 is pure and recomputed rather than
    stored, and it is written in the same transaction as L2, so it has run
    exactly when L2 has. Inferring it from `control_exceptions` instead
    would report a call that broke no controls as one nobody checked.

    `callerRef` comes off the call rather than out of the extraction: it is
    on the call row from ingestion, and L1's contribution is that the join
    it enables is deterministic, not that it invented the reference.
    """
    exceptions = () if extraction is None else (extraction.control_exceptions or ())
    return L1PanelResponse(
        ran=ran,
        not_run_because=None if ran else NOT_RUN,
        caller_ref=caller_ref,
        control_exceptions=[coded(item) for item in sorted(exceptions, key=lambda x: x.value)],
    )


def _l2(extraction: CallExtraction | None) -> L2PanelResponse:
    assert extraction is not None  # noqa: S101 - guarded by l2_ran
    complaint = extraction.complaint
    broker = extraction.broker_named_aloud
    scope = extraction.impact_scope
    return L2PanelResponse(
        ran=True,
        run=_run(extraction.l2_run),
        outcome=coded(extraction.outcome) if extraction.outcome is not None else None,
        category=extraction.category.value if extraction.category is not None else None,
        product_lines=[coded(line) for line in extraction.product_lines],
        complaint_present=None if complaint is None else complaint.present,
        complaint_attributed_to=(
            coded(complaint.attributed_to)
            if complaint is not None and complaint.attributed_to is not None
            else None
        ),
        intent=[
            EvidencedItem(type=coded(item.type), quote=item.quote, turn_seq=item.turn_seq)
            for item in extraction.intent
        ],
        escalation_triggered=extraction.escalation_triggered,
        escalation_requested_by_caller=extraction.escalation_requested_by_caller,
        broker_named_aloud=None if broker is None else broker.present,
        broker_ref=None if broker is None else broker.broker_ref,
        broker_sentiment=(
            coded(broker.sentiment) if broker is not None and broker.sentiment is not None else None
        ),
        broker_matches_employer_of_record=(
            None if broker is None else broker.matches_employer_of_record
        ),
        touchpoint=extraction.touchpoint,
        summary=extraction.summary,
        primary_issue=extraction.primary_issue,
        secondary_issues=list(extraction.secondary_issues),
        impact_scope=coded(scope.bucket) if scope is not None else None,
        impact_scope_count=None if scope is None else scope.count,
    )


def _l3(extraction: CallExtraction | None) -> L3PanelResponse:
    assert extraction is not None  # noqa: S101 - guarded by l3_ran
    failure = extraction.knowledge_failure
    return L3PanelResponse(
        ran=True,
        run=_run(extraction.l3_run),
        quality_score=(
            extraction.quality_score.value if extraction.quality_score is not None else None
        ),
        quality_status=(
            coded(extraction.quality_status) if extraction.quality_status is not None else None
        ),
        quality_tier=coded(extraction.quality_tier)
        if extraction.quality_tier is not None
        else None,
        markers=[
            MarkerResponse(
                dimension=marker.dimension,
                polarity=coded(marker.polarity),
                description=marker.description,
                quote=marker.quote,
                turn_seq=marker.turn_seq,
            )
            for marker in extraction.markers
        ],
        knowledge_failure_present=None if failure is None else failure.present,
        knowledge_failure_rule_id=None if failure is None else failure.rule_id,
        knowledge_failure_correct_statement=(
            None if failure is None else failure.correct_statement
        ),
    )


def _l4(extraction: CallExtraction | None) -> L4PanelResponse:
    assert extraction is not None  # noqa: S101 - guarded by l4_ran
    gap = extraction.process_gap
    # Worst first, and stable within a severity by the order the taxonomy
    # lists the types — a drawer that reshuffled two equally severe signals
    # between reloads would look like the analysis had changed.
    signals = sorted(
        extraction.signals,
        key=lambda signal: (
            SEVERITY_ORDER.index(severity_of(signal.type)),
            signal.type.value,
        ),
    )
    return L4PanelResponse(
        ran=True,
        run=_run(extraction.l4_run),
        signals=[
            EvidencedItem(
                type=coded(signal.type),
                quote=signal.quote,
                turn_seq=signal.turn_seq,
                severity=coded(severity_of(signal.type)),
                owner_team=owner_team_of(signal.type),
            )
            for signal in signals
        ],
        escalation_handled=extraction.escalation_handled,
        escalation_trigger_type=(
            coded(extraction.escalation_trigger_type)
            if extraction.escalation_trigger_type is not None
            else None
        ),
        process_gap_present=None if gap is None else gap.present,
        process_gap_type=None if gap is None else gap.gap_type,
        process_gap_touchpoint=(
            None if gap is None or gap.touchpoint is None else touchpoint_label(gap.touchpoint)
        ),
        process_gap_proposed_change=None if gap is None else gap.proposed_change,
        process_gap_raised_by=(
            coded(gap.raised_by) if gap is not None and gap.raised_by is not None else None
        ),
        process_gap_status=(
            coded(gap.status) if gap is not None and gap.status is not None else None
        ),
        root_cause_owner=(
            coded(extraction.root_cause_owner) if extraction.root_cause_owner is not None else None
        ),
        preventable=(extraction.preventable.value if extraction.preventable is not None else None),
    )
