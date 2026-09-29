"""`/insights/generated` over a real application.

The assertions that matter are the two the surface exists to protect: a
screen with no model still answers, saying so; and the model is only ever
shown numbers the screen itself published.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from application.dto.insight_response import InsightItem, InsightsResponse
from domain.insights.facts import numbers_in
from frameworks_drivers.api.dependencies import get_insight_provider
from frameworks_drivers.api.v1.insights.exec_scorecard import ExecScorecardResponse
from frameworks_drivers.api.v1.insights.generated import exec_facts
from tests.integration.test_insights_endpoints import AS_OF, seed
from tests.support.llm import FakeProvider

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


def _answer(sentence: str, *, fact_keys: list[str] | None = None) -> InsightsResponse:
    return InsightsResponse(
        insights=[
            InsightItem.model_validate(
                {
                    "key": "resolution",
                    "sentence": sentence,
                    "kind": "INFERENCE",
                    "severity": "READ_FIRST",
                    "lens": "EMPLOYERS",
                    "fact_keys": fact_keys or ["first_contact_resolution"],
                    "issue_key": "none",
                }
            )
        ]
    )


@pytest.mark.anyio
async def test_no_provider_answers_200_with_an_explicit_unavailable_state(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """U2: never a hidden panel, never templated copy, never a 500."""
    await seed(session_factory, calls_per_employer={"EMP-1001": 40})

    response = client.get("/api/v1/insights/generated", params={"asOf": AS_OF})

    assert response.status_code == 200
    body = response.json()
    assert body["status"]["code"] == "UNAVAILABLE"
    assert body["reason"]["code"] in {"NO_PROVIDER", "NO_PUBLISHED_FACTS"}
    assert body["insights"] == []
    # The reason is written for a reader, not only coded for a client.
    assert body["reason"]["label"]


@pytest.mark.anyio
async def test_a_clean_answer_reaches_the_wire_with_its_kind(
    app: FastAPI, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed(session_factory, calls_per_employer={"EMP-1001": 40})
    scorecard = client.get("/api/v1/insights/exec", params={"asOf": AS_OF}).json()
    resolution = next(
        metric for metric in scorecard["metrics"] if metric["key"] == "first_contact_resolution"
    )
    printed = f"{round(resolution['figure']['value'] * 100)}%"

    provider = FakeProvider(_answer(f"Resolution held at {printed}."))
    app.dependency_overrides[get_insight_provider] = lambda: provider
    try:
        response = client.get("/api/v1/insights/generated", params={"asOf": AS_OF})
    finally:
        app.dependency_overrides.pop(get_insight_provider, None)

    body = response.json()
    assert body["status"]["code"] == "GENERATED"
    assert body["insights"][0]["kind"]["code"] == "INFERENCE"
    assert body["insights"][0]["factKeys"] == ["first_contact_resolution"]


@pytest.mark.anyio
async def test_a_figure_the_screen_never_published_is_refused(
    app: FastAPI, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """The property Phase 5 exits on, asserted end to end."""
    await seed(session_factory, calls_per_employer={"EMP-1001": 40})

    provider = FakeProvider(_answer("Resolution collapsed to 3% this week."))
    app.dependency_overrides[get_insight_provider] = lambda: provider
    try:
        response = client.get("/api/v1/insights/generated", params={"asOf": AS_OF})
    finally:
        app.dependency_overrides.pop(get_insight_provider, None)

    body = response.json()
    assert body["status"]["code"] == "UNAVAILABLE"
    assert body["reason"]["code"] == "GUARDRAIL_REJECTED"
    assert body["insights"] == []


@pytest.mark.anyio
async def test_the_model_is_shown_only_numbers_the_screen_published(
    app: FastAPI, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Every number in the prompt traces to the scorecard response.

    This is the check that keeps the two endpoints honest with each other.
    If `/exec` ever starts rounding differently from the fact builder, a
    sentence could quote a figure that is nowhere on the page, and this
    fails rather than the reader noticing.
    """
    await seed(session_factory, calls_per_employer={"EMP-1001": 40})
    scorecard = client.get("/api/v1/insights/exec", params={"asOf": AS_OF}).json()

    provider = FakeProvider(_answer("Resolution is the figure to watch."))
    app.dependency_overrides[get_insight_provider] = lambda: provider
    try:
        client.get("/api/v1/insights/generated", params={"asOf": AS_OF})
    finally:
        app.dependency_overrides.pop(get_insight_provider, None)

    # The invariant: the model is never shown a number it may not quote.
    # Two different code paths — what `_render_facts` prints and what
    # `allowed_numbers` permits — and a number offered then punished is a
    # trap. ("v9" in a withheld reason put a 9 in front of the model once.)
    prompt = provider.requests[0].prompt
    facts_block = prompt.split("THE FIGURES")[1].split("## The one rule")[0]
    facts = exec_facts(ExecScorecardResponse.model_validate(scorecard))

    assert numbers_in(facts_block) <= facts.allowed_numbers


@pytest.mark.anyio
async def test_the_risk_screen_is_shown_its_own_figures(
    app: FastAPI, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """A second screen means a second fact builder, not a second branch in one."""
    await seed(session_factory, calls_per_employer={"EMP-1001": 40})

    provider = FakeProvider(
        _answer("Most accounts could not be assessed.", fact_keys=["accounts_assessed"])
    )
    app.dependency_overrides[get_insight_provider] = lambda: provider
    try:
        response = client.get(
            "/api/v1/insights/generated", params={"asOf": AS_OF, "screen": "risk"}
        )
    finally:
        app.dependency_overrides.pop(get_insight_provider, None)

    assert response.status_code == 200
    prompt = provider.requests[0].prompt
    assert "the account risk screen" in prompt
    assert "accounts_assessed" in prompt
    # Scoped to the facts block: the instructions around it legitimately use
    # these words — the "Payer & carrier" lens is described as "billing,
    # premium and carrier-owned issues" — and what matters is that neither
    # figure is offered to the model.
    facts_block = prompt.split("THE FIGURES")[1].split("## The one rule")[0]
    # A comparison across weeks is a number nobody computed, and the screen
    # shows lives rather than money.
    assert "weekly" not in facts_block
    assert "premium" not in facts_block


@pytest.mark.anyio
async def test_an_unknown_screen_is_refused_rather_than_guessed(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """`hierarchy` used to stand in for an unknown screen here. It is a
    known one now, so the example has to be a name nobody will ever add —
    a screen with no fact builder must 422 rather than be answered from
    whichever builder looked closest."""
    await seed(session_factory, calls_per_employer={"EMP-1001": 40})

    response = client.get(
        "/api/v1/insights/generated", params={"asOf": AS_OF, "screen": "not-a-screen"}
    )

    assert response.status_code == 422


@pytest.mark.anyio
@pytest.mark.parametrize("screen", ["hierarchy", "agents"])
async def test_a_screen_with_a_fact_builder_is_answered(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession], screen: str
) -> None:
    """Both of these are surfaces the prototype carries. The point is that
    the endpoint reaches its own builder — whether the model then writes
    anything is the provider's business and is tested elsewhere."""
    await seed(session_factory, calls_per_employer={"EMP-1001": 40})

    response = client.get("/api/v1/insights/generated", params={"asOf": AS_OF, "screen": screen})

    assert response.status_code == 200


@pytest.mark.anyio
async def test_the_account_screen_is_shown_only_its_own_account(
    app: FastAPI, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed(session_factory, calls_per_employer={"EMP-1001": 40})

    provider = FakeProvider(
        _answer("Contact rate is the figure to watch.", fact_keys=["calls_in_period"])
    )
    app.dependency_overrides[get_insight_provider] = lambda: provider
    try:
        response = client.get(
            "/api/v1/insights/generated",
            params={"asOf": AS_OF, "screen": "account", "employerRef": "EMP-1001"},
        )
    finally:
        app.dependency_overrides.pop(get_insight_provider, None)

    assert response.status_code == 200
    prompt = provider.requests[0].prompt
    # The subject names the account the way the page does. (The seed happens
    # to name employers after their reference, so asserting the code is
    # absent would test the fixture rather than the behaviour.)
    name = client.get(f"/api/v1/insights/accounts/EMP-1001?asOf={AS_OF}").json()["facts"]["name"]
    assert name in prompt

    facts_block = prompt.split("THE FIGURES")[1].split("## The one rule")[0]
    assert "calls_in_period" in facts_block
    # Reference facts stay out: a sentence mixing enrolled lives into a
    # reading of the calls blurs what the REFERENCE chip exists to mark.
    assert "enrolled" not in facts_block.lower()
    assert "premium" not in facts_block.lower()
    # Metric 12 is per agent; an account-level quality figure must not appear
    # to exist.
    assert "quality" not in facts_block.lower()


@pytest.mark.anyio
async def test_the_account_screen_needs_to_know_which_account(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await seed(session_factory, calls_per_employer={"EMP-1001": 40})

    response = client.get("/api/v1/insights/generated", params={"asOf": AS_OF, "screen": "account"})

    assert response.status_code == 422


@pytest.mark.anyio
async def test_an_unknown_account_is_a_404_not_an_empty_surface(
    client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """An insight panel for a reference nobody recognises would invent a
    business relationship, exactly as the account page itself refuses to."""
    await seed(session_factory, calls_per_employer={"EMP-1001": 40})

    response = client.get(
        "/api/v1/insights/generated",
        params={"asOf": AS_OF, "screen": "account", "employerRef": "EMP-9999"},
    )

    assert response.status_code == 404


@pytest.mark.anyio
async def test_an_account_nobody_could_assess_spends_nothing(
    app: FastAPI, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Most of the book is here at this corpus's volume.

    Its counts are true and already on the tiles; a sentence restating one is
    worth neither the wait nor the spend, so no model is asked at all.
    """
    await seed(session_factory, calls_per_employer={"EMP-1001": 1})

    provider = FakeProvider(_answer("Something."))
    app.dependency_overrides[get_insight_provider] = lambda: provider
    try:
        response = client.get(
            "/api/v1/insights/generated",
            params={"asOf": AS_OF, "screen": "account", "employerRef": "EMP-1001"},
        )
    finally:
        app.dependency_overrides.pop(get_insight_provider, None)

    body = response.json()
    assert body["status"]["code"] == "UNAVAILABLE"
    assert body["reason"]["code"] == "NOT_ASSESSABLE"
    assert provider.requests == []


@pytest.mark.anyio
async def test_a_withheld_figure_reaches_the_model_in_a_reader_s_words(
    app: FastAPI, client: TestClient, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    """Handed a code it writes the code. The first real run produced "the
    contact rate is WITHHELD", which is our token in a reader's sentence."""
    await seed(session_factory, calls_per_employer={"EMP-1001": 40})

    provider = FakeProvider(_answer("Resolution held."))
    app.dependency_overrides[get_insight_provider] = lambda: provider
    try:
        client.get("/api/v1/insights/generated", params={"asOf": AS_OF})
    finally:
        app.dependency_overrides.pop(get_insight_provider, None)

    facts_block = provider.requests[0].prompt.split("THE FIGURES")[1].split("## The one rule")[0]
    assert "WITHHELD" not in facts_block
    assert "BELOW_MIN_N" not in facts_block
    assert "not published" in facts_block
