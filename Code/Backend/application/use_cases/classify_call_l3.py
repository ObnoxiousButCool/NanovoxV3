"""L3 — quality & knowledge (plan §7, §8 Phase 4).

Runs after L2: needs its `category` and `product_lines` to scope which
rules the model is shown (plan §7, "never all 122"). Markers are checked
against the transcript exactly like L2's intent statements
(`domain.extraction.evidence.validate_evidence`); a cited rule id is
checked against the scoped rule set, the same way an L2 broker mention is
checked against the reference data — a rule id the model invents is
rejected, never guessed past. The rubric turns accepted markers into a
score; the rubric itself never sees the model's output directly (Call
Quality Framework sheet: "The score is not written by the model").
"""

from __future__ import annotations

from dataclasses import dataclass

from application.dto.l3_response import L3Response
from application.ports.call_extraction_repository import (
    CallExtractionRepository,
    L3Provenance,
    L3Save,
    RaisedMarker,
)
from application.ports.call_repository import CallRepository
from application.ports.clock import Clock
from application.ports.llm_provider import LLMProvider, LlmRequest
from application.ports.prompts import PromptSource
from application.ports.reference_lookup import ReferenceLookup
from application.ports.stage_cache import StageCache, StageCacheKey
from domain.entities.l3_quality import L3Quality
from domain.entities.rule import Rule
from domain.entities.score_marker import ScoreMarker
from domain.entities.transcript import Transcript
from domain.errors import ValidationError
from domain.extraction.evidence import EvidenceValidation, validate_evidence
from domain.extraction.rule_scoping import scope_rules
from domain.layers import Layer
from domain.scoring.rubric import Rubric
from domain.scoring.rubric_engine import RubricEngine
from domain.transcript_hash import content_hash
from domain.value_objects.knowledge_failure import KnowledgeFailure
from domain.value_objects.polarity import Polarity

_PROMPT_ID = "l3_quality"
_ACCEPTED = "accepted"


@dataclass(frozen=True)
class ClassifyCallL3Result:
    quality: L3Quality
    rejected_markers: EvidenceValidation[ScoreMarker]


class ClassifyCallL3:
    def __init__(
        self,
        *,
        calls: CallRepository,
        reference_lookup: ReferenceLookup,
        prompts: PromptSource,
        stage_cache: StageCache,
        extractions: CallExtractionRepository,
        rubric: Rubric,
        clock: Clock,
    ) -> None:
        self._calls = calls
        self._reference_lookup = reference_lookup
        self._prompts = prompts
        self._stage_cache = stage_cache
        self._extractions = extractions
        self._engine = RubricEngine(rubric)
        self._clock = clock

    async def execute(self, call_reference: str, provider: LLMProvider) -> ClassifyCallL3Result:
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
            # category is always set together with everything else L2
            # writes (application.use_cases.classify_call_l2), so its
            # absence alone means L2 hasn't run for this call yet.
            raise ValidationError(
                f"Call {call_reference!r} has no L2 classification yet.",
                detail="L3 needs L2's category and product lines to scope which rules to show.",
            )

        all_rules = await self._reference_lookup.list_rules()
        scoped_rules = scope_rules(all_rules, l2.product_lines)

        rendered = self._prompts.render(
            _PROMPT_ID,
            transcript=_render_transcript(transcript),
            rules=_render_rules(scoped_rules),
        )
        key = StageCacheKey(
            transcript_hash=content_hash(transcript),
            layer=Layer.L3,
            prompt_version=rendered.version,
            model=provider.model,
        )

        cached = await self._stage_cache.get(key)
        if cached is not None:
            response = L3Response.model_validate_json(cached)
        else:
            result = await provider.complete(
                LlmRequest(
                    prompt=rendered.text,
                    response_model=L3Response,
                    prompt_id=rendered.id,
                    prompt_version=rendered.version,
                )
            )
            response = result.value
            await self._stage_cache.put(key, response.model_dump_json())

        marker_candidates = tuple(
            ScoreMarker(
                polarity=Polarity(item.polarity),
                dimension=item.dimension,
                description=item.description,
                quote=item.quote,
                turn_seq=item.turn_seq,
            )
            for item in response.markers
        )
        marker_validation = validate_evidence(marker_candidates, transcript)

        known_rule_ids = frozenset(rule.reference for rule in scoped_rules)
        knowledge_failure = _validate_knowledge_failure(response, known_rule_ids)

        score_result = self._engine.score(
            list(marker_validation.accepted),
            evidence_all_rejected=marker_validation.all_rejected,
        )
        quality = L3Quality(
            score_result=score_result,
            markers=marker_validation.accepted,
            knowledge_failure=knowledge_failure,
        )

        raised_markers = tuple(
            RaisedMarker(marker=marker, verification_status=_ACCEPTED)
            for marker in marker_validation.accepted
        ) + tuple(
            RaisedMarker(marker=rejected.item, verification_status=rejected.reason.value)
            for rejected in marker_validation.rejected
        )

        await self._extractions.save_l3(
            call_reference,
            L3Save(
                score_result=score_result,
                markers=raised_markers,
                knowledge_failure=knowledge_failure,
                provenance=L3Provenance(
                    provider=provider.name,
                    model=provider.model,
                    prompt_version=rendered.version,
                    rubric_version=self._engine.rubric.version,
                    completed_at=self._clock.now(),
                ),
            ),
        )

        return ClassifyCallL3Result(quality=quality, rejected_markers=marker_validation)


def _render_transcript(transcript: Transcript) -> str:
    return "\n".join(
        f"[{index}] {turn.role.value}: {turn.text}" for index, turn in enumerate(transcript.turns)
    )


def _render_rules(rules: tuple[Rule, ...]) -> str:
    if not rules:
        return "(no rules apply to this call's product lines)"
    return "\n".join(f"{rule.reference}: {rule.text}" for rule in rules)


def _validate_knowledge_failure(
    response: L3Response, known_rule_ids: frozenset[str]
) -> KnowledgeFailure:
    failure = response.knowledge_failure
    if not failure.present or not failure.correct_statement.strip():
        return KnowledgeFailure(present=False)

    if failure.rule_id not in known_rule_ids:
        # The model cited a rule outside what it was shown, or invented
        # one — rejected the same way an unfindable quote is, never
        # guessed past.
        return KnowledgeFailure(present=False)

    return KnowledgeFailure(
        present=True,
        rule_id=failure.rule_id,
        correct_statement=failure.correct_statement,
    )
