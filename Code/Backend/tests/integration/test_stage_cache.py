"""`SqlStageCache` against a real (temporary) SQLite database.

Keyed by (transcript hash, layer, prompt version, model) — plan §7's "Cache
layer outputs... so re-runs don't re-bill."
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from application.ports.stage_cache import StageCacheKey
from domain.layers import Layer
from infrastructure.persistence.repositories.stage_cache import SqlStageCache
from infrastructure.system_clock import SystemClock

_KEY = StageCacheKey(
    transcript_hash="abc123", layer=Layer.L2, prompt_version="1.0.0", model="gpt-4o-mini"
)


async def test_a_miss_returns_none(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    cache = SqlStageCache(session_factory, SystemClock())

    assert await cache.get(_KEY) is None


async def test_a_stored_value_is_read_back(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    cache = SqlStageCache(session_factory, SystemClock())

    await cache.put(_KEY, '{"category": "Billing"}')

    assert await cache.get(_KEY) == '{"category": "Billing"}'


async def test_a_repeat_write_replaces_rather_than_duplicates(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    cache = SqlStageCache(session_factory, SystemClock())

    await cache.put(_KEY, "first")
    await cache.put(_KEY, "second")

    assert await cache.get(_KEY) == "second"


async def test_keys_differing_only_by_layer_are_independent(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    cache = SqlStageCache(session_factory, SystemClock())
    other_layer = StageCacheKey(
        transcript_hash=_KEY.transcript_hash,
        layer=Layer.L3,
        prompt_version=_KEY.prompt_version,
        model=_KEY.model,
    )

    await cache.put(_KEY, "l2 output")
    await cache.put(other_layer, "l3 output")

    assert await cache.get(_KEY) == "l2 output"
    assert await cache.get(other_layer) == "l3 output"


async def test_keys_differing_only_by_prompt_version_are_independent(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    # A prompt edit must be a cache miss, not a stale answer from the old
    # wording — the version is part of the key precisely so a rewritten
    # prompt can't silently reuse an answer it never actually produced.
    cache = SqlStageCache(session_factory, SystemClock())
    newer_prompt = StageCacheKey(
        transcript_hash=_KEY.transcript_hash,
        layer=_KEY.layer,
        prompt_version="1.1.0",
        model=_KEY.model,
    )

    await cache.put(_KEY, "old wording's answer")

    assert await cache.get(newer_prompt) is None


async def test_keys_differing_only_by_model_are_independent(
    engine: AsyncEngine, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    cache = SqlStageCache(session_factory, SystemClock())
    other_model = StageCacheKey(
        transcript_hash=_KEY.transcript_hash,
        layer=_KEY.layer,
        prompt_version=_KEY.prompt_version,
        model="claude-opus-5",
    )

    await cache.put(_KEY, "gpt-4o-mini's answer")

    assert await cache.get(other_model) is None
