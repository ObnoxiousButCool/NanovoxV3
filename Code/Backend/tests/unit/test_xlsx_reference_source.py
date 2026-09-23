"""Row-mapping logic — sheet rows to domain entities — against a small
hand-built `Sheets` fixture (`tests/fixtures/reference_sheets.py`), not a
real xlsx file. `read_workbook_sheets` itself (the XML parsing) is tested
separately, against a real minimal xlsx, in `test_workbook_xml.py`.
"""

from __future__ import annotations

import copy

from domain.value_objects.authority import Authority
from domain.value_objects.rule_confidence import RuleConfidence
from domain.value_objects.rule_layer import RuleLayer
from infrastructure.reference.xlsx_reference_source import map_sheets_to_dataset
from tests.fixtures.reference_sheets import REFERENCE_SHEETS


def test_reads_every_broker() -> None:
    dataset = map_sheets_to_dataset(REFERENCE_SHEETS)

    assert [b.reference for b in dataset.brokers] == ["BRK-01", "BRK-02"]
    salerno = dataset.brokers[0]
    assert salerno.name == "Anthony Salerno"
    assert salerno.agency == "Salerno Benefits Group"
    assert salerno.region == "Orange County"
    assert salerno.groups_in_book == 3


def test_employer_derived_fields_are_computed_not_read() -> None:
    dataset = map_sheets_to_dataset(REFERENCE_SHEETS)

    cedar_point = next(e for e in dataset.employers if e.reference == "EMP-1001")
    assert cedar_point.eligible == 420
    assert cedar_point.enrolled == 315
    assert cedar_point.broker_ref == "BRK-01"
    assert cedar_point.participation == 0.75
    assert cedar_point.fee_band == 50  # 420 eligible -> 200+ band
    assert cedar_point.annual_fee == 600
    assert cedar_point.cobra_regime == "Federal COBRA"  # 420 >= 20
    assert cedar_point.annual_premium == 315 * 486  # the parsed lever


def test_a_small_employer_lands_in_cal_cobra_and_the_lowest_fee_band() -> None:
    dataset = map_sheets_to_dataset(REFERENCE_SHEETS)

    bellwether = next(e for e in dataset.employers if e.reference == "EMP-1002")
    assert bellwether.fee_band == 25  # 5 eligible -> 2-8 band
    assert bellwether.cobra_regime == "Cal-COBRA"  # 5 < 20


def test_members_have_no_broker_field_and_parse_repeat_caller_as_a_bool() -> None:
    dataset = map_sheets_to_dataset(REFERENCE_SHEETS)

    assert not hasattr(dataset.members[0], "broker_ref")
    omar = next(m for m in dataset.members if m.reference == "CB-7700001")
    anouk = next(m for m in dataset.members if m.reference == "CB-7700002")
    assert omar.repeat_caller is False
    assert anouk.repeat_caller is True
    assert omar.employer_ref == "EMP-1001"


def test_employer_contacts_resolve_authority() -> None:
    dataset = map_sheets_to_dataset(REFERENCE_SHEETS)

    quentin = next(c for c in dataset.employer_contacts if c.reference == "CON-101")
    sandra = next(c for c in dataset.employer_contacts if c.reference == "CON-102")
    assert quentin.authority is Authority.CANNOT_BIND
    assert sandra.authority is Authority.CAN_BIND


def test_agent_variance_column_is_matched_by_prefix() -> None:
    """The header carries a typographic sign ('Score variance (±)')."""
    dataset = map_sheets_to_dataset(REFERENCE_SHEETS)

    sarah = dataset.agents[0]
    assert sarah.expected_score == 88
    assert sarah.score_variance == 7


def test_rules_read_from_all_three_layers_with_the_right_area_column() -> None:
    dataset = map_sheets_to_dataset(REFERENCE_SHEETS)

    by_ref = {r.reference: r for r in dataset.rules}
    assert by_ref["P-01"].layer is RuleLayer.PROGRAM
    assert by_ref["P-01"].area == "Group eligibility"
    assert by_ref["P-01"].call_scenarios is None

    assert by_ref["A-01"].layer is RuleLayer.ADMINISTRATION
    assert by_ref["A-01"].call_scenarios == "New hire given the wrong start date."

    assert by_ref["C-01"].layer is RuleLayer.CARRIER
    assert by_ref["C-01"].area == "DeltaCare USA — DHMO"  # "Carrier / line" column
    assert by_ref["C-01"].confidence is RuleConfidence.VERIFIED_SECONDARY


def test_touchpoints_read_owner_and_controls() -> None:
    dataset = map_sheets_to_dataset(REFERENCE_SHEETS)

    touchpoint = dataset.touchpoints[0]
    assert touchpoint.reference == "enrolment_meeting"
    assert touchpoint.owner == "Broker Relations"
    assert touchpoint.controls == "The broker, not Choice"


def test_warns_when_the_premium_lever_is_missing() -> None:
    sheets = copy.deepcopy(REFERENCE_SHEETS)
    sheets["Distribution Targets"] = [["Section", "Target", "Share / value"]]

    dataset = map_sheets_to_dataset(sheets)

    assert any("premium" in w.lower() for w in dataset.warnings)
    assert all(e.annual_premium is None for e in dataset.employers)


def test_warns_when_a_rule_sheet_is_missing_rather_than_raising() -> None:
    sheets = copy.deepcopy(REFERENCE_SHEETS)
    del sheets["Rules — Carrier"]

    dataset = map_sheets_to_dataset(sheets)

    assert not any(r.reference.startswith("C-") for r in dataset.rules)
    assert any("Rules — Carrier" in w for w in dataset.warnings)
