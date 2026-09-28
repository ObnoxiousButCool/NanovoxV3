"""The insight cache, and what it refuses to remember.

Every model call is billed, so the assertions that matter are about how
many calls happen — not that a dictionary stores things.
"""

from __future__ import annotations

import pytest

from application.ports.insight_cache import InsightCacheKey
from application.use_cases.generate_insights import GenerateInsights, GenerateInsightsRequest
from domain.insights.facts import Fact, FactSet
from domain.insights.generated import GeneratedInsights, InsightsStatus, UnavailableReason
from domain.playbooks import PlaybookCatalogue
from infrastructure.cache.insight_cache import InMemoryInsightCache
from infrastructure.config.paths import DEFAULT_CONFIG_DIR
from infrastructure.config.playbook_loader import load_playbooks
from infrastructure.llm.prompt_source import FilePromptSource
from infrastructure.llm.prompts import PromptLibrary
from tests.support.llm import FakeProvider, UnavailableProvider
from tests.unit.test_generate_insights import _answering, _facts, _item


@pytest.fixture(scope="module")
def catalogue() -> PlaybookCatalogue:
    return load_playbooks(DEFAULT_CONFIG_DIR / "playbooks.yaml")


def _key(**overrides: object) -> InsightCacheKey:
    fields: dict[str, object] = {
        "facts_digest": "abc",
        "prompt_version": "1.0.0",
        "provider": "fake",
        "model": "fake-model",
        "limit": 4,
    }
    fields.update(overrides)
    return InsightCacheKey(**fields)  # type: ignore[arg-type]


class TestTheStore:
    async def test_a_miss_is_none_not_an_error(self) -> None:
        assert await InMemoryInsightCache().get(_key()) is None

    async def test_what_went_in_comes_back(self) -> None:
        cache = InMemoryInsightCache()
        value = GeneratedInsights.unavailable(UnavailableReason.NO_PROVIDER)

        await cache.put(_key(), value)

        assert await cache.get(_key()) is value

    @pytest.mark.parametrize(
        "difference",
        [
            {"facts_digest": "different"},
            {"prompt_version": "1.0.1"},
            {"provider": "other"},
            {"model": "other-model"},
            {"limit": 2},
        ],
        ids=["figures", "prompt", "provider", "model", "limit"],
    )
    async def test_every_part_of_the_key_separates_answers(
        self, difference: dict[str, object]
    ) -> None:
        """Each of these changes the answer, so none may share an entry."""
        cache = InMemoryInsightCache()
        await cache.put(_key(), GeneratedInsights.unavailable(UnavailableReason.NO_PROVIDER))

        assert await cache.get(_key(**difference)) is None

    async def test_it_is_bounded(self) -> None:
        """Unbounded would be a slow leak: every filter combination is a key."""
        cache = InMemoryInsightCache(max_entries=2)
        value = GeneratedInsights.unavailable(UnavailableReason.NO_PROVIDER)

        for digest in ("a", "b", "c"):
            await cache.put(_key(facts_digest=digest), value)

        assert await cache.get(_key(facts_digest="a")) is None
        assert await cache.get(_key(facts_digest="c")) is not None

    def test_a_cache_that_holds_nothing_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="at least one"):
            InMemoryInsightCache(max_entries=0)


class TestWhatTheServiceAsksTwice:
    @pytest.fixture
    def cache(self) -> InMemoryInsightCache:
        return InMemoryInsightCache()

    @pytest.fixture
    def service(
        self, catalogue: PlaybookCatalogue, cache: InMemoryInsightCache
    ) -> GenerateInsights:
        return GenerateInsights(
            prompts=FilePromptSource(PromptLibrary()), catalogue=catalogue, cache=cache
        )

    async def _twice(self, service: GenerateInsights, provider: FakeProvider) -> None:
        for _ in range(2):
            await service.execute(GenerateInsightsRequest(facts=_facts()), provider)

    async def test_the_same_figures_are_generated_once(self, service: GenerateInsights) -> None:
        provider = _answering(_item())

        await self._twice(service, provider)

        assert len(provider.requests) == 1

    async def test_the_second_reader_gets_the_same_answer(self, service: GenerateInsights) -> None:
        provider = _answering(_item())

        first = await service.execute(GenerateInsightsRequest(facts=_facts()), provider)
        second = await service.execute(GenerateInsightsRequest(facts=_facts()), provider)

        assert second.status is InsightsStatus.GENERATED
        assert [i.sentence for i in second.insights] == [i.sentence for i in first.insights]

    async def test_changed_figures_are_asked_again(self, service: GenerateInsights) -> None:
        """The cache keys on the facts, so a moved number is a miss."""
        provider = _answering(_item())

        await service.execute(GenerateInsightsRequest(facts=_facts()), provider)
        moved = FactSet(
            subject="the executive scorecard",
            facts=(
                Fact(
                    key="first_contact_resolution",
                    label="First contact resolution",
                    display="75%",
                    n=112,
                    basis="OBSERVED",
                ),
            ),
        )
        await service.execute(GenerateInsightsRequest(facts=moved), provider)

        assert len(provider.requests) == 2

    async def test_a_refusal_is_not_paid_for_twice(self, service: GenerateInsights) -> None:
        """A broken prompt costs one call per fact set, not one per page load."""
        provider = _answering(_item(sentence="Resolution slipped to 71%."))

        await self._twice(service, provider)

        assert len(provider.requests) == 1

    async def test_an_outage_is_never_cached(self, service: GenerateInsights) -> None:
        """The key says nothing about whether the network is up, so a cached
        outage would outlive the outage."""
        down = UnavailableProvider()

        first = await service.execute(GenerateInsightsRequest(facts=_facts()), down)
        assert first.reason is UnavailableReason.PROVIDER_FAILED

        recovered = _answering(_item())
        second = await service.execute(GenerateInsightsRequest(facts=_facts()), recovered)

        assert second.status is InsightsStatus.GENERATED
        assert len(recovered.requests) == 1

    async def test_a_screen_with_nothing_published_asks_no_model_either_time(
        self, service: GenerateInsights
    ) -> None:
        """It costs nothing to answer, so there is nothing to cache."""
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

        provider = _answering(_item())
        for _ in range(2):
            await service.execute(GenerateInsightsRequest(facts=withheld), provider)

        assert provider.requests == []
