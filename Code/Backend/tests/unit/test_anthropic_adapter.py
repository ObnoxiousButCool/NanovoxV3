"""Anthropic adapter, driven through a stubbed HTTP transport.

Exercises the real adapter code — request shaping, error translation,
status reporting — without a network call or a bill.
"""

from __future__ import annotations

import json
from typing import Any

import httpx2 as httpx
import pytest
from anthropic import AsyncAnthropic

from application.ports.llm_provider import LlmRequest
from domain.errors import ProviderUnavailableError
from infrastructure.llm.providers.anthropic_provider import AnthropicProvider
from infrastructure.logging.llm_audit import LlmAuditLog
from tests.support.llm import Sentiment

REQUEST = LlmRequest(prompt="Classify this.", response_model=Sentiment)


def messages_response(text: str, **usage: int) -> dict[str, Any]:
    return {
        "id": "msg_1",
        "type": "message",
        "role": "assistant",
        "model": "claude-opus-5",
        "content": [{"type": "text", "text": text}],
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "usage": {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
        },
    }


VALID_TEXT = (
    '{"sentiment": "NEGATIVE", "justification": "Cost was prioritised.", "confidence": 0.9}'
)


def provider_with(handler: httpx.MockTransport) -> AnthropicProvider:
    return AnthropicProvider(
        api_key="test",
        model="claude-opus-5",
        timeout_seconds=5.0,
        max_retries=0,
        max_output_tokens=512,
        audit=LlmAuditLog(),
        client=AsyncAnthropic(api_key="test", http_client=httpx.AsyncClient(transport=handler)),
    )


class TestRequestShaping:
    async def test_no_sampling_parameters_are_sent(self) -> None:
        # Current Claude models reject temperature/top_p/top_k outright;
        # determinism comes from the schema constraint instead.
        sent: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            sent.update(json.loads(request.content))
            return httpx.Response(200, json=messages_response(VALID_TEXT))

        provider = provider_with(httpx.MockTransport(handler))
        await provider.complete(REQUEST)
        await provider.aclose()

        assert "temperature" not in sent
        assert "top_p" not in sent
        assert "top_k" not in sent
        assert sent["max_tokens"] == 512

    async def test_a_system_prompt_is_sent_as_the_system_field(self) -> None:
        sent: dict[str, Any] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            sent.update(json.loads(request.content))
            return httpx.Response(200, json=messages_response(VALID_TEXT))

        provider = provider_with(httpx.MockTransport(handler))
        await provider.complete(
            LlmRequest(prompt="Classify.", response_model=Sentiment, system="Be terse.")
        )
        await provider.aclose()

        assert sent["system"] == "Be terse."

    async def test_the_repair_correction_is_appended_to_the_prompt(self) -> None:
        sent: list[dict[str, Any]] = []

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            sent.append(body)
            if len(sent) == 1:
                return httpx.Response(200, json=messages_response("not json"))
            return httpx.Response(200, json=messages_response(VALID_TEXT))

        provider = provider_with(httpx.MockTransport(handler))
        result = await provider.complete(REQUEST)
        await provider.aclose()

        assert result.repaired
        second_prompt = sent[1]["messages"][0]["content"]
        assert "did not match the required schema" in second_prompt

    async def test_usage_is_read_from_the_response(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json=messages_response(VALID_TEXT, input_tokens=14, output_tokens=6)
            )

        provider = provider_with(httpx.MockTransport(handler))
        result = await provider.complete(REQUEST)
        await provider.aclose()

        assert result.usage.input_tokens == 14
        assert result.usage.output_tokens == 6


class TestFailureTranslation:
    async def test_an_http_error_becomes_a_provider_outage(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"type": "error", "error": {"message": "overloaded"}})

        provider = provider_with(httpx.MockTransport(handler))

        with pytest.raises(ProviderUnavailableError) as exc_info:
            await provider.complete(REQUEST)
        await provider.aclose()

        assert "HTTP 500" in exc_info.value.message

    async def test_a_rate_limit_reads_the_plain_integer_retry_after(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                429,
                headers={"retry-after": "12"},
                json={"type": "error", "error": {"message": "rate limited"}},
            )

        provider = provider_with(httpx.MockTransport(handler))

        with pytest.raises(ProviderUnavailableError) as exc_info:
            await provider.complete(REQUEST)
        await provider.aclose()

        assert exc_info.value.retry_after == pytest.approx(12.0)

    async def test_a_connection_failure_is_a_provider_outage(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        provider = provider_with(httpx.MockTransport(handler))

        with pytest.raises(ProviderUnavailableError, match="could not be reached"):
            await provider.complete(REQUEST)
        await provider.aclose()


class TestStatus:
    async def test_reachable_on_a_successful_ping(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=messages_response("pong"))

        provider = provider_with(httpx.MockTransport(handler))
        status = await provider.status()
        await provider.aclose()

        assert status.reachable

    async def test_a_rejected_key_names_the_setting(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                401, json={"type": "error", "error": {"message": "invalid x-api-key"}}
            )

        provider = provider_with(httpx.MockTransport(handler))
        status = await provider.status()
        await provider.aclose()

        assert not status.reachable
        assert status.detail == "ANTHROPIC_API_KEY was rejected."
