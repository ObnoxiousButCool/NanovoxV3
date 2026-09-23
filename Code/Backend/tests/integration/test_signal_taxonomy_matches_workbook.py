"""`SignalCode` against the Signal Taxonomy sheet it was transcribed from.

Same guard as `test_dashboard_config_matches_workbook.py`, for the same
reason. Severity drives ranking and owner drives routing, and the sheet
calls both mandatory — so a severity that has drifted silently reorders the
Inferences screen, and a wrong owner team routes a compliance failure to the
call centre.

The membership check matters more than either. A signal added to the sheet
and not to the enum is not an error anywhere: the parser records it as an
unrecognised code, the aggregations never count it, and the screen shows a
smaller number with no indication that anything is missing.

The corpus lives in `Documents/` and is tracked, so this runs by default.
"""

from __future__ import annotations

import pytest

from domain.value_objects.signal_code import SignalCode, owner_team_of, severity_of
from infrastructure.config.paths import DEFAULT_WORKBOOK_PATH
from infrastructure.reference.workbook_xml import Sheets, read_workbook_sheets

pytestmark = pytest.mark.skipif(
    not DEFAULT_WORKBOOK_PATH.exists(),
    reason="corpus not found — expected it under Documents/ (see infrastructure/config/paths.py)",
)


@pytest.fixture(scope="module")
def sheets() -> Sheets:
    return read_workbook_sheets(DEFAULT_WORKBOOK_PATH)


def _taxonomy(sheets: Sheets) -> dict[str, tuple[str, str]]:
    """{signal type: (severity, owner)} from the sheet's own rows."""
    rows = sheets["Signal Taxonomy"]
    header = next(
        index for index, row in enumerate(rows) if row and row[0].strip() == "Signal type"
    )
    code, severity, owner = (
        rows[header].index(name) for name in ("Signal type", "Severity", "Owner")
    )

    return {
        row[code].strip(): (row[severity].strip(), row[owner].strip())
        for row in rows[header + 1 :]
        if len(row) > owner and row[code].strip()
    }


def test_the_enum_is_exactly_the_sheets_signal_types(sheets: Sheets) -> None:
    assert {signal.value for signal in SignalCode} == set(_taxonomy(sheets))


def test_every_severity_and_owner_matches_the_sheet(sheets: Sheets) -> None:
    from_sheet = _taxonomy(sheets)

    mismatched = [
        f"{signal.value}: code says ({severity_of(signal).value}, {owner_team_of(signal)!r}), "
        f"sheet says {from_sheet[signal.value]}"
        for signal in SignalCode
        if (severity_of(signal).value, owner_team_of(signal)) != from_sheet[signal.value]
    ]

    assert mismatched == []


def test_knowledge_error_is_the_agent_conduct_signal_and_stands_alone(sheets: Sheets) -> None:
    """D7's distinction, checked against the sheet rather than trusted.

    `knowledge_error` — "an agent stated a published rule incorrectly" — is
    the real agent-conduct event. The `knowledge_failure` *tag* (schema field
    8) is a different thing that the workbook contradicts itself about, and
    D7 is open with Karim on it. If a signal named `knowledge_failure` ever
    appears in this taxonomy the two have been merged upstream, and that is a
    conversation, not a code change.
    """
    taxonomy = _taxonomy(sheets)

    assert taxonomy[SignalCode.KNOWLEDGE_ERROR.value] == ("MEDIUM", "Knowledge Management")
    assert "knowledge_failure" not in taxonomy
