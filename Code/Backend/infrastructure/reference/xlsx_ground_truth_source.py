"""Maps the workbook's Transcript Tracker sheet onto `GroundTruth`.

Follows `xlsx_reference_source`: find the header row by its own first-column
heading rather than a fixed index, resolve columns by name so a reordered
revision cannot silently misattribute a field, and read the data rows below.

The tracker packs several fields into one cell with `|` separators, and
lists with `; `. Every one of those forms is parsed here against what the
sheet actually contains, not against what it might reasonably contain:

    Complaint           absent
                        present|CHOICE
    Escalation          triggered false
                        triggered true|authority_limit|requested_by_caller true|handled true
    Signals             code|SEVERITY|Owner Team; code|SEVERITY|Owner Team
    Knowledge failure   present|C-12|major-service waiting periods do not apply
    Intent              expansion|verbatim, turn 14
    Process gap         present|denial letter should name the network
    Broker named        present|BRK-01|ADVERSE
    Repeat of           C-0002 | 06 Jul | closed unresolved
    Rule refs           A-05, A-06, A-09     (or the em-dash for none)

Anything that does not match produces a warning naming the call and the
column, and leaves that field unset. It never guesses, and it never aborts
the import: an answer key that refuses to load leaves Phase 5 with nothing
to score against, which is worse than one that loads with three fields
flagged.

Answer-key material. No extraction code may import this module — the
import-linter contract "Extraction cannot read the answer key" in
`pyproject.toml` forbids it structurally.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from application.ports.ground_truth_source import GroundTruthDataset, GroundTruthSource
from domain.entities.ground_truth import GroundTruth, GroundTruthSignal
from domain.errors import ReferenceIntegrityError
from domain.value_objects.category import Category
from domain.value_objects.outcome import Outcome
from infrastructure.reference.workbook_xml import Sheets, read_workbook_sheets

# Called with (column name, offending raw value) when a cell does not match
# the form documented above. Closes over the call reference at the call site,
# so the parsing helpers never need to carry it.
Warn = Callable[[str, str], None]

_SHEET = "Transcript Tracker"
_FIRST_COLUMN = "Call ID"
_CALL_PREFIX = "C-"

# The tracker writes "no rules cited" as an em-dash, the same convention the
# corpus PDF's header uses.
_NONE_MARKER = "—"
_LIST_SEPARATOR = "; "
_PART_SEPARATOR = "|"

# The tracker spells this outcome with a space; the enum uses an underscore,
# as the Outcomes sheet's own identifier does. Mapping it here keeps the
# workbook's spelling out of the domain.
_OUTCOME_SPELLINGS = {"PARTIALLY RESOLVED": Outcome.PARTIALLY_RESOLVED}

_PRESENT = "present"
_ABSENT = "absent"
_TRIGGERED_TRUE = "triggered true"
_TRIGGERED_FALSE = "triggered false"


def _cell(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return (row[index] or "").strip()


def _as_int(value: str) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _flag(part: str, name: str) -> bool | None:
    """`"handled true"` → True. Returns None for anything else."""
    remainder = part.removeprefix(name).strip()
    if remainder == "true":
        return True
    if remainder == "false":
        return False
    return None


def _without_annotation(part: str) -> str:
    """Drops a trailing `" — <label>"` comment, e.g. `"handled true —
    OVER-ESCALATION"` → `"handled true"`.

    Scoped to this one call site rather than applied broadly: an em dash on
    its own is `_NONE_MARKER` elsewhere in the tracker (a blank cell), so a
    generic strip-after-em-dash rule would misread those cells instead.
    """
    head, separator, _annotation = part.partition(" — ")
    return head if separator else part


class XlsxGroundTruthSource(GroundTruthSource):
    def __init__(self, path: Path) -> None:
        self._path = path

    def read(self) -> GroundTruthDataset:
        return map_tracker_to_dataset(read_workbook_sheets(self._path))


class _Mapper:
    """Holds nothing; groups the per-column parsing so the module reads in
    the order the sheet does."""

    @classmethod
    def map(cls, sheets: Sheets) -> GroundTruthDataset:
        rows = sheets.get(_SHEET)
        if rows is None:
            raise ReferenceIntegrityError(
                f"workbook has no {_SHEET!r} sheet",
                detail="the workbook may be the wrong revision, or its layout has changed",
            )

        header_index, columns = cls._find_header(rows)
        warnings: list[str] = []
        parsed = [
            cls._parse_row(row, columns, warnings)
            for row in rows[header_index + 1 :]
            if _cell(row, 0).startswith(_CALL_PREFIX)
        ]
        return GroundTruthDataset(rows=tuple(parsed), warnings=tuple(warnings))

    @classmethod
    def _find_header(cls, rows: list[list[str]]) -> tuple[int, dict[str, int]]:
        for index, row in enumerate(rows):
            if _cell(row, 0) == _FIRST_COLUMN:
                return index, {
                    name.strip(): i for i, name in enumerate(row) if name and name.strip()
                }
        raise ReferenceIntegrityError(
            f"sheet {_SHEET!r} has no header row starting with {_FIRST_COLUMN!r}",
            detail="the workbook may be the wrong revision, or its layout has changed",
        )

    @classmethod
    def _parse_row(
        cls, row: list[str], columns: dict[str, int], warnings: list[str]
    ) -> GroundTruth:
        def value(name: str) -> str:
            return _cell(row, columns.get(name))

        reference = value(_FIRST_COLUMN)

        def warn(column: str, raw: str) -> None:
            warnings.append(
                f"{reference}: {column} value {raw!r} is not in a form this parser recognises "
                f"— the field is left unset rather than guessed"
            )

        complaint_present, complaint_target = cls._complaint(value("Complaint"), warn)
        triggered, esc_type, requested, handled = cls._escalation(value("Escalation"), warn)
        kf_present, kf_rule, kf_statement = cls._knowledge_failure(value("Knowledge failure"), warn)
        intent_type, intent_evidence = cls._intent(value("Intent"), warn)
        gap_present, gap_description = cls._process_gap(value("Process gap"), warn)
        broker_present, broker_ref, broker_sentiment = cls._broker_named(
            value("Broker named"), warn
        )
        repeat_reference, repeat_note = cls._repeat_of(value("Repeat of"))

        return GroundTruth(
            reference=reference,
            category=cls._category(value("Category"), warn),
            archetype=value("Archetype"),
            rule_refs=cls._refs(value("Rule refs")),
            outcome=cls._outcome(value("Outcome"), warn),
            score=_as_int(value("Score")),
            product_line=value("Product line"),
            touchpoint=value("Touchpoint"),
            aht_seconds=_as_int(value("AHT (s)")),
            complaint_present=complaint_present,
            complaint_attributed_to=complaint_target,
            signals=cls._signals(value("Signals"), warn),
            control_exceptions=tuple(cls._items(value("Control exceptions"))),
            escalation_triggered=triggered,
            escalation_type=esc_type,
            escalation_requested_by_caller=requested,
            escalation_handled=handled,
            knowledge_failure_present=kf_present,
            knowledge_failure_rule_ref=kf_rule,
            knowledge_failure_statement=kf_statement,
            intent_type=intent_type,
            intent_evidence=intent_evidence,
            process_gap_present=gap_present,
            process_gap_description=gap_description,
            broker_named_present=broker_present,
            broker_named_broker_ref=broker_ref,
            broker_named_sentiment=broker_sentiment,
            repeat_of_reference=repeat_reference,
            repeat_of_note=repeat_note,
        )

    # --- per-column parsing ------------------------------------------------

    @staticmethod
    def _items(raw: str) -> list[str]:
        if not raw or raw == _NONE_MARKER:
            return []
        return [item.strip() for item in raw.split(_LIST_SEPARATOR) if item.strip()]

    @staticmethod
    def _refs(raw: str) -> tuple[str, ...]:
        if not raw or raw == _NONE_MARKER:
            return ()
        return tuple(ref.strip() for ref in raw.split(",") if ref.strip())

    @staticmethod
    def _category(raw: str, warn: Warn) -> Category | None:
        if not raw:
            return None
        try:
            return Category(raw)
        except ValueError:
            warn("Category", raw)
            return None

    @staticmethod
    def _outcome(raw: str, warn: Warn) -> Outcome | None:
        if not raw:
            return None
        if raw in _OUTCOME_SPELLINGS:
            return _OUTCOME_SPELLINGS[raw]
        try:
            return Outcome(raw)
        except ValueError:
            warn("Outcome", raw)
            return None

    @staticmethod
    def _complaint(raw: str, warn: Warn) -> tuple[bool | None, str | None]:
        if not raw:
            return None, None
        if raw == _ABSENT:
            return False, None
        parts = raw.split(_PART_SEPARATOR)
        if parts[0] == _PRESENT and len(parts) == 2:
            return True, parts[1].strip()
        warn("Complaint", raw)
        return None, None

    @staticmethod
    def _escalation(
        raw: str, warn: Warn
    ) -> tuple[bool | None, str | None, bool | None, bool | None]:
        if not raw:
            return None, None, None, None
        if raw == _TRIGGERED_FALSE:
            return False, None, None, None
        parts = [p.strip() for p in raw.split(_PART_SEPARATOR)]
        if parts[0] == _TRIGGERED_TRUE and len(parts) == 4:
            return (
                True,
                parts[1],
                _flag(parts[2], "requested_by_caller"),
                _flag(parts[3], "handled"),
            )
        if parts[0] == _TRIGGERED_FALSE and len(parts) == 4 and parts[1] == "none":
            # Nothing warranted escalation, and it happened anyway — the
            # tracker calls this out with a trailing " — OVER-ESCALATION"
            # annotation on the "handled" fact (first seen on C-0120). The
            # annotation names a finding, not a fourth fact to store: an
            # escalation with no trigger type is not one of the eight
            # documented trigger types, and the combination
            # triggered=False, handled=True is already visible as an
            # anomaly to anything that reads both fields.
            return (
                False,
                None,
                _flag(parts[2], "requested_by_caller"),
                _flag(_without_annotation(parts[3]), "handled"),
            )
        warn("Escalation", raw)
        return None, None, None, None

    @classmethod
    def _signals(cls, raw: str, warn: Warn) -> tuple[GroundTruthSignal, ...]:
        signals = []
        for item in cls._items(raw):
            parts = [p.strip() for p in item.split(_PART_SEPARATOR)]
            if len(parts) != 3:
                warn("Signals", item)
                continue
            signals.append(GroundTruthSignal(code=parts[0], severity=parts[1], owner_team=parts[2]))
        return tuple(signals)

    @staticmethod
    def _knowledge_failure(raw: str, warn: Warn) -> tuple[bool | None, str | None, str | None]:
        if not raw:
            return False, None, None
        parts = raw.split(_PART_SEPARATOR, 2)
        if parts[0] == _PRESENT and len(parts) == 3:
            return True, parts[1].strip(), parts[2].strip()
        warn("Knowledge failure", raw)
        return None, None, None

    @staticmethod
    def _intent(raw: str, warn: Warn) -> tuple[str | None, str | None]:
        if not raw:
            return None, None
        parts = raw.split(_PART_SEPARATOR, 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
        warn("Intent", raw)
        return None, None

    @staticmethod
    def _process_gap(raw: str, warn: Warn) -> tuple[bool | None, str | None]:
        if not raw:
            return False, None
        parts = raw.split(_PART_SEPARATOR, 1)
        if parts[0] == _PRESENT and len(parts) == 2:
            return True, parts[1].strip()
        warn("Process gap", raw)
        return None, None

    @staticmethod
    def _broker_named(raw: str, warn: Warn) -> tuple[bool | None, str | None, str | None]:
        if not raw:
            return False, None, None
        parts = [p.strip() for p in raw.split(_PART_SEPARATOR)]
        if parts[0] == _PRESENT and len(parts) == 3:
            return True, parts[1], parts[2]
        warn("Broker named", raw)
        return None, None, None

    @staticmethod
    def _repeat_of(raw: str) -> tuple[str | None, str | None]:
        """`"C-0002 | 06 Jul | closed unresolved"` → the reference and the rest.

        No warning path: the cell is free text after the reference, and the
        reference is the only part with a defined shape. A cell that does not
        start with a call reference simply yields no repeat.
        """
        if not raw:
            return None, None
        head, _, remainder = raw.partition(_PART_SEPARATOR)
        head = head.strip()
        if not head.startswith(_CALL_PREFIX):
            return None, None
        note = remainder.strip() or None
        return head, note


def map_tracker_to_dataset(sheets: Sheets) -> GroundTruthDataset:
    """The tracker sheet, mapped to domain rows.

    Separate from reading the file, exactly as `map_sheets_to_dataset` is in
    `xlsx_reference_source`: the mapping is where the judgement lives, so it
    is tested against a hand-built `Sheets` fixture rather than a binary
    xlsx checked into the tests.
    """
    return _Mapper.map(sheets)
