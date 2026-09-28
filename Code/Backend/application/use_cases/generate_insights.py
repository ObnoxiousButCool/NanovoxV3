"""Generate the one AI surface per screen (Revised plan §9, Phase 5).

## The service can only see facts

Its `execute` takes a `FactSet` and a provider. There is no repository, no
corpus reader and no session on it, so the guardrail contract — that the
service's only inputs are already-computed response figures — is a property
of the signature rather than a rule someone has to keep.
`domain/insights/facts.py` explains why those figures arrive flattened into
facts rather than as the response models themselves.

## Three ways to refuse, and no way to improvise

U2 (D14) rules out templated copy standing in for generated text, so every
failure ends the same way: an explicit unavailable surface carrying the
reason. Nothing here writes a sentence.

A model answer is taken **whole or not at all**. If one sentence states a
number no fact supports, the entire surface is rejected rather than that
sentence quietly dropped. Dropping would leave a screen that looks correct,
produced by a model that has just demonstrated it will invent a figure —
and it would hide the event from the people who need to fix the prompt. The
cost is real and is accepted: one bad sentence costs the reader three good
ones, and the screen says it could not say.

## Ordering is ours, not the model's

Severity comes back from the model; the *order* is applied here, stably, so
two runs over the same facts present the same reading order. A model asked
to also rank would be doing a job a sort already does.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from application.dto.insight_response import InsightItem, InsightsResponse
from application.ports.llm_provider import LLMProvider, LlmRequest
from application.ports.prompts import PromptSource
from domain.insights.facts import FactSet
from domain.insights.generated import (
    GeneratedInsights,
    Insight,
    InsightKind,
    Severity,
    UnavailableReason,
)
from domain.playbooks import PlaybookCatalogue

logger = logging.getLogger(__name__)

_PROMPT_ID = "insights"
_NO_ISSUE = "none"
_MAX_OUTPUT_TOKENS = 1200

#: Reading order. The model supplies the severity; this fixes the sort.
_ORDER = {Severity.READ_FIRST: 0, Severity.WORTH_READING: 1, Severity.BACKGROUND: 2}


@dataclass(frozen=True)
class GenerateInsightsRequest:
    facts: FactSet
    #: How many sentences the surface shows. The prototype's insight strip
    #: holds two to four cards; the feed shows more. Capped here rather than
    #: asked of the model, because a model told "at most four" will pad to
    #: four.
    limit: int = 4


class GenerateInsights:
    def __init__(self, *, prompts: PromptSource, catalogue: PlaybookCatalogue) -> None:
        self._prompts = prompts
        self._catalogue = catalogue

    async def execute(
        self, request: GenerateInsightsRequest, provider: LLMProvider | None
    ) -> GeneratedInsights:
        facts = request.facts

        if not facts.published:
            # Nothing on this screen carries a number, so there is nothing to
            # read. Distinct from a missing provider: no key would fix it.
            return GeneratedInsights.unavailable(UnavailableReason.NO_PUBLISHED_FACTS)

        if provider is None:
            return GeneratedInsights.unavailable(UnavailableReason.NO_PROVIDER)

        prompt = self._prompts.render(
            _PROMPT_ID,
            subject=facts.subject,
            facts=_render_facts(facts),
            issue_keys=_render_issue_keys(self._catalogue),
            limit=request.limit,
        )

        try:
            result = await provider.complete(
                LlmRequest(
                    prompt=prompt.text,
                    response_model=InsightsResponse,
                    prompt_id=prompt.id,
                    prompt_version=prompt.version,
                    max_output_tokens=_MAX_OUTPUT_TOKENS,
                )
            )
        except Exception:
            # Deliberately broad: every provider failure is the same fact to a
            # reader — there is no generated text and it is not their doing.
            # The traceback is logged because it is an operations problem.
            logger.exception("Insight generation failed", extra={"subject": facts.subject})
            return GeneratedInsights.unavailable(UnavailableReason.PROVIDER_FAILED)

        accepted = self._accept(list(result.value.insights), facts)
        if accepted is None:
            return GeneratedInsights.unavailable(UnavailableReason.GUARDRAIL_REJECTED)
        if not accepted:
            # A well-formed answer with nothing in it is still nothing to show,
            # and must not be dressed up as a generated surface.
            return GeneratedInsights.unavailable(UnavailableReason.NO_PUBLISHED_FACTS)

        ordered = sorted(accepted, key=lambda insight: (_ORDER[insight.severity], insight.key))
        return GeneratedInsights.generated(
            tuple(ordered[: request.limit]),
            provider=result.provider,
            model=result.model,
        )

    def _accept(self, items: list[InsightItem], facts: FactSet) -> list[Insight] | None:
        """Every item, or `None` if any one of them must be refused."""
        known = {fact.key for fact in facts.facts}
        accepted: list[Insight] = []

        for item in items:
            unsupported = facts.unsupported_numbers(item.sentence)
            if unsupported:
                logger.error(
                    "Insight rejected: stated a number no fact supports",
                    extra={
                        "subject": facts.subject,
                        "numbers": sorted(unsupported),
                        "prompt_id": _PROMPT_ID,
                    },
                )
                return None

            cited = tuple(key for key in item.fact_keys if key in known)
            if not cited:
                # A sentence that cites nothing on the screen cannot be checked
                # against the screen, which is the whole basis for trusting it.
                logger.error(
                    "Insight rejected: cited no figure on the screen",
                    extra={"subject": facts.subject, "cited": list(item.fact_keys)},
                )
                return None

            accepted.append(
                Insight(
                    key=item.key,
                    sentence=item.sentence.strip(),
                    kind=InsightKind(item.kind),
                    severity=Severity(item.severity),
                    fact_keys=cited,
                    issue_key=self._issue_key(item.issue_key),
                )
            )

        return accepted

    def _issue_key(self, key: str) -> str | None:
        """A playbook key that resolves, or nothing.

        An unrecognised key loses the link but keeps the sentence: a dead
        "What to do" link is a worse outcome than no link, and the sentence
        itself has already passed the check that matters.
        """
        if key == _NO_ISSUE or not key.strip():
            return None
        if self._catalogue.static(key) is None:
            logger.warning(
                "Insight named an unknown playbook key; link dropped",
                extra={"issue_key": key},
            )
            return None
        return key


def _render_facts(facts: FactSet) -> str:
    """The facts as the model sees them: labels, printed numbers, reasons."""
    lines = []
    for fact in facts.facts:
        if fact.published:
            basis = f", {fact.basis.lower()}" if fact.basis else ""
            lines.append(f"- {fact.key}: {fact.label} = {fact.display} (n={fact.n}{basis})")
        else:
            lines.append(
                f"- {fact.key}: {fact.label} = WITHHELD ({fact.withheld_reason}, n={fact.n})"
            )
    return "\n".join(lines)


def _render_issue_keys(catalogue: PlaybookCatalogue) -> str:
    return ", ".join(sorted(playbook.key for playbook in catalogue.playbooks))
