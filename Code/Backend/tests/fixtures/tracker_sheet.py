"""A small `Sheets` dict with the real Transcript Tracker's column layout,
so the mapping in `infrastructure/reference/xlsx_ground_truth_source.py` can
be tested without a binary xlsx fixture — the same arrangement as
`reference_sheets.py`.

The header sits at index 0 here; the real sheet has a title and a
description paragraph above it, and `_find_header` searches by content, so
the position does not matter to what is under test.

Four rows, each chosen to exercise a different shape rather than to look
like a plausible corpus:

    C-9001  every composite column populated, escalation triggered and
            handled, two signals, a repeat
    C-9002  the quiet row — complaint absent, escalation not triggered,
            every optional cell empty, and an em-dash for "no rules"
    C-9003  the four-word outcome the tracker spells with a space, and an
            escalation that was requested but not handled
    C-9004  malformed cells in seven columns, to prove the parser warns and
            leaves the field unset rather than guessing
    C-9005  an escalation with nothing warranting it, escalated anyway — the
            tracker's " — OVER-ESCALATION" annotation on an otherwise
            untriggered row (first seen on C-0120, batch 2a)

Five more columns, added for the v10 schema fields (`Documents/notes/Corpus-v10-Schema-Update.md`
§3): `Root cause owner`, `Preventable`, `Primary issue`, `Secondary issues`,
`Impact scope`. C-9003 also exercises `Preventable`'s "Partly — lever" shape.
"""

from __future__ import annotations

from infrastructure.reference.workbook_xml import Sheets

_HEADER = [
    "Call ID",
    "Date / time",
    "Batch",
    "Caller type",
    "caller_ref",
    "Caller name",
    "Agent",
    "Category",
    "Product line",
    "Rule refs",
    "Touchpoint",
    "Outcome",
    "Score",
    "AHT (s)",
    "Archetype",
    "Complaint",
    "Signals",
    "Escalation",
    "Control exceptions",
    "Knowledge failure",
    "Intent",
    "Process gap",
    "Broker named",
    "Repeat of",
    "Root cause owner",
    "Preventable",
    "Primary issue",
    "Secondary issues",
    "Impact scope",
]

TRACKER_SHEETS: Sheets = {
    "Transcript Tracker": [
        _HEADER,
        [
            "C-9001",
            "Mon 06 Jul 2026 09:14",
            "B1",
            "MEMBER",
            "CB-7700205",
            "Leon Castellano",
            "AGT-01|Sarah Whitlock",
            "Claims & EOB",
            "dental",
            "C-12, P-14",
            "denial_letter_eob",
            "RESOLVED",
            "91",
            "380",
            "Competent and resolved",
            "present|CHOICE",
            "billing_defect|HIGH|Operations / Finance; retention_risk|CRITICAL|Account Management",
            "triggered true|authority_limit|requested_by_caller true|handled true",
            "no_recording_disclosure",
            "present|C-12|major-service waiting periods do not apply",
            "expansion|verbatim, turn 14",
            "present|denial letter should name the waiting period",
            "present|BRK-01|ADVERSE",
            "C-0002 | 06 Jul | closed unresolved",
            "CHOICE",
            "Yes",
            "claims & eob",
            "missing id card, dependent add",
            "1 member",
        ],
        [
            "C-9002",
            "Mon 06 Jul 2026 10:41",
            "B1",
            "EMPLOYER",
            "CON-137",
            "Sandra Villalobos",
            "AGT-05|Adaeze Nwosu",
            "Billing & Premium",
            "program",
            "—",
            "invoice_statement",
            "UNRESOLVED",
            "44",
            "245",
            "Brush-off",
            "absent",
            "",
            "triggered false",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
        ],
        [
            "C-9003",
            "Tue 07 Jul 2026 09:02",
            "B1",
            "MEMBER",
            "CB-7700211",
            "Mateo Nkemdi",
            "AGT-13|Kayla Brennan",
            "Coverage & Benefits",
            "vision",
            "A-05",
            "agent_conversation",
            "PARTIALLY RESOLVED",
            "70",
            "192",
            "Competent but constrained",
            "present|CARRIER",
            "process_breakdown|HIGH|Operations",
            "triggered true|caller_request|requested_by_caller true|handled false",
            "",
            "",
            "market_test|verbatim, turn 16",
            "",
            "",
            "",
            "CARRIER",
            "Partly — communication",
            "coverage explanation",
            "none",
            "1 group",
        ],
        [
            "C-9004",
            "Wed 08 Jul 2026 11:30",
            "B1",
            "MEMBER",
            "CB-7700999",
            "Nobody Atall",
            "AGT-99|Ghost Agent",
            "Telepathy & Vibes",  # not a Category
            "dental",
            "A-01",
            "agent_conversation",
            "MOSTLY FINE",  # not an Outcome
            "50",
            "300",
            "Circular",
            "present",  # missing the target
            "just_a_code",  # missing severity and owner
            "triggered true|authority_limit",  # truncated
            "",
            "",
            "",
            "",
            "",
            "",
            "NOT_A_REAL_OWNER",  # not a RootCauseOwner
            "Sorta",  # not Yes/Partly/No
            "",
            "",
            "",
        ],
        [
            "C-9005",
            "Thu 06 Aug 2026 14:05",
            "B2a",
            "MEMBER",
            "CB-7700301",
            "Priya Osei",
            "AGT-07|Marcus Diallo",
            "Billing & Premium",
            "dental",
            "—",
            "invoice_statement",
            "RESOLVED",
            "78",
            "310",
            "Competent and resolved",
            "absent",
            "",
            "triggered false|none|requested_by_caller false|handled true — OVER-ESCALATION",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "billing dispute",
            "",
            "n_employees: 3",
        ],
    ]
}
