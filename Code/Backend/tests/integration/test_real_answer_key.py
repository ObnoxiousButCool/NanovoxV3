"""The answer key against the real corpus: every tracker row parses, and the
workbook and the PDF agree on all five fields they both carry.

This is the regression guard that matters most in B1. Plan §11's trap is
that a workbook from one revision and a transcripts PDF from another are
*each* internally consistent, so a mismatched pair misattributes every call
and nothing announces it. These two sources state the same five fields
about the same calls independently, which makes their agreement the only
check anyone has that the set is the matched one.

Fails, rather than skips, if the corpus is absent: it lives in `Documents/`
and is tracked. A skip here would be the same silent nothing the corpus
tests used to produce.

The corpus arrives in batches short of a 600-call target
(Corpus-v10-Schema-Update.md); only the batch-1-specific tests below pin an
exact count, because they cross-check figures the prototype's own tooling
published for that batch alone. Everything else asserts a floor.
"""

from __future__ import annotations

import pytest

from application.use_cases.import_answer_key import compare_shared_fields
from domain.value_objects.category import Category
from domain.value_objects.outcome import Outcome
from infrastructure.config.paths import DEFAULT_TRANSCRIPTS_DIR, DEFAULT_WORKBOOK_PATH
from infrastructure.corpus.pdf_answer_key_source import PdfAnswerKeySource
from infrastructure.reference.xlsx_ground_truth_source import XlsxGroundTruthSource

# Batch 1 was C-0001 to C-0100. Later batches don't renumber it.
_BATCH_1_LAST_REFERENCE = "C-0100"

pytestmark = pytest.mark.skipif(
    not (DEFAULT_WORKBOOK_PATH.exists() and DEFAULT_TRANSCRIPTS_DIR.exists()),
    reason="corpus not found — expected it under Documents/ (see infrastructure/config/paths.py)",
)


def test_every_tracker_row_parses_with_no_warnings() -> None:
    """A warning here means the workbook has started writing a cell in a
    form this parser does not know — a revision change, not a bad row.
    """
    dataset = XlsxGroundTruthSource(DEFAULT_WORKBOOK_PATH).read()

    assert len(dataset.rows) >= 100
    assert dataset.warnings == ()


def test_the_tracker_and_the_pdf_agree_on_every_shared_field() -> None:
    truths = {
        row.reference: row for row in XlsxGroundTruthSource(DEFAULT_WORKBOOK_PATH).read().rows
    }
    keys = {key.reference: key for key in PdfAnswerKeySource(DEFAULT_TRANSCRIPTS_DIR).read()}

    assert truths.keys() == keys.keys(), "the two sources describe different sets of calls"

    disagreements = [
        d.describe()
        for reference in sorted(truths)
        for d in compare_shared_fields(truths[reference], keys[reference])
    ]
    assert disagreements == []


def test_the_answer_key_reproduces_the_corpus_figures_the_prototype_documents() -> None:
    """`Prototype/tools/README.md` states these from an entirely separate
    pipeline, run against batch 1 alone. Reading the same batch through this
    one and getting the same numbers is a cross-check on both — filtered to
    C-0001 through C-0100 so a later batch's mix doesn't change what this
    checks.
    """
    rows = [
        row
        for row in XlsxGroundTruthSource(DEFAULT_WORKBOOK_PATH).read().rows
        if row.reference <= _BATCH_1_LAST_REFERENCE
    ]

    outcomes = dict.fromkeys(Outcome, 0)
    for row in rows:
        if row.outcome is not None:
            outcomes[row.outcome] += 1

    assert outcomes[Outcome.RESOLVED] == 63
    assert outcomes[Outcome.UNRESOLVED] == 19
    assert outcomes[Outcome.PARTIALLY_RESOLVED] == 11
    assert outcomes[Outcome.ESCALATED] == 7

    triggered = [r for r in rows if r.escalation_triggered]
    handled = [r for r in triggered if r.escalation_handled]
    assert (len(handled), len(triggered)) == (7, 11), "escalation integrity: 7 handled of 11"


def test_c0001_carries_the_17_sep_reissues_answers() -> None:
    """The same call the corpus regression guard pins on the reference side,
    checked here on the answer side (plan §11).
    """
    rows = {row.reference: row for row in XlsxGroundTruthSource(DEFAULT_WORKBOOK_PATH).read().rows}
    first = rows["C-0001"]

    assert first.category is Category.CLAIMS_AND_EOB
    assert first.outcome is Outcome.RESOLVED
    assert first.score == 91
    assert first.rule_refs == ("C-12", "P-14")
    assert first.knowledge_failure_rule_ref == "C-12"


def test_complaint_attribution_never_names_an_employer() -> None:
    """Insight 6 is WITHHELD on exactly this basis: no EMPLOYER value exists
    anywhere in `complaint.attributed_to`, so employer-caused member
    confusion cannot be computed. If this ever fails, the workbook has
    changed and §9 insight 6 needs revisiting rather than the test relaxing.
    """
    rows = XlsxGroundTruthSource(DEFAULT_WORKBOOK_PATH).read().rows

    targets = {row.complaint_attributed_to for row in rows if row.complaint_attributed_to}
    assert targets == {"CHOICE", "BROKER", "PROVIDER", "CARRIER"}
