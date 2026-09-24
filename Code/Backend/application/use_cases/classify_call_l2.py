"""L2 — classification (plan §7, §8 Phase 4).

Runs L1 first (deterministic, cheap), then asks a model for outcome,
category, product lines, complaint, intent, the caller/detection half of
escalation, a broker mention and a first-pass touchpoint. The model's
answer is never trusted as-is: intent quotes are checked against the
transcript the same way every other layer's evidence is (plan §7), and a
broker mention is checked against the employer's actual broker of record
— a mismatch is itself a finding (Call Tag Schema field 14), computed here
rather than asked of the model.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from application.dto.l2_response import L2Response
from application.ports.call_extraction_repository import (
    CallExtractionRepository,
    L2Provenance,
    L2Save,
)
from application.ports.call_repository import CallRepository
from application.ports.clock import Clock
from application.ports.llm_provider import LLMProvider, LlmRequest
from application.ports.prompts import PromptSource
from application.ports.reference_lookup import ReferenceLookup
from application.ports.stage_cache import StageCache, StageCacheKey
from domain.entities.employer import Employer
from domain.entities.l2_classification import L2Classification
from domain.entities.transcript import Transcript
from domain.errors import ValidationError
from domain.extraction.evidence import EvidenceValidation, validate_evidence
from domain.extraction.l1_deterministic import run_l1
from domain.layers import Layer
from domain.transcript_hash import content_hash
from domain.value_objects.broker_named_aloud import BrokerNamedAloud
from domain.value_objects.broker_sentiment import BrokerSentiment
from domain.value_objects.category import Category
from domain.value_objects.complaint import Complaint
from domain.value_objects.complaint_attribution import ComplaintAttribution
from domain.value_objects.intent_statement import IntentStatement
from domain.value_objects.intent_type import IntentType
from domain.value_objects.outcome import Outcome
from domain.value_objects.product_line import ProductLine
from domain.value_objects.token_usage import TokenUsage

_PROMPT_ID = "l2_classification"


@dataclass(frozen=True)
class ClassifyCallL2Result:
    classification: L2Classification
    #: Intent statements the model cited that didn't survive checking
    #: against the transcript — kept for Diagnostics (plan §8 Phase 5),
    #: never silently discarded.
    rejected_intent: EvidenceValidation[IntentStatement]
    #: Tokens this layer consumed. A reported zero where the stage cache
    #: answered — genuinely free, not unknown. See `TokenUsage`.
    usage: TokenUsage = field(default_factory=TokenUsage)


class ClassifyCallL2:
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

    async def execute(self, call_reference: str, provider: LLMProvider) -> ClassifyCallL2Result:
        call = await self._calls.get(call_reference)
        if call is None:
            raise ValidationError(f"There is no ingested call {call_reference!r} to classify.")
        transcript = call.transcript
        if transcript is None:
            raise ValidationError(
                f"Call {call_reference!r} has no usable transcript.",
                detail=f"resolution_status={call.resolution_status.value}",
            )

        known_brokers = await self._reference_lookup.list_brokers()
        l1 = run_l1(transcript, known_brokers)

        rendered = self._prompts.render(_PROMPT_ID, transcript=_render_transcript(transcript))
        key = StageCacheKey(
            transcript_hash=content_hash(transcript),
            layer=Layer.L2,
            prompt_version=rendered.version,
            model=provider.model,
        )

        usage = TokenUsage()
        cached = await self._stage_cache.get(key)
        if cached is not None:
            response = L2Response.model_validate_json(cached)
        else:
            result = await provider.complete(
                LlmRequest(
                    prompt=rendered.text,
                    response_model=L2Response,
                    prompt_id=rendered.id,
                    prompt_version=rendered.version,
                )
            )
            response = result.value
            usage = result.usage
            await self._stage_cache.put(key, response.model_dump_json())

        employer = await self._resolve_employer(call.employer_ref)
        classification, rejected_intent = _to_domain(
            response,
            transcript=transcript,
            known_broker_refs=frozenset(broker.reference for broker in known_brokers),
            employer_broker_ref=employer.broker_ref if employer is not None else None,
            l1_broker_candidates=frozenset(m.broker_ref for m in l1.broker_mentions),
        )

        await self._extractions.save_l2(
            call_reference,
            L2Save(
                outcome=classification.outcome,
                category=classification.category,
                product_lines=classification.product_lines,
                complaint=classification.complaint,
                intent=classification.intent,
                escalation_triggered=classification.escalation_triggered,
                escalation_requested_by_caller=classification.escalation_requested_by_caller,
                broker_named_aloud=classification.broker_named_aloud,
                touchpoint=classification.touchpoint,
                summary=classification.summary,
                provenance=L2Provenance(
                    provider=provider.name,
                    model=provider.model,
                    prompt_version=rendered.version,
                    completed_at=self._clock.now(),
                ),
            ),
        )

        return ClassifyCallL2Result(
            classification=classification,
            rejected_intent=rejected_intent,
            usage=usage,
        )

    async def _resolve_employer(self, employer_ref: str | None) -> Employer | None:
        if employer_ref is None:
            return None
        return await self._reference_lookup.find_employer(employer_ref)


def _render_transcript(transcript: Transcript) -> str:
    return "\n".join(
        f"[{index}] {turn.role.value}: {turn.text}" for index, turn in enumerate(transcript.turns)
    )


def _to_domain(
    response: L2Response,
    *,
    transcript: Transcript,
    known_broker_refs: frozenset[str],
    employer_broker_ref: str | None,
    l1_broker_candidates: frozenset[str],
) -> tuple[L2Classification, EvidenceValidation[IntentStatement]]:
    intent_candidates = tuple(
        IntentStatement(type=IntentType(item.type), quote=item.quote, turn_seq=item.turn_seq)
        for item in response.intent
    )
    intent_validation = validate_evidence(intent_candidates, transcript)

    complaint = _validate_complaint(response)

    broker_named_aloud = _validate_broker_mention(
        response,
        known_broker_refs=known_broker_refs,
        employer_broker_ref=employer_broker_ref,
        l1_broker_candidates=l1_broker_candidates,
    )

    classification = L2Classification(
        outcome=Outcome(response.outcome),
        category=Category(response.category),
        product_lines=tuple(ProductLine(line) for line in response.product_lines),
        complaint=complaint,
        intent=intent_validation.accepted,
        escalation_triggered=response.escalation_triggered,
        escalation_requested_by_caller=response.escalation_requested_by_caller,
        broker_named_aloud=broker_named_aloud,
        touchpoint=response.touchpoint or None,
        summary=response.summary,
    )
    return classification, intent_validation


def _validate_complaint(response: L2Response) -> Complaint:
    if not response.complaint.present or response.complaint.attributed_to == "NONE":
        # An internally inconsistent answer — present but no real
        # attribution — is treated as no complaint, never guessed past.
        return Complaint(present=False)
    return Complaint(
        present=True,
        attributed_to=ComplaintAttribution(response.complaint.attributed_to),
    )


def _validate_broker_mention(
    response: L2Response,
    *,
    known_broker_refs: frozenset[str],
    employer_broker_ref: str | None,
    l1_broker_candidates: frozenset[str],
) -> BrokerNamedAloud:
    """Never trust the model's `broker_ref` alone.

    A broker mention is only accepted when it names a broker that
    genuinely exists in the reference data — and, more conservatively,
    only one L1 independently spotted by pattern-matching the caller's
    own words. A model claiming a broker mention that L1 never found is
    treated the same way an unfindable quote is treated everywhere else
    in this pipeline: rejected, never guessed past.
    """
    mention = response.broker_named_aloud
    if not mention.present or mention.sentiment == "NONE":
        # The second condition is a model that said `present` but not a
        # real sentiment — an internally inconsistent answer, treated the
        # same as no mention rather than guessed past.
        return BrokerNamedAloud(present=False)

    broker_ref = mention.broker_ref
    if broker_ref not in known_broker_refs or broker_ref not in l1_broker_candidates:
        return BrokerNamedAloud(present=False)

    return BrokerNamedAloud(
        present=True,
        broker_ref=broker_ref,
        sentiment=BrokerSentiment(mention.sentiment),
        matches_employer_of_record=(
            broker_ref == employer_broker_ref if employer_broker_ref is not None else None
        ),
    )
