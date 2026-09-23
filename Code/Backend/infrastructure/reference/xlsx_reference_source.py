"""Maps the workbook's master-data sheets onto domain entities.

Ported from the prototype's `tools/03_join_corpus.py`: locate each sheet's
header row, resolve columns by name (not position — a workbook revision
that reorders columns must not silently misattribute a field), and read
data rows below it.

Header rows are found by searching for the sheet's own first-column
heading (``"Broker ID"``, ``"Rule ID"``, ...) rather than assumed at a fixed
row index. `03_join_corpus.py` does this already for the Rules sheets
(`next(r for r in d[sheet] if cell(r, 0) == "Rule ID")`); applying the same
technique to every sheet here is a deliberate hardening, not a departure —
the fixed-index form it uses elsewhere depends on the raw XML emitting a
`<row>` element for every blank row above the header, which happens to hold
for this workbook but isn't a property worth depending on going forward.
"""

from __future__ import annotations

from pathlib import Path

from application.ports.reference_source import ReferenceDataset, ReferenceSource
from domain.entities.agent import Agent
from domain.entities.broker import Broker
from domain.entities.employer import Employer
from domain.entities.employer_contact import EmployerContact
from domain.entities.member import Member
from domain.entities.rule import Rule
from domain.entities.touchpoint import Touchpoint
from domain.errors import ReferenceIntegrityError
from domain.reference_derivations import (
    annual_fee,
    annual_premium,
    calls_per_100,
    cobra_regime,
    fee_band,
    participation,
)
from domain.value_objects.authority import Authority
from domain.value_objects.rule_confidence import RuleConfidence
from domain.value_objects.rule_layer import RuleLayer
from infrastructure.reference.workbook_xml import Sheets, read_workbook_sheets

_PREMIUM_LEVER_LABEL = "Annual premium per enrolled life"
_RULE_SHEETS: tuple[tuple[str, RuleLayer], ...] = (
    ("Rules — Program", RuleLayer.PROGRAM),
    ("Rules — Administration", RuleLayer.ADMINISTRATION),
    ("Rules — Carrier", RuleLayer.CARRIER),
)


def _cell(row: list[str], index: int) -> str:
    return (row[index] if index < len(row) else "") or ""


def _find_header(
    rows: list[list[str]], first_column: str, *, sheet: str
) -> tuple[int, dict[str, int]]:
    """The row index and column-name → index map for a sheet's header row.

    Raises a domain error, not a bare `ValueError` — a workbook missing an
    expected header is bad source data, exactly like an unresolved broker
    reference, and needs to fail the same clean way through the CLI and the
    API rather than crashing with a raw traceback.
    """
    for row_index, row in enumerate(rows):
        if _cell(row, 0).strip() == first_column:
            columns = {name.strip(): i for i, name in enumerate(row) if name and name.strip()}
            return row_index, columns
    raise ReferenceIntegrityError(
        f"sheet {sheet!r} has no header row starting with {first_column!r}",
        detail="the workbook may be the wrong revision, or its layout has changed",
    )


def _rows_with_prefix(rows: list[list[str]], header_row: int, prefix: str) -> list[list[str]]:
    return [r for r in rows[header_row + 1 :] if _cell(r, 0).strip().startswith(prefix)]


def _as_int(value: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def _as_float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _premium_per_life(sheets: Sheets) -> float | None:
    """The flat per-life premium lever, parsed rather than hardcoded.

    Distribution Targets carries one reference figure — "Annual premium per
    enrolled life ($)" — that Employer Master's population was built from
    (tools/README.md). Parsing it means a corpus revision that changes the
    lever changes every figure downstream instead of silently going stale.
    """
    for row in sheets.get("Distribution Targets", []):
        label = " ".join(str(cell) for cell in row if cell)
        if _PREMIUM_LEVER_LABEL not in label:
            continue
        for cell in row:
            value = _as_float(cell)
            # Skip share/index columns (typically <= 1) sitting in the same row.
            if value is not None and value > 1:
                return value
    return None


def map_sheets_to_dataset(sheets: Sheets) -> ReferenceDataset:
    """The row-mapping half of `XlsxReferenceSource`, independent of file I/O.

    Split out so the mapping logic — column resolution, prefix filtering,
    derivation wiring — can be tested against a small hand-built `Sheets`
    dict, without needing a real xlsx fixture on disk.
    """
    return _SheetMapper().map(sheets)


class XlsxReferenceSource(ReferenceSource):
    """Reads master data from the build-bible workbook at `path`."""

    def __init__(self, path: Path) -> None:
        self._path = path

    def read(self) -> ReferenceDataset:
        sheets = read_workbook_sheets(self._path)
        return map_sheets_to_dataset(sheets)


class _SheetMapper:
    """Implementation detail of `map_sheets_to_dataset` — not part of the
    public module surface; use that function instead.
    """

    def map(self, sheets: Sheets) -> ReferenceDataset:
        warnings: list[str] = []

        brokers = self._read_brokers(sheets)
        premium_per_life = _premium_per_life(sheets)
        if premium_per_life is None:
            warnings.append(
                "no 'Annual premium per enrolled life' lever found in Distribution "
                "Targets; every employer's annual_premium will be None"
            )
        employers = self._read_employers(sheets, premium_per_life)
        members = self._read_members(sheets)
        contacts = self._read_employer_contacts(sheets)
        agents = self._read_agents(sheets)
        rules, rule_warnings = self._read_rules(sheets)
        touchpoints = self._read_touchpoints(sheets)
        warnings.extend(rule_warnings)

        return ReferenceDataset(
            brokers=brokers,
            employers=employers,
            members=members,
            employer_contacts=contacts,
            agents=agents,
            rules=rules,
            touchpoints=touchpoints,
            warnings=tuple(warnings),
        )

    def _read_brokers(self, sheets: Sheets) -> tuple[Broker, ...]:
        rows = sheets.get("Broker Master", [])
        header_row, columns = _find_header(rows, "Broker ID", sheet="Broker Master")
        brokers = []
        for row in _rows_with_prefix(rows, header_row, "BRK"):
            brokers.append(
                Broker(
                    reference=_cell(row, 0).strip(),
                    name=_cell(row, columns["Broker"]).strip(),
                    agency=_cell(row, columns["Agency"]).strip(),
                    region=_cell(row, columns["Region"]).strip(),
                    groups_in_book=_as_int(_cell(row, columns["Groups in book"])),
                    signal_profile=_cell(row, columns["Signal profile"]).strip(),
                )
            )
        return tuple(brokers)

    def _read_employers(
        self, sheets: Sheets, premium_per_life: float | None
    ) -> tuple[Employer, ...]:
        rows = sheets.get("Employer Master", [])
        header_row, columns = _find_header(rows, "Employer ID", sheet="Employer Master")
        employers = []
        for row in _rows_with_prefix(rows, header_row, "EMP"):
            eligible = _as_int(_cell(row, columns["Eligible employees"]))
            enrolled = _as_int(_cell(row, columns["Enrolled lives"]))
            planned_calls = _as_int(_cell(row, columns["Planned calls"]))
            employers.append(
                Employer(
                    reference=_cell(row, 0).strip(),
                    name=_cell(row, columns["Employer name"]).strip(),
                    industry=_cell(row, columns["Industry"]).strip(),
                    design_churn_profile=_cell(row, columns["Churn profile"]).strip(),
                    eligible=eligible,
                    enrolled=enrolled,
                    region=_cell(row, columns["Region"]).strip(),
                    renewal_month=_cell(row, columns["Renewal month"]).strip(),
                    broker_ref=_cell(row, columns["Broker of record"]).strip(),
                    dental_sponsorship=_cell(row, columns["Dental sponsorship"]).strip(),
                    lines_held=_cell(row, columns["Lines held"]).strip(),
                    planned_calls=planned_calls,
                    planned_member_calls=_as_int(_cell(row, columns["Member calls"])),
                    planned_employer_calls=_as_int(_cell(row, columns["Employer calls"])),
                    participation=participation(enrolled, eligible),
                    fee_band=fee_band(eligible),
                    annual_fee=annual_fee(eligible),
                    annual_premium=annual_premium(enrolled, premium_per_life),
                    cobra_regime=cobra_regime(eligible),
                    calls_per_100=calls_per_100(planned_calls, enrolled),
                )
            )
        return tuple(employers)

    def _read_members(self, sheets: Sheets) -> tuple[Member, ...]:
        rows = sheets.get("Member Master", [])
        header_row, columns = _find_header(rows, "Member ID", sheet="Member Master")
        members = []
        for row in _rows_with_prefix(rows, header_row, "CB"):
            members.append(
                Member(
                    reference=_cell(row, 0).strip(),
                    name=_cell(row, columns["Member name"]).strip(),
                    age=_as_int(_cell(row, columns["Age"])),
                    employer_ref=_cell(row, columns["Employer ID"]).strip(),
                    primary_line=_cell(row, columns["Primary line"]).strip(),
                    planned_calls=_as_int(_cell(row, columns["Planned calls"])),
                    repeat_caller=bool(_cell(row, columns["Repeat caller"]).strip()),
                )
            )
        return tuple(members)

    def _read_employer_contacts(self, sheets: Sheets) -> tuple[EmployerContact, ...]:
        rows = sheets.get("Employer Contacts", [])
        header_row, columns = _find_header(rows, "Contact ID", sheet="Employer Contacts")
        contacts = []
        for row in _rows_with_prefix(rows, header_row, "CON"):
            contacts.append(
                EmployerContact(
                    reference=_cell(row, 0).strip(),
                    name=_cell(row, columns["Contact name"]).strip(),
                    role=_cell(row, columns["Role"]).strip(),
                    authority=Authority(_cell(row, columns["Authority"]).strip()),
                    employer_ref=_cell(row, columns["Employer ID"]).strip(),
                    planned_calls=_as_int(_cell(row, columns["Planned calls"])),
                )
            )
        return tuple(contacts)

    def _read_agents(self, sheets: Sheets) -> tuple[Agent, ...]:
        rows = sheets.get("Agent Roster", [])
        header_row, columns = _find_header(rows, "Agent ID", sheet="Agent Roster")
        # The variance column's header carries a typographic sign
        # ("Score variance (±)") that a corpus revision is free to change;
        # matched by prefix rather than the exact string.
        variance_column = next(
            (i for name, i in columns.items() if name.startswith("Score variance")), None
        )
        agents = []
        for row in _rows_with_prefix(rows, header_row, "AGT"):
            agents.append(
                Agent(
                    reference=_cell(row, 0).strip(),
                    name=_cell(row, columns["Agent"]).strip(),
                    band=_cell(row, columns["Band"]).strip(),
                    planned_calls=_as_int(_cell(row, columns["Planned calls"])),
                    expected_score=_as_float(_cell(row, columns["Expected mean score"])),
                    score_variance=(
                        _as_float(_cell(row, variance_column))
                        if variance_column is not None
                        else None
                    ),
                    dominant_pattern=_cell(row, columns["Dominant pattern"]).strip(),
                )
            )
        return tuple(agents)

    def _read_rules(self, sheets: Sheets) -> tuple[tuple[Rule, ...], list[str]]:
        rules: list[Rule] = []
        warnings: list[str] = []
        for sheet_name, layer in _RULE_SHEETS:
            rows = sheets.get(sheet_name, [])
            if not rows:
                warnings.append(f"sheet {sheet_name!r} not found; no {layer.value}-rules read")
                continue
            header_row, columns = _find_header(rows, "Rule ID", sheet=sheet_name)
            area_column = "Area" if "Area" in columns else "Carrier / line"
            for row in rows[header_row + 1 :]:
                reference = _cell(row, 0).strip()
                if not reference.startswith(f"{layer.value}-"):
                    continue
                rules.append(
                    Rule(
                        reference=reference,
                        layer=layer,
                        area=_cell(row, columns[area_column]).strip(),
                        text=_cell(row, columns["Rule"]).strip(),
                        commonly_confused_with=_cell(
                            row, columns["Commonly confused with"]
                        ).strip(),
                        source=_cell(row, columns["Source"]).strip(),
                        confidence=RuleConfidence(_cell(row, columns["Confidence"]).strip()),
                        call_scenarios=(
                            _cell(row, columns["Call scenarios it generates"]).strip()
                            if "Call scenarios it generates" in columns
                            else None
                        ),
                    )
                )
        return tuple(rules), warnings

    def _read_touchpoints(self, sheets: Sheets) -> tuple[Touchpoint, ...]:
        rows = sheets.get("Touchpoints", [])
        header_row, columns = _find_header(rows, "Touchpoint", sheet="Touchpoints")
        touchpoints = []
        for row in rows[header_row + 1 :]:
            reference = _cell(row, 0).strip()
            if not reference:
                continue
            touchpoints.append(
                Touchpoint(
                    reference=reference,
                    owner=_cell(row, columns["Owner"]).strip(),
                    controls=_cell(row, columns["Who controls the content"]).strip(),
                )
            )
        return tuple(touchpoints)
