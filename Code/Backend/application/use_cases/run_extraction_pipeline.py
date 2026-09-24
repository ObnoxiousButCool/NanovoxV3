"""The extraction pipeline — L1 -> L2 -> (L3 || L4) (plan §7, §8 Phase 4).

L1 has no use case of its own: it runs inside L2 itself (see
`frameworks_drivers/container.py`'s docstring), so this pipeline only
sequences three calls. L2 goes first, because L3 and L4 both need its
`category` and `product_lines` to scope which rules they're shown; L3
and L4 then run together, since neither reads anything the other
produces.

**Essential vs degradable** (`domain/layers.py`): every layer this
pipeline runs is, today, essential — `ESSENTIAL_LAYERS` names all four —
so a layer's failure fails the whole call. The distinction is still made
explicitly here, layer by layer, rather than assumed, so that a future
metric served by fewer layers doesn't need this file rewritten, only
`ESSENTIAL_LAYERS` re-scoped.

**Clinical risk suspension**, deferred from L3's own scoring (see
`domain/scoring/rubric.py`'s module docstring for why): L3 cannot see
L4's `escalation.trigger_type` at scoring time, because the two run
concurrently. Once both have finished, this pipeline checks L4's result
and, if it found `clinical_or_safety_risk`, moves L3's already-saved
score to `PROVISIONAL` — the score and tier are left untouched, only
their confidence status, matching the Call Quality Framework sheet's
"Withholding" step.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import TypeVar

from application.ports.call_extraction_repository import CallExtractionRepository
from application.ports.llm_provider import LLMProvider
from application.use_cases.classify_call_l2 import ClassifyCallL2, ClassifyCallL2Result
from application.use_cases.classify_call_l3 import ClassifyCallL3, ClassifyCallL3Result
from application.use_cases.classify_call_l4 import ClassifyCallL4, ClassifyCallL4Result
from domain.layers import ESSENTIAL_LAYERS, Layer
from domain.value_objects.escalation_trigger_type import EscalationTriggerType
from domain.value_objects.score import ScoreStatus
from domain.value_objects.token_usage import TokenUsage

T = TypeVar("T")


@dataclass(frozen=True)
class ExtractionPipelineResult:
    l2: ClassifyCallL2Result
    #: `None` only when L3 failed and L3 was not essential.
    l3: ClassifyCallL3Result | None
    #: `None` only when L4 failed and L4 was not essential.
    l4: ClassifyCallL4Result | None
    #: Layers whose failure did not fail the run because they weren't
    #: essential — empty while `ESSENTIAL_LAYERS` names every layer this
    #: pipeline runs.
    degraded: tuple[Layer, ...] = ()

    @property
    def usage(self) -> TokenUsage:
        """What this call cost across every layer that ran.

        A degraded layer contributes nothing because it produced nothing —
        which is a reported zero, not an unknown. A layer answered from the
        stage cache also contributes a reported zero, because it genuinely
        was free. The total is a floor only when some provider that did run
        declined to report its usage, and `TokenUsage.__add__` carries that
        through.
        """
        return TokenUsage.total(
            layer.usage for layer in (self.l2, self.l3, self.l4) if layer is not None
        )


class ExtractionPipeline:
    def __init__(
        self,
        *,
        l2: ClassifyCallL2,
        l3: ClassifyCallL3,
        l4: ClassifyCallL4,
        extractions: CallExtractionRepository,
        essential_layers: frozenset[Layer] = ESSENTIAL_LAYERS,
    ) -> None:
        self._l2 = l2
        self._l3 = l3
        self._l4 = l4
        self._extractions = extractions
        self._essential_layers = essential_layers

    async def execute(self, call_reference: str, provider: LLMProvider) -> ExtractionPipelineResult:
        l2_result = await self._l2.execute(call_reference, provider)

        (l3_result, l3_degraded), (l4_result, l4_degraded) = await asyncio.gather(
            self._run(Layer.L3, self._l3.execute(call_reference, provider)),
            self._run(Layer.L4, self._l4.execute(call_reference, provider)),
        )
        degraded = tuple(
            layer
            for layer, was_degraded in ((Layer.L3, l3_degraded), (Layer.L4, l4_degraded))
            if was_degraded
        )

        if l3_result is not None and l4_result is not None:
            await self._suspend_if_clinical_risk(call_reference, l3_result, l4_result)

        return ExtractionPipelineResult(l2=l2_result, l3=l3_result, l4=l4_result, degraded=degraded)

    async def _run(self, layer: Layer, coro: Coroutine[object, object, T]) -> tuple[T | None, bool]:
        try:
            return (await coro), False
        except Exception:
            if layer in self._essential_layers:
                raise
            return None, True

    async def _suspend_if_clinical_risk(
        self,
        call_reference: str,
        l3_result: ClassifyCallL3Result,
        l4_result: ClassifyCallL4Result,
    ) -> None:
        trigger = l4_result.findings.escalation_trigger_type
        if trigger is not EscalationTriggerType.CLINICAL_OR_SAFETY_RISK:
            return
        if l3_result.quality.score_result.status is ScoreStatus.PROVISIONAL:
            # Already withheld — every marker was rejected, most likely.
            return
        await self._extractions.mark_l3_provisional(call_reference)
