"""Stage-output cache port (plan §7).

Keyed by (transcript hash, layer, prompt version, model) rather than by
call reference — see ``domain/transcript_hash.py`` for why. A cache hit
means a re-run of the pipeline (after a code change to a downstream layer,
or a retry of a failed run) doesn't re-bill an LLM call whose answer, given
this exact transcript content, this exact prompt wording and this exact
model, cannot have changed.

The stored value is the layer's raw completion text, not the parsed
domain object: caching the validated pydantic instance would tie the cache
to today's schema, and a schema change between the cached run and a replay
would then need a migration instead of simply being a cache miss.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from domain.layers import Layer


@dataclass(frozen=True)
class StageCacheKey:
    """Identifies one layer's output for one exact transcript, prompt and model."""

    transcript_hash: str
    layer: Layer
    prompt_version: str
    model: str


class StageCache(ABC):
    """Reads and writes cached layer completions."""

    @abstractmethod
    async def get(self, key: StageCacheKey) -> str | None:
        """The cached completion text, or ``None`` on a miss."""

    @abstractmethod
    async def put(self, key: StageCacheKey, value: str) -> None:
        """Store a completion, replacing any value already cached for this key."""
