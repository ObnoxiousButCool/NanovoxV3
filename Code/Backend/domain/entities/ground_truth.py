"""What the workbook's Transcript Tracker says a call actually contained.

The answer key proper (plan §8 Phase 2, "`AnswerKeyImporter`: Transcript
Tracker → `ground_truth`"). Phase 5 scores the extraction pipeline against
this, field by field, so the shape here deliberately mirrors
`CallExtractionRow`'s column names — `complaint_present`,
`escalation_triggered`, `broker_named_*` and so on — rather than the
tracker's own spreadsheet headings. A comparison between two records that
name the same thing differently is a comparison waiting to be written
wrong.

This is answer-key material. No extraction code may reach it: the
import-linter contract "Extraction cannot read the answer key" in
`pyproject.toml` forbids the import structurally, the same way it already
forbids `domain.entities.answer_key`.

Distinct from `AnswerKey`, which is the *PDF's* five-field version of the
same truth. The tracker carries twenty-four columns and the PDF header
carries five; the five overlap, which is exactly what makes them worth
cross-checking (`ImportAnswerKey`). Two sources, two entities, one
reconciliation — not one entity pretending the two sources agree.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from domain.value_objects.category import Category
from domain.value_objects.outcome import Outcome


@dataclass(frozen=True)
class GroundTruthSignal:
    """One entry from the tracker's `Signals` cell: `code|SEVERITY|Owner Team`.

    Severity and owner team travel with the code because the Signal Taxonomy
    sheet defines them per signal — carrying them here means a disagreement
    can say *which* signal differed and who owns it, without a second lookup.
    """

    code: str
    severity: str
    owner_team: str


@dataclass(frozen=True)
class GroundTruth:
    """One Transcript Tracker row. `reference` is the call's business key.

    Every field below `reference` is optional in the sense that the tracker
    leaves most cells empty for most calls — an absent signal, no knowledge
    failure, no process gap. Empty means absent, and absent is a real answer
    the pipeline can get right or wrong; it is never "unknown". The only
    `None`s here are values the workbook genuinely did not state, or values
    it stated in a form this parser did not recognise — and the second kind
    always arrives with a warning beside it.
    """

    reference: str

    # --- the five the PDF header also carries (cross-checked) ------------
    category: Category | None = None
    archetype: str = ""
    rule_refs: tuple[str, ...] = ()
    outcome: Outcome | None = None
    score: int | None = None

    # --- the nineteen only the tracker carries ---------------------------
    product_line: str = ""
    touchpoint: str = ""
    aht_seconds: int | None = None

    complaint_present: bool | None = None
    complaint_attributed_to: str | None = None

    signals: tuple[GroundTruthSignal, ...] = field(default_factory=tuple)
    control_exceptions: tuple[str, ...] = ()

    escalation_triggered: bool | None = None
    escalation_type: str | None = None
    escalation_requested_by_caller: bool | None = None
    escalation_handled: bool | None = None

    knowledge_failure_present: bool | None = None
    knowledge_failure_rule_ref: str | None = None
    knowledge_failure_statement: str | None = None

    intent_type: str | None = None
    intent_evidence: str | None = None

    process_gap_present: bool | None = None
    process_gap_description: str | None = None

    broker_named_present: bool | None = None
    broker_named_broker_ref: str | None = None
    broker_named_sentiment: str | None = None

    # The tracker states a repeat as "C-0002 | 06 Jul | closed unresolved":
    # the prior call, its date, and how it closed. Only the reference is
    # structured here; the rest is kept verbatim as the note, because the
    # date is a partial one (no year) and re-deriving a full timestamp from
    # it would be inventing precision the cell does not have.
    repeat_of_reference: str | None = None
    repeat_of_note: str | None = None
