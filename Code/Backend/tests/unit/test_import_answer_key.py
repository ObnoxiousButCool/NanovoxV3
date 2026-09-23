"""The answer-key import and its reconciliation, against fakes.

The behaviour worth pinning down is the cross-check: the tracker is what
gets stored, but a disagreement with the PDF is reported rather than
resolved, because at batch 1 it means the two files are different revisions
(plan §11) and silently preferring one source would hide exactly that.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from application.ports.answer_key_source import AnswerKeySource
from application.ports.ground_truth_repository import GroundTruthCounts, GroundTruthRepository
from application.ports.ground_truth_source import GroundTruthDataset, GroundTruthSource
from application.use_cases.import_answer_key import ImportAnswerKey
from domain.entities.answer_key import AnswerKey
from domain.entities.ground_truth import GroundTruth
from domain.value_objects.category import Category
from domain.value_objects.outcome import Outcome

TRUTH = GroundTruth(
    reference="C-0001",
    category=Category.CLAIMS_AND_EOB,
    archetype="Competent and resolved",
    rule_refs=("C-12", "P-14"),
    outcome=Outcome.RESOLVED,
    score=91,
)
KEY = AnswerKey(
    reference="C-0001",
    category="Claims & EOB",
    archetype="Competent and resolved",
    rule_refs=("C-12", "P-14"),
    outcome="RESOLVED",
    score=91,
    call_tags_text="CALL TAGS ...",
)


class FakeGroundTruthSource(GroundTruthSource):
    def __init__(self, dataset: GroundTruthDataset) -> None:
        self._dataset = dataset

    def read(self) -> GroundTruthDataset:
        return self._dataset


class FakeAnswerKeySource(AnswerKeySource):
    def __init__(self, keys: tuple[AnswerKey, ...]) -> None:
        self._keys = keys

    def read(self) -> tuple[AnswerKey, ...]:
        return self._keys


class FakeRepository(GroundTruthRepository):
    def __init__(self, unmatched: tuple[str, ...] = ()) -> None:
        self.saved: tuple[GroundTruth, ...] = ()
        self._unmatched = unmatched

    async def upsert(self, rows: tuple[GroundTruth, ...]) -> GroundTruthCounts:
        self.saved = rows
        return GroundTruthCounts(
            written=len(rows) - len(self._unmatched), unmatched=self._unmatched
        )


def _use_case(
    truths: tuple[GroundTruth, ...],
    keys: tuple[AnswerKey, ...],
    *,
    warnings: tuple[str, ...] = (),
    repository: FakeRepository | None = None,
) -> tuple[ImportAnswerKey, FakeRepository]:
    repo = repository or FakeRepository()
    return (
        ImportAnswerKey(
            source=FakeGroundTruthSource(GroundTruthDataset(rows=truths, warnings=warnings)),
            repository=repo,
            pdf_source=FakeAnswerKeySource(keys),
        ),
        repo,
    )


async def test_stores_the_tracker_rows() -> None:
    use_case, repo = _use_case((TRUTH,), (KEY,))

    result = await use_case.execute()

    assert repo.saved == (TRUTH,)
    assert result.counts.written == 1


async def test_agreeing_sources_reconcile() -> None:
    use_case, _ = _use_case((TRUTH,), (KEY,))

    result = await use_case.execute()

    assert result.disagreements == ()
    assert result.reconciled is True


@pytest.mark.parametrize(
    ("field", "tracker_change", "pdf_change"),
    [
        ("category", {"category": Category.BILLING_AND_PREMIUM}, {}),
        ("archetype", {"archetype": "Brush-off"}, {}),
        ("rule_refs", {"rule_refs": ("C-12",)}, {}),
        ("outcome", {"outcome": Outcome.UNRESOLVED}, {}),
        ("score", {"score": 44}, {}),
        ("score", {}, {"score": 44}),
    ],
)
async def test_reports_a_disagreement_on_any_shared_field(
    field: str, tracker_change: dict[str, object], pdf_change: dict[str, object]
) -> None:
    truth = replace(TRUTH, **tracker_change)  # type: ignore[arg-type]
    key = replace(KEY, **pdf_change)  # type: ignore[arg-type]
    use_case, _ = _use_case((truth,), (key,))

    result = await use_case.execute()

    assert [d.field for d in result.disagreements] == [field]
    assert result.reconciled is False


async def test_a_disagreement_is_reported_not_resolved() -> None:
    """The tracker still wins — it is what gets stored. The disagreement
    travels back beside it rather than changing what is written.
    """
    truth = replace(TRUTH, outcome=Outcome.UNRESOLVED)
    use_case, repo = _use_case((truth,), (KEY,))

    result = await use_case.execute()

    assert repo.saved == (truth,)
    assert result.disagreements[0].tracker == "UNRESOLVED"
    assert result.disagreements[0].pdf == "RESOLVED"


async def test_the_four_word_outcome_is_not_a_disagreement() -> None:
    """The PDF header spells it with a space and the enum with an
    underscore. Same value, two sheets of one workbook.
    """
    truth = replace(TRUTH, outcome=Outcome.PARTIALLY_RESOLVED)
    key = replace(KEY, outcome="PARTIALLY RESOLVED")
    use_case, _ = _use_case((truth,), (key,))

    assert (await use_case.execute()).disagreements == ()


async def test_no_cited_rules_in_both_sources_is_not_a_disagreement() -> None:
    truth = replace(TRUTH, rule_refs=())
    key = replace(KEY, rule_refs=())
    use_case, _ = _use_case((truth,), (key,))

    assert (await use_case.execute()).disagreements == ()


async def test_reports_calls_present_in_only_one_source() -> None:
    """A stronger signal than any single-field disagreement: the two files
    do not even describe the same calls.
    """
    only_tracker = replace(TRUTH, reference="C-0002")
    only_pdf = replace(KEY, reference="C-0003")
    use_case, _ = _use_case((TRUTH, only_tracker), (KEY, only_pdf))

    result = await use_case.execute()

    assert result.missing_from_pdf == ("C-0002",)
    assert result.missing_from_tracker == ("C-0003",)
    assert result.reconciled is False


async def test_only_shared_calls_are_compared() -> None:
    """A call missing from one side is reported as missing, not as five
    disagreements about empty fields.
    """
    use_case, _ = _use_case((TRUTH, replace(TRUTH, reference="C-0002")), (KEY,))

    assert (await use_case.execute()).disagreements == ()


async def test_source_warnings_travel_through_to_the_caller() -> None:
    use_case, _ = _use_case((TRUTH,), (KEY,), warnings=("C-0001: Signals value ...",))

    assert (await use_case.execute()).warnings == ("C-0001: Signals value ...",)


async def test_unmatched_calls_are_reported_and_block_reconciliation() -> None:
    repo = FakeRepository(unmatched=("C-0001",))
    use_case, _ = _use_case((TRUTH,), (KEY,), repository=repo)

    result = await use_case.execute()

    assert result.counts.unmatched == ("C-0001",)


async def test_a_disagreement_describes_itself_for_an_operator() -> None:
    truth = replace(TRUTH, score=44)
    use_case, _ = _use_case((truth,), (KEY,))

    result = await use_case.execute()

    assert result.disagreements[0].describe() == (
        "C-0001: score — tracker says '44', PDF says '91'"
    )
