"""L4 — signals & gaps (plan §7, §8 Phase 4).

Runs after L2, like L3, and reads L2's classification for the same two
reasons: `category`/`product_lines` scope which rules are shown, and
`escalation_triggered` gates whether L4 is even asked to classify a
trigger type — a model asked to name one on a call L2 found no trigger on
would have to invent something, so the question is never put to it.
Signals are evidence-checked the same way every other layer's citations
are (plan §7).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from application.dto.l4_response import L4Response
from application.ports.call_extraction_repository import (
    CallExtractionRepository,
    L4Provenance,
    L4Save,
)
from application.ports.call_repository import CallRepository
from application.ports.clock import Clock
from application.ports.llm_provider import LLMProvider, LlmRequest
from application.ports.prompts import PromptSource
from application.ports.reference_lookup import ReferenceLookup
from application.ports.stage_cache import StageCache, StageCacheKey
from domain.derivations.root_cause import preventable_of, root_cause_owner
from domain.entities.l4_signals_and_gaps import L4SignalsAndGaps
from domain.entities.rule import Rule
from domain.entities.transcript import Transcript
from domain.errors import ValidationError
from domain.extraction.evidence import EvidenceValidation, validate_evidence
from domain.extraction.rule_scoping import scope_rules
from domain.layers import Layer
from domain.transcript_hash import content_hash
from domain.value_objects.complaint import Complaint
from domain.value_objects.escalation_trigger_type import EscalationTriggerType
from domain.value_objects.process_gap import ProcessGap, ProcessGapStatus, RaisedBy
from domain.value_objects.signal import Signal
from domain.value_objects.signal_type import SignalType
from domain.value_objects.token_usage import TokenUsage

_PROMPT_ID = "l4_signals"


@dataclass(frozen=True)
class ClassifyCallL4Result:
    findings: L4SignalsAndGaps
    rejected_signals: EvidenceValidation[Signal]
    #: Tokens this layer consumed. A reported zero where the stage cache
    #: answered — genuinely free, not unknown. See `TokenUsage`.
    usage: TokenUsage = field(default_factory=TokenUsage)


class ClassifyCallL4:
    def __init__(
        self,
        *,
        calls: CallRepository,
        reference_lookup: ReferenceLookup,
        prompts: PromptSource,
        stage_cache: StageCache,
        extractions: CallExtractionRepository,
        clock: Clock,
    ) -> None:
        self._calls = calls
        self._reference_lookup = reference_lookup
        self._prompts = prompts
        self._stage_cache = stage_cache
        self._extractions = extractions
        self._clock = clock

    async def execute(self, call_reference: str, provider: LLMProvider) -> ClassifyCallL4Result:
        call = await self._calls.get(call_reference)
        if call is None:
            raise ValidationError(f"There is no ingested call {call_reference!r} to classify.")
        transcript = call.transcript
        if transcript is None:
            raise ValidationError(
                f"Call {call_reference!r} has no usable transcript.",
                detail=f"resolution_status={call.resolution_status.value}",
            )

        l2 = await self._extractions.get(call_reference)
        if l2 is None or l2.category is None:
            raise ValidationError(
                f"Call {call_reference!r} has no L2 classification yet.",
                detail="L4 needs L2's category, product lines and escalation fields.",
            )

        all_rules = await self._reference_lookup.list_rules()
        scoped_rules = scope_rules(all_rules, l2.product_lines)

        rendered = self._prompts.render(
            _PROMPT_ID,
            transcript=_render_transcript(transcript),
            rules=_render_rules(scoped_rules),
            escalation_triggered=str(bool(l2.escalation_triggered)),
            escalation_requested_by_caller=str(bool(l2.escalation_requested_by_caller)),
            l2_touchpoint=l2.touchpoint or "",
        )
        key = StageCacheKey(
            transcript_hash=content_hash(transcript),
            layer=Layer.L4,
            prompt_version=rendered.version,
            model=provider.model,
        )

        usage = TokenUsage()
        cached = await self._stage_cache.get(key)
        if cached is not None:
            response = L4Response.model_validate_json(cached)
        else:
            result = await provider.complete(
                LlmRequest(
                    prompt=rendered.text,
                    response_model=L4Response,
                    prompt_id=rendered.id,
                    prompt_version=rendered.version,
                )
            )
            response = result.value
            usage = result.usage
            await self._stage_cache.put(key, response.model_dump_json())

        signal_candidates = tuple(
            Signal(type=SignalType(item.type), quote=item.quote, turn_seq=item.turn_seq)
            for item in response.signals
        )
        signal_validation = validate_evidence(signal_candidates, transcript)

        # L2 alone decides whether a trigger exists at all; L4 only
        # classifies which one, and only when L2 says one fired. A model
        # answering a trigger type on a call L2 found untriggered is
        # disagreeing with L2, not adding information — the two layers
        # never reconcile with each other (plan §7: they run concurrently).
        escalation_trigger_type = (
            EscalationTriggerType(response.escalation_trigger_type)
            if l2.escalation_triggered and response.escalation_trigger_type != "NONE"
            else None
        )

        # `handled` is gated on the same verdict, for the same reason. It is
        # not a property of the call; it is a property of an escalation, and
        # on a call that never escalated the question has no subject. Asked
        # anyway, a model answers "yes" — nothing went wrong — and the answer
        # stores as "never triggered, but handled", which `Escalation`
        # refuses to construct and which took every insights endpoint down
        # with a 500 once real extractions existed.
        #
        # Escalation integrity divides handled by *warranted*, so a false
        # here cannot flatter the metric: these calls are in neither half.
        # `bool(...)` because L2's verdict is tri-state: an unset one means
        # nobody has decided whether this call escalated, and a `handled`
        # of true under that is the same unanswerable claim as under false.
        escalation_handled = bool(l2.escalation_triggered and response.escalation_handled)

        process_gap = _validate_process_gap(response)

        findings = L4SignalsAndGaps(
            signals=signal_validation.accepted,
            escalation_handled=escalation_handled,
            escalation_trigger_type=escalation_trigger_type,
            process_gap=process_gap,
            touchpoint=response.touchpoint or None,
        )

        # Call Tag Schema fields 17-18 (v10) — computed, not extracted, from
        # L2's own complaint and this pass's own signals (see
        # `domain/derivations/root_cause.py`). L2 always saves a complaint
        # once it has run at all, so the fallback below only guards mypy's
        # narrowing, not a real gap.
        complaint = l2.complaint if l2.complaint is not None else Complaint(present=False)
        owner = root_cause_owner(complaint, findings.signals)
        preventable = preventable_of(owner)

        await self._extractions.save_l4(
            call_reference,
            L4Save(
                signals=findings.signals,
                escalation_handled=findings.escalation_handled,
                escalation_trigger_type=findings.escalation_trigger_type,
                process_gap=findings.process_gap,
                touchpoint=findings.touchpoint,
                root_cause_owner=owner,
                preventable=preventable,
                provenance=L4Provenance(
                    provider=provider.name,
                    model=provider.model,
                    prompt_version=rendered.version,
                    completed_at=self._clock.now(),
                ),
            ),
        )

        return ClassifyCallL4Result(
            findings=findings,
            rejected_signals=signal_validation,
            usage=usage,
        )


def _render_transcript(transcript: Transcript) -> str:
    return "\n".join(
        f"[{index}] {turn.role.value}: {turn.text}" for index, turn in enumerate(transcript.turns)
    )


def _render_rules(rules: tuple[Rule, ...]) -> str:
    if not rules:
        return "(no rules apply to this call's product lines)"
    return "\n".join(f"{rule.reference}: {rule.text}" for rule in rules)


def _validate_process_gap(response: L4Response) -> ProcessGap:
    gap = response.process_gap
    if (
        not gap.present
        or gap.raised_by == "NONE"
        or gap.status == "NONE"
        or not gap.gap_type.strip()
        or not gap.proposed_change.strip()
    ):
        # An internally inconsistent answer — present but missing one of
        # its required fields — is treated as no gap, never guessed past.
        return ProcessGap(present=False)

    return ProcessGap(
        present=True,
        gap_type=gap.gap_type,
        touchpoint=gap.touchpoint or None,
        proposed_change=gap.proposed_change,
        raised_by=RaisedBy(gap.raised_by),
        status=ProcessGapStatus(gap.status),
    )
