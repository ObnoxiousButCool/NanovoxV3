"""Mapping the Transcript Tracker's rows onto `GroundTruth`, against the
hand-built fixture in `tests/fixtures/tracker_sheet.py` rather than a real
xlsx. `read_workbook_sheets` itself is tested in `test_workbook_xml.py`.

The cases that matter here are the composite cells — the tracker packs
four facts into one escalation cell and a list into one signals cell — and
the refusal to guess when a cell does not match the documented form.
"""

from __future__ import annotations

import copy

import pytest

from domain.entities.ground_truth import GroundTruth
from domain.errors import ReferenceIntegrityError
from domain.value_objects.category import Category
from domain.value_objects.outcome import Outcome
from domain.value_objects.preventable import Preventable
from domain.value_objects.root_cause_owner import RootCauseOwner
from infrastructure.reference.xlsx_ground_truth_source import map_tracker_to_dataset
from tests.fixtures.tracker_sheet import TRACKER_SHEETS


def _row(reference: str) -> GroundTruth:
    dataset = map_tracker_to_dataset(TRACKER_SHEETS)
    return next(r for r in dataset.rows if r.reference == reference)


def test_reads_every_tracker_row() -> None:
    dataset = map_tracker_to_dataset(TRACKER_SHEETS)

    assert [r.reference for r in dataset.rows] == [
        "C-9001",
        "C-9002",
        "C-9003",
        "C-9004",
        "C-9005",
    ]


def test_maps_the_five_fields_the_pdf_also_carries() -> None:
    row = _row("C-9001")

    assert row.category is Category.CLAIMS_AND_EOB
    assert row.archetype == "Competent and resolved"
    assert row.rule_refs == ("C-12", "P-14")
    assert row.outcome is Outcome.RESOLVED
    assert row.score == 91


def test_an_em_dash_means_no_rules_cited_not_a_rule_called_em_dash() -> None:
    assert _row("C-9002").rule_refs == ()


def test_the_tracker_spells_partially_resolved_with_a_space() -> None:
    """The sheet writes "PARTIALLY RESOLVED"; the enum uses the underscore
    the Outcomes sheet's own identifier uses. Normalised, not warned about —
    a spelling difference between two sheets of one workbook is not a
    disagreement about a call.
    """
    row = _row("C-9003")

    assert row.outcome is Outcome.PARTIALLY_RESOLVED
    warnings = map_tracker_to_dataset(TRACKER_SHEETS).warnings
    assert not [w for w in warnings if w.startswith("C-9003:")]


def test_splits_the_complaint_cell_into_presence_and_target() -> None:
    assert (_row("C-9001").complaint_present, _row("C-9001").complaint_attributed_to) == (
        True,
        "CHOICE",
    )
    assert (_row("C-9002").complaint_present, _row("C-9002").complaint_attributed_to) == (
        False,
        None,
    )


def test_splits_the_escalation_cell_into_its_four_facts() -> None:
    handled = _row("C-9001")
    assert handled.escalation_triggered is True
    assert handled.escalation_type == "authority_limit"
    assert handled.escalation_requested_by_caller is True
    assert handled.escalation_handled is True

    unhandled = _row("C-9003")
    assert unhandled.escalation_requested_by_caller is True
    assert unhandled.escalation_handled is False


def test_not_triggered_leaves_the_other_three_escalation_facts_unset() -> None:
    """ "triggered false" states one thing and implies nothing about type,
    request or handling — those are absent, not False.
    """
    row = _row("C-9002")

    assert row.escalation_triggered is False
    assert row.escalation_type is None
    assert row.escalation_requested_by_caller is None
    assert row.escalation_handled is None


def test_an_escalation_nothing_warranted_is_read_without_its_annotation() -> None:
    """C-0120 (batch 2a) is the corpus's first "OVER-ESCALATION": nothing
    triggered it, and it was handled anyway. The annotation names the
    finding rather than a fifth fact — triggered=False with handled=True is
    already visible as the anomaly to anything reading both fields.
    """
    row = _row("C-9005")

    assert row.escalation_triggered is False
    assert row.escalation_type is None
    assert row.escalation_requested_by_caller is False
    assert row.escalation_handled is True
    assert not [w for w in map_tracker_to_dataset(TRACKER_SHEETS).warnings if "C-9005" in w]


def test_reads_a_semicolon_separated_list_of_signals_with_severity_and_owner() -> None:
    signals = _row("C-9001").signals

    assert [s.code for s in signals] == ["billing_defect", "retention_risk"]
    assert signals[0].severity == "HIGH"
    assert signals[0].owner_team == "Operations / Finance"
    assert signals[1].owner_team == "Account Management"


def test_an_empty_signals_cell_is_no_signals() -> None:
    assert _row("C-9002").signals == ()


def test_knowledge_failure_keeps_the_rule_id_and_the_statement_apart() -> None:
    row = _row("C-9001")

    assert row.knowledge_failure_present is True
    assert row.knowledge_failure_rule_ref == "C-12"
    assert row.knowledge_failure_statement == "major-service waiting periods do not apply"


def test_an_empty_optional_cell_means_absent_not_unknown() -> None:
    """Empty is a real answer the pipeline can get right or wrong. Only a
    cell the parser could not read becomes None.
    """
    row = _row("C-9002")

    assert row.knowledge_failure_present is False
    assert row.process_gap_present is False
    assert row.broker_named_present is False


def test_splits_intent_process_gap_and_broker_named() -> None:
    row = _row("C-9001")

    assert (row.intent_type, row.intent_evidence) == ("expansion", "verbatim, turn 14")
    assert row.process_gap_present is True
    assert row.process_gap_description == "denial letter should name the waiting period"
    assert (row.broker_named_broker_ref, row.broker_named_sentiment) == ("BRK-01", "ADVERSE")


def test_a_repeat_keeps_the_reference_structured_and_the_rest_verbatim() -> None:
    """The cell's date has no year, so re-deriving a timestamp from it would
    invent precision the sheet does not have.
    """
    row = _row("C-9001")

    assert row.repeat_of_reference == "C-0002"
    assert row.repeat_of_note == "06 Jul | closed unresolved"
    assert _row("C-9002").repeat_of_reference is None


def test_an_unreadable_cell_warns_and_leaves_the_field_unset() -> None:
    dataset = map_tracker_to_dataset(TRACKER_SHEETS)
    row = next(r for r in dataset.rows if r.reference == "C-9004")

    assert row.category is None
    assert row.outcome is None
    assert row.complaint_present is None
    assert row.escalation_triggered is None
    assert row.signals == ()
    assert row.root_cause_owner is None
    assert row.preventable is None

    warned_on = {w.split(": ", 1)[1].split(" value", 1)[0] for w in dataset.warnings}
    assert warned_on == {
        "Category",
        "Outcome",
        "Complaint",
        "Escalation",
        "Signals",
        "Root cause owner",
        "Preventable",
    }
    assert all(w.startswith("C-9004:") for w in dataset.warnings)


def test_root_cause_owner_matches_the_enums_own_names() -> None:
    assert _row("C-9001").root_cause_owner is RootCauseOwner.CHOICE
    assert _row("C-9003").root_cause_owner is RootCauseOwner.CARRIER


def test_an_empty_root_cause_owner_cell_is_absent_not_unknown() -> None:
    assert _row("C-9002").root_cause_owner is None


def test_preventable_reads_the_plain_form() -> None:
    assert _row("C-9001").preventable is Preventable.YES


def test_preventable_takes_only_the_leading_word_before_the_lever() -> None:
    """The tracker writes "Partly — communication": the lever names which
    lever fixes it, but only the Yes/Partly/No word maps to the enum."""
    row = _row("C-9003")

    assert row.preventable is Preventable.PARTLY
    assert not [w for w in map_tracker_to_dataset(TRACKER_SHEETS).warnings if "C-9003" in w]


def test_primary_issue_is_read_as_free_text() -> None:
    assert _row("C-9001").primary_issue == "claims & eob"
    assert _row("C-9002").primary_issue == ""


def test_secondary_issues_are_comma_split_and_trimmed() -> None:
    assert _row("C-9001").secondary_issues == ("missing id card", "dependent add")


def test_secondary_issues_none_or_blank_is_an_empty_tuple() -> None:
    assert _row("C-9002").secondary_issues == ()
    assert _row("C-9003").secondary_issues == ()  # the cell literally says "none"


def test_impact_scope_is_kept_as_a_raw_unparsed_string() -> None:
    """Deliberately not forced into `ImpactScope`'s four buckets — the
    tracker's own free text is messier than the pipeline's target shape.
    See `domain/value_objects/impact_scope.py`."""
    assert _row("C-9001").impact_scope == "1 member"
    assert _row("C-9005").impact_scope == "n_employees: 3"
    assert _row("C-9002").impact_scope == ""


def test_one_unreadable_row_does_not_cost_the_other_ninety_nine() -> None:
    """An answer key that refuses to load leaves Phase 5 with nothing to
    score against, which is worse than one that loads with fields flagged.
    """
    dataset = map_tracker_to_dataset(TRACKER_SHEETS)

    assert len(dataset.rows) == 5
    assert _row("C-9001").category is Category.CLAIMS_AND_EOB


def test_columns_are_resolved_by_name_so_a_reordered_sheet_still_maps() -> None:
    """A revision that moves a column must not silently misattribute a
    field — the same hardening `xlsx_reference_source` applies.
    """
    swapped = copy.deepcopy(TRACKER_SHEETS)
    rows = swapped["Transcript Tracker"]
    outcome, score = rows[0].index("Outcome"), rows[0].index("Score")
    for row in rows:
        row[outcome], row[score] = row[score], row[outcome]

    mapped = next(r for r in map_tracker_to_dataset(swapped).rows if r.reference == "C-9001")
    assert mapped.outcome is Outcome.RESOLVED
    assert mapped.score == 91


def test_a_workbook_with_no_tracker_sheet_fails_as_a_domain_error() -> None:
    with pytest.raises(ReferenceIntegrityError):
        map_tracker_to_dataset({"Employer Master": [["Employer ID"]]})


def test_a_tracker_with_no_header_row_fails_as_a_domain_error() -> None:
    with pytest.raises(ReferenceIntegrityError):
        map_tracker_to_dataset({"Transcript Tracker": [["Something Else", "Date / time"]]})
