"""The insight service: what it accepts, and every way it refuses.

No live model — plan §2A.5. The provider is a double throughout, so these
tests state the contract rather than the weather.
"""

from __future__ import annotations

import pytest

from application.dto.insight_response import InsightItem, InsightsResponse
from application.use_cases.generate_insights import GenerateInsights, GenerateInsightsRequest
from domain.insights.facts import Fact, FactSet
from domain.insights.generated import (
    GeneratedInsights,
    InsightKind,
    InsightsStatus,
    Severity,
    UnavailableReason,
)
from domain.playbooks import PlaybookCatalogue
from infrastructure.config.paths import DEFAULT_CONFIG_DIR
from infrastructure.config.playbook_loader import load_playbooks
from infrastructure.llm.prompt_source import FilePromptSource
from infrastructure.llm.prompts import PromptLibrary
from tests.support.llm import FakeProvider, UnavailableProvider


@pytest.fixture(scope="module")
def catalogue() -> PlaybookCatalogue:
    return load_playbooks(DEFAULT_CONFIG_DIR / "playbooks.yaml")


@pytest.fixture
def service(catalogue: PlaybookCatalogue) -> GenerateInsights:
    """Wired to the real prompt file, so a missing placeholder fails here."""
    return GenerateInsights(prompts=FilePromptSource(PromptLibrary()), catalogue=catalogue)


def _facts() -> FactSet:
    return FactSet(
        subject="the executive scorecard",
        facts=(
            Fact(
                key="first_contact_resolution",
                label="First contact resolution",
                display="74%",
                n=112,
                basis="OBSERVED",
            ),
            Fact(
                key="intent_routed",
                label="Commercial intent routed",
                display=None,
                n=0,
                withheld_reason="NO_FIELD",
            ),
        ),
    )


def _item(**overrides: object) -> InsightItem:
    fields: dict[str, object] = {
        "key": "resolution_held",
        "sentence": "Resolution held at 74% across the period.",
        "kind": "INFERENCE",
        "severity": "READ_FIRST",
        "fact_keys": ["first_contact_resolution"],
        "issue_key": "none",
    }
    fields.update(overrides)
    return InsightItem.model_validate(fields)


def _answering(*items: InsightItem) -> FakeProvider:
    return FakeProvider(InsightsResponse(insights=list(items)))


async def _run(service: GenerateInsights, provider: object, *, limit: int = 4) -> GeneratedInsights:
    return await service.execute(
        GenerateInsightsRequest(facts=_facts(), limit=limit),
        provider,  # type: ignore[arg-type]
    )


class TestGenerating:
    async def test_a_clean_answer_becomes_a_generated_surface(
        self, service: GenerateInsights
    ) -> None:
        result = await _run(service, _answering(_item()))

        assert result.status is InsightsStatus.GENERATED
        assert len(result.insights) == 1
        assert result.insights[0].sentence == "Resolution held at 74% across the period."
        assert result.insights[0].kind is InsightKind.INFERENCE

    async def test_the_provider_and_model_are_recorded(self, service: GenerateInsights) -> None:
        """Provenance on screen: a reader can see who wrote it."""
        result = await _run(service, _answering(_item()))

        assert result.provider == "fake"
        assert result.model == "fake-model"

    async def test_a_recommendation_keeps_its_kind_on_the_wire(
        self, service: GenerateInsights
    ) -> None:
        """C3a: a suggestion must not be readable as a measurement."""
        result = await _run(service, _answering(_item(kind="RECOMMENDATION")))

        assert result.insights[0].kind is InsightKind.RECOMMENDATION

    async def test_reading_order_is_ours_not_the_models(self, service: GenerateInsights) -> None:
        provider = _answering(
            _item(key="c", severity="BACKGROUND"),
            _item(key="a", severity="READ_FIRST"),
            _item(key="b", severity="WORTH_READING"),
        )

        result = await _run(service, provider)

        assert [insight.severity for insight in result.insights] == [
            Severity.READ_FIRST,
            Severity.WORTH_READING,
            Severity.BACKGROUND,
        ]

    async def test_the_limit_is_applied_here_not_asked_of_the_model(
        self, service: GenerateInsights
    ) -> None:
        provider = _answering(
            _item(key="a"), _item(key="b"), _item(key="c"), _item(key="d"), _item(key="e")
        )

        result = await _run(service, provider, limit=2)

        assert len(result.insights) == 2

    async def test_a_withheld_figure_can_be_written_about(self, service: GenerateInsights) -> None:
        """Saying "we cannot yet say" is often the most useful sentence."""
        provider = _answering(
            _item(
                sentence="Whether commercial intent reached anyone is not yet measurable.",
                fact_keys=["intent_routed"],
            )
        )

        result = await _run(service, provider)

        assert result.status is InsightsStatus.GENERATED

    async def test_a_known_playbook_key_is_kept(self, service: GenerateInsights) -> None:
        result = await _run(service, _answering(_item(issue_key="unresolved")))

        assert result.insights[0].issue_key == "unresolved"

    async def test_an_invented_playbook_key_loses_the_link_not_the_sentence(
        self, service: GenerateInsights
    ) -> None:
        """A dead "what to do" link is worse than no link."""
        result = await _run(service, _answering(_item(issue_key="not_a_playbook")))

        assert result.status is InsightsStatus.GENERATED
        assert result.insights[0].issue_key is None


class TestRefusing:
    async def test_no_provider_is_an_explicit_unavailable_state(
        self, service: GenerateInsights
    ) -> None:
        """U2: never templated copy, never a silently hidden panel."""
        result = await _run(service, None)

        assert result.status is InsightsStatus.UNAVAILABLE
        assert result.reason is UnavailableReason.NO_PROVIDER
        assert result.insights == ()

    async def test_a_failing_provider_is_unavailable_not_an_error(
        self, service: GenerateInsights
    ) -> None:
        result = await _run(service, UnavailableProvider())

        assert result.reason is UnavailableReason.PROVIDER_FAILED

    async def test_a_number_no_fact_supports_rejects_the_whole_surface(
        self, service: GenerateInsights
    ) -> None:
        provider = _answering(_item(sentence="Resolution slipped to 71% this period."))

        result = await _run(service, provider)

        assert result.status is InsightsStatus.UNAVAILABLE
        assert result.reason is UnavailableReason.GUARDRAIL_REJECTED

    async def test_one_bad_sentence_costs_the_good_ones_too(
        self, service: GenerateInsights
    ) -> None:
        """Deliberate: a model that has just invented a figure is not
        trusted for the rest of its answer."""
        provider = _answering(
            _item(key="good"),
            _item(key="bad", sentence="A 48 point gap opened up."),
        )

        result = await _run(service, provider)

        assert result.reason is UnavailableReason.GUARDRAIL_REJECTED

    async def test_a_sentence_citing_no_figure_is_refused(self, service: GenerateInsights) -> None:
        provider = _answering(_item(fact_keys=["something_not_on_this_screen"]))

        result = await _run(service, provider)

        assert result.reason is UnavailableReason.GUARDRAIL_REJECTED

    async def test_an_empty_answer_is_not_dressed_up_as_generated(
        self, service: GenerateInsights
    ) -> None:
        result = await _run(service, _answering())

        assert result.status is InsightsStatus.UNAVAILABLE

    async def test_a_screen_with_every_figure_withheld_asks_no_model(
        self, service: GenerateInsights
    ) -> None:
        """No key would fix this, so it is its own reason — and it must not
        spend a model call to discover there was nothing to say."""
        provider = _answering(_item())
        withheld = FactSet(
            subject="the executive scorecard",
            facts=(
                Fact(
                    key="intent_routed",
                    label="Commercial intent routed",
                    display=None,
                    n=0,
                    withheld_reason="NO_FIELD",
                ),
            ),
        )

        result = await service.execute(GenerateInsightsRequest(facts=withheld), provider)

        assert result.reason is UnavailableReason.NO_PUBLISHED_FACTS
        assert provider.requests == []


class TestTheServiceCannotReachPastItsFacts:
    def test_it_takes_no_repository_corpus_or_session(self) -> None:
        """The §9 guardrail contract, asserted structurally.

        If someone later gives this service a reader "just to look one thing
        up", this test is what says no: the whole basis for trusting its
        output is that everything it saw is on the screen the reader is
        looking at.
        """
        import inspect

        parameters = set(inspect.signature(GenerateInsights.__init__).parameters)

        assert parameters == {"self", "prompts", "catalogue"}

    async def test_the_prompt_receives_only_facts(self, service: GenerateInsights) -> None:
        provider = _answering(_item())

        await _run(service, provider)

        sent = provider.requests[0].prompt
        assert "first_contact_resolution" in sent
        assert "74%" in sent
        # The withheld figure goes in with its reason and no number.
        assert "WITHHELD" in sent
        assert "NO_FIELD" in sent
