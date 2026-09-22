"""Provenance grade of a rule.

Rules — Program/Administration/Carrier sheets, column "Confidence". A rule
marked `UNVERIFIED` may only shape a question, never assert that an agent or
a document was wrong (Rules — Program sheet's own instruction) — insight 24
(rule provenance and confidence) exists to make this distinction visible,
not just enforced silently in the extraction prompts.

`VERIFIED_SECONDARY` is a third value actually present in the workbook (10
rows: Rules — Program P-27, Rules — Carrier C-22 through C-25, C-32,
C-34 through C-37), not documented in the plan's original two-value
description of this column — confirmed by reading every distinct value
across all three rule sheets rather than assuming VERIFIED/UNVERIFIED was
exhaustive.

**The workbook never defines this value in prose anywhere** — not in the
Rules sheets' own intro text, not in Corrections & Sources. There is no
sentence to quote. What's there instead is a consistent pattern in the
"Source" column: every `VERIFIED (SECONDARY)` row cites a member-facing
summary, an agent portal, or an employer-facing page ("VSP member
material", "Assurity Agent Center", "choicebuilder / mycalchoice employer
page") rather than the carrier's own primary plan document ("DeltaCare USA
EOC", "Program Guidelines") the way plain `VERIFIED` rows do. That reads as
"verified, but against a secondary source rather than the primary one" —
inferred from the data, not asserted by the workbook. Worth confirming with
Karim rather than treated as settled.

Rendering: Ranjit's `rules.html` already has three-way logic for this —
`confChip()` gives `VERIFIED (SECONDARY)` its own class (`is-secondary`,
label "secondary") distinct from `is-unverified`, and its own KPI row
(`CONF = ["VERIFIED", "VERIFIED (SECONDARY)", "UNVERIFIED"]`). But **no
`.conf` rule exists anywhere in `app.css`** — none of the three states has
an actual visual style (colour, shape) defined, not just this one. Phase 7's
epistemic chip system has to design the confidence chip from scratch, not
adapt an existing one. Flagged for Minnie; no chip style invented here.
"""

from __future__ import annotations

from enum import Enum


class RuleConfidence(str, Enum):
    VERIFIED = "VERIFIED"
    VERIFIED_SECONDARY = "VERIFIED (SECONDARY)"
    UNVERIFIED = "UNVERIFIED"
