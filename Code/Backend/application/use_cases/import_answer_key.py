"""Import the answer key, and reconcile the workbook against the PDF.

Plan §8 Phase 2: "`AnswerKeyImporter`: Transcript Tracker → `ground_truth`.
Cross-check against the PDF's stripped `CALL TAGS`; report any
disagreement."

Two sources state the same truth about the same 100 calls. The workbook's
Transcript Tracker carries twenty-four columns and is what gets stored; the
corpus PDF's header carries five of them and is what the transcript itself
shows. Five fields overlap — category, archetype, cited rules, outcome,
score — and that overlap is the whole point: it is the only independent
check anyone has that the workbook revision and the PDF revision are the
matched pair plan §11 insists on.

**The tracker wins, and disagreements are reported rather than resolved.**
The tracker is the answer key by §3.0's precedence (the workbook wins on
definitions), so it is what is written. But a disagreement is not a tie to
be broken — at batch 1 it means the two files are different revisions, which
is §11's known trap: both pairings are internally consistent, so nothing
else announces it. Silently preferring one source would hide exactly the
condition this cross-check exists to surface.

Answer-key material. No extraction code may import this module, per the
import-linter contract "Extraction cannot read the answer key".
"""

from __future__ import annotations

from dataclasses import dataclass

from application.ports.answer_key_source import AnswerKeySource
from application.ports.ground_truth_repository import GroundTruthCounts, GroundTruthRepository
from application.ports.ground_truth_source import GroundTruthSource
from domain.entities.answer_key import AnswerKey
from domain.entities.ground_truth import GroundTruth


@dataclass(frozen=True)
class Disagreement:
    """One field, for one call, where the two sources do not agree."""

    reference: str
    field: str
    tracker: str
    pdf: str

    def describe(self) -> str:
        return (
            f"{self.reference}: {self.field} — tracker says {self.tracker!r}, PDF says {self.pdf!r}"
        )


@dataclass(frozen=True)
class AnswerKeyImportResult:
    counts: GroundTruthCounts
    warnings: tuple[str, ...]
    disagreements: tuple[Disagreement, ...]
    #: Calls the PDF has and the tracker does not, and the reverse. A
    #: non-empty pair here is a stronger signal than any single-field
    #: disagreement: the two files do not even describe the same calls.
    missing_from_tracker: tuple[str, ...]
    missing_from_pdf: tuple[str, ...]

    @property
    def reconciled(self) -> bool:
        return not (self.disagreements or self.missing_from_tracker or self.missing_from_pdf)


def _rules(refs: tuple[str, ...]) -> str:
    return ", ".join(refs) if refs else "—"


def compare_shared_fields(truth: GroundTruth, key: AnswerKey) -> list[Disagreement]:
    """The five fields both sources carry.

    Outcome is compared on the enum's value, which is why the tracker's
    "PARTIALLY RESOLVED" and the PDF's are both normalised before they get
    here — a spelling difference between two sheets of the same workbook is
    not a disagreement about a call.

    Cited rules are compared as an ordered join rather than as a set: the
    two sources list them in the same order when they agree, and a
    difference in order is itself worth seeing rather than normalising away.
    """
    found: list[Disagreement] = []

    def check(field: str, tracker: str, pdf: str) -> None:
        if tracker != pdf:
            found.append(
                Disagreement(reference=truth.reference, field=field, tracker=tracker, pdf=pdf)
            )

    check("category", truth.category.value if truth.category else "", key.category)
    check("archetype", truth.archetype, key.archetype)
    check("rule_refs", _rules(truth.rule_refs), _rules(key.rule_refs))
    check("outcome", truth.outcome.value if truth.outcome else "", _normalise(key.outcome))
    check(
        "score",
        "" if truth.score is None else str(truth.score),
        "" if key.score is None else str(key.score),
    )
    return found


def _normalise(outcome: str) -> str:
    """The PDF header spells the four-word outcome with a space, as the
    tracker does; the enum uses an underscore. Same normalisation, applied
    on the PDF side, so the comparison is enum value against enum value.
    """
    return outcome.replace(" ", "_")


class ImportAnswerKey:
    """Reads the tracker, stores it, and reconciles it against the PDF."""

    def __init__(
        self,
        source: GroundTruthSource,
        repository: GroundTruthRepository,
        pdf_source: AnswerKeySource,
    ) -> None:
        self._source = source
        self._repository = repository
        self._pdf_source = pdf_source

    async def execute(self) -> AnswerKeyImportResult:
        dataset = self._source.read()
        keys = {key.reference: key for key in self._pdf_source.read()}
        truths = {truth.reference: truth for truth in dataset.rows}

        disagreements: list[Disagreement] = []
        for reference in sorted(truths.keys() & keys.keys()):
            disagreements.extend(compare_shared_fields(truths[reference], keys[reference]))

        counts = await self._repository.upsert(dataset.rows)
        return AnswerKeyImportResult(
            counts=counts,
            warnings=dataset.warnings,
            disagreements=tuple(disagreements),
            missing_from_tracker=tuple(sorted(keys.keys() - truths.keys())),
            missing_from_pdf=tuple(sorted(truths.keys() - keys.keys())),
        )
