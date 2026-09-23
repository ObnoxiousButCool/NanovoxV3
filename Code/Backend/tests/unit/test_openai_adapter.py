"""OpenAI adapter, driven through a stubbed HTTP transport.

Exercises the real adapter code — strict-schema shaping, the
reasoning-model request shape, error translation, status reporting —
without a network call or a bill.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from openai import AsyncOpenAI

from application.ports.llm_provider import LlmRequest
from domain.errors import ProviderUnavailableError
from infrastructure.llm.providers.openai_provider import OpenAIProvider
from infrastructure.logging.llm_audit import LlmAuditLog
from tests.support.llm import VALID_JSON, Sentiment

REQUEST = LlmRequest(prompt="Classify this.", response_model=Sentiment)


def chat_completion(content: str, **usage: int) -> dict[str, Any]:
    body: dict[str, Any] = {
        "id": "chatcmpl-1",
        "object": "chat.completion",
        "created": 1,
        "model": "gpt-4o-mini",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    }
    if usage:
        body["usage"] = {
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0),
        }
    return body


def provider_with(handler: httpx.MockTransport, *, model: str = "gpt-4o-mini") -> OpenAIProvider:
    return OpenAIProvider(
        api_key="test",
        model=model,
        timeout_seconds=5.0,
        max_retries=0,
        max_output_tokens=512,
        audit=LlmAuditLog(),
        client=AsyncOpenAI(api_key="test", http_client=httpx.AsyncClient(transport=handler)),
    )


class TestRequestShaping:
    async def test_a_non_reasoning_model_sends_temperature_and_max_tokens(self) -> None:
        sent: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            sent.update(json.loads(request.content))
            return httpx.Response(200, json=chat_completion(VALID_JSON))

        provider = provider_with(httpx.MockTransport(handler))
        await provider.complete(REQUEST)
        await provider.aclose()

        assert sent["temperature"] == 0.0
        assert sent["max_tokens"] == 512
        assert sent["response_format"]["json_schema"]["strict"] is True

    async def test_a_reasoning_model_sends_reasoning_effort_instead_of_temperature(self) -> None:
        sent: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            sent.update(json.loads(request.content))
            return httpx.Response(200, json=chat_completion(VALID_JSON))

        provider = provider_with(httpx.MockTransport(handler), model="o3")
        await provider.complete(REQUEST)
        await provider.aclose()

        assert "temperature" not in sent
        assert "max_tokens" not in sent
        assert sent["reasoning_effort"] == "low"
        assert sent["max_completion_tokens"] == 512

    async def test_usage_is_read_from_the_response(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json=chat_completion(VALID_JSON, prompt_tokens=12, completion_tokens=4)
            )

        provider = provider_with(httpx.MockTransport(handler))
        result = await provider.complete(REQUEST)
        await provider.aclose()

        assert result.usage.input_tokens == 12
        assert result.usage.output_tokens == 4

    async def test_missing_usage_is_reported_as_unknown_not_as_zero(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=chat_completion(VALID_JSON))

        provider = provider_with(httpx.MockTransport(handler))
        result = await provider.complete(REQUEST)
        await provider.aclose()

        assert not result.usage.reported


class TestFailureTranslation:
    async def test_an_http_error_becomes_a_provider_outage(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": {"message": "internal error"}})

        provider = provider_with(httpx.MockTransport(handler))

        with pytest.raises(ProviderUnavailableError) as exc_info:
            await provider.complete(REQUEST)
        await provider.aclose()

        assert "HTTP 500" in exc_info.value.message

    async def test_a_rate_limit_reads_the_reset_header_as_retry_after(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                429,
                headers={"x-ratelimit-reset-tokens": "1m30s"},
                json={"error": {"message": "rate limited"}},
            )

        provider = provider_with(httpx.MockTransport(handler))

        with pytest.raises(ProviderUnavailableError) as exc_info:
            await provider.complete(REQUEST)
        await provider.aclose()

        assert exc_info.value.retry_after == pytest.approx(90.0)

    async def test_a_connection_failure_is_a_provider_outage(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        provider = provider_with(httpx.MockTransport(handler))

        with pytest.raises(ProviderUnavailableError, match="could not be reached"):
            await provider.complete(REQUEST)
        await provider.aclose()


class TestStatus:
    async def test_reachable_when_the_model_can_be_retrieved(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"id": "gpt-4o-mini", "object": "model"})

        provider = provider_with(httpx.MockTransport(handler))
        status = await provider.status()
        await provider.aclose()

        assert status.reachable

    async def test_a_rejected_key_names_the_setting(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": {"message": "invalid api key"}})

        provider = provider_with(httpx.MockTransport(handler))
        status = await provider.status()
        await provider.aclose()

        assert not status.reachable
        assert status.detail == "OPENAI_API_KEY was rejected."

    async def test_a_model_unavailable_to_the_account_names_the_model(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"error": {"message": "model not found"}})

        provider = provider_with(httpx.MockTransport(handler))
        status = await provider.status()
        await provider.aclose()

        assert not status.reachable
        assert status.detail is not None
        assert "gpt-4o-mini" in status.detail
