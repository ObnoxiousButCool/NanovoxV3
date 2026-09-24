"""Score the extraction pipeline against the answer key, and stop there.

Phase 5's harness. It loads every stored answer and every stored extraction,
applies E2's field map and E1's comparators, and returns a report.

**It resolves nothing and corrects nothing.** Same discipline as
`ImportAnswerKey`, which reports a disagreement between the tracker and the
PDF rather than preferring one: this reports a disagreement between the
pipeline and the answer key rather than adjusting either. Nothing here
tunes a prompt, retries a call, or decides what agreement is good enough —
plan §8 is explicit that which fields are good enough is decided with Minnie
once the numbers exist, and a harness that graded its own subject would be
the last place to notice it was wrong.

## This module reads the answers

It is therefore answer-key material and sits inside the import-linter
contract "Extraction cannot read the answer key" as a *forbidden* module.
`domain.evaluation` went in with E1; this use case goes in with E4. §6.3
calls label stripping the single most important safety property in the
system, and the harness is the first thing built that holds both sides at
once — the one object an extraction module must never be able to reach.

## What a missing extraction means

A call with an answer and no extraction is reported as unscored, not as a
field the pipeline got wrong. `MissingSide.PIPELINE` carries that through
every comparator, and `EvaluationReport.coverage` is what stops a run that
processed four calls from reading as a pipeline that agrees on everything.
"""

from __future__ import annotations

from dataclasses import dataclass

from application.ports.call_extraction_repository import CallExtractionRepository
from application.ports.diagnostics_source import Diagnostics, DiagnosticsSource
from application.ports.ground_truth_repository import GroundTruthRepository
from domain.evaluation.agreement import Agreement, LayerAgreement, agreement_for
from domain.evaluation.comparison import Comparison, SetComparison
from domain.evaluation.field_map import UNSCORED, Layer, Unscored, compare_call


@dataclass(frozen=True)
class EvaluationReport:
    """What the pipeline agreed with, and what nobody could tell."""

    #: Answer-key rows considered — the denominator for coverage.
    calls: int
    #: Calls that had an extraction to compare against.
    scored: int
    #: Calls with an answer and no pipeline output. Named, not counted,
    #: because the first question anyone asks is which ones.
    unscored_calls: tuple[str, ...]
    fields: tuple[Agreement, ...]
    layers: tuple[LayerAgreement, ...]
    #: Answer-key columns with no pipeline counterpart at all (E2).
    unscored_fields: tuple[Unscored, ...] = UNSCORED
    #: How much to trust the figures above: refused evidence, unresolved
    #: callers, and what the last run cost. `None` only when no diagnostics
    #: source was supplied.
    diagnostics: Diagnostics | None = None

    @property
    def coverage(self) -> float:
        """Calls with any pipeline output, over calls with an answer.

        Reported beside every agreement figure and never replaced by one. A
        pipeline that processed four of a hundred calls and got all four
        right is not a pipeline that agrees on everything.
        """
        return self.scored / self.calls if self.calls else 0.0

    @property
    def comparable(self) -> bool:
        """Whether anything could be compared at all.

        False is a distinct outcome rather than a bad score: it means the
        pipeline has not run, or ran and stored nothing, and no amount of
        reading the agreement numbers would tell anyone that.
        """
        return any(field.comparable for field in self.fields)

    @property
    def weakest_layer(self) -> LayerAgreement | None:
        """The layer to look at first, or `None` if nothing compared.

        Layers with nothing comparable are excluded rather than sorted to
        the bottom — an unanswered layer is not a badly performing one, and
        naming it as the thing to fix sends someone to the wrong prompt.
        """
        rated = [layer for layer in self.layers if layer.rate is not None]
        if not rated:
            return None
        return min(rated, key=lambda layer: (layer.rate or 0.0, layer.layer))


class EvaluateExtraction:
    """Compare stored pipeline output against the stored answer key."""

    def __init__(
        self,
        ground_truth: GroundTruthRepository,
        extractions: CallExtractionRepository,
        diagnostics: DiagnosticsSource | None = None,
    ) -> None:
        self._ground_truth = ground_truth
        self._extractions = extractions
        self._diagnostics = diagnostics

    async def execute(self) -> EvaluationReport:
        answers = await self._ground_truth.all()

        per_field: dict[str, list[Comparison | SetComparison]] = {}
        layer_of: dict[str, Layer] = {}
        unscored_calls: list[str] = []
        scored = 0

        for answer in answers:
            extraction = await self._extractions.get(answer.reference)
            if extraction is None:
                unscored_calls.append(answer.reference)
            else:
                scored += 1
            for mapped in compare_call(answer, extraction):
                per_field.setdefault(mapped.field, []).append(mapped.comparison)
                layer_of[mapped.field] = mapped.layer

        fields = tuple(agreement_for(name, comparisons) for name, comparisons in per_field.items())
        return EvaluationReport(
            calls=len(answers),
            scored=scored,
            unscored_calls=tuple(unscored_calls),
            fields=fields,
            layers=_by_layer(fields, layer_of),
            diagnostics=await self._diagnostics.read() if self._diagnostics else None,
        )


def _by_layer(
    fields: tuple[Agreement, ...], layer_of: dict[str, Layer]
) -> tuple[LayerAgreement, ...]:
    """Group the fields under the layer that produces them.

    In `Layer`'s own order rather than by agreement, because the layers run
    in that order and a reader tracing a weak L4 wants to see whether L2 was
    sound first.
    """
    grouped: dict[Layer, list[Agreement]] = {}
    for field in fields:
        grouped.setdefault(layer_of[field.field], []).append(field)
    return tuple(
        LayerAgreement(layer=layer.value, fields=tuple(grouped[layer]))
        for layer in Layer
        if layer in grouped
    )
