"""Insight-surface cache port.

## Why a second cache and not the stage cache

`StageCache` keys on `(transcript hash, layer, prompt version, model)` and
stores raw completion text. Neither half fits here: an insight is computed
from a *screen's figures*, not from one transcript, and `Layer` names the
four extraction stages. Storing a facts digest in a field called
`transcript_hash` would be a lie in the one place a reader goes to find out
what a cached row means.

## What it stores, and why the stage cache's reasoning does not carry over

`StageCache` stores raw text specifically so a schema change is a cache
miss rather than a migration. That concern is real for rows that outlive a
deployment. These do not: the surface is served from a single-tenant,
trusted-network process (D14/R9), so the cache is per process and dies with
it. Within one process there is exactly one schema, so storing the domain
object is simpler and no less safe. If this ever needs to survive a restart
or be shared between processes, it becomes a table and that argument comes
back with it.

## What is worth caching

A generated surface, and a rejected one.

Generated is obvious. **Rejected is the one worth explaining:** if the model
states a number no fact supports, it will very likely do so again for the
same figures, and re-asking bills for the privilege of being told the same
thing. Caching the refusal makes a broken prompt cost one call per fact set
rather than one per page load — and because the prompt version is part of
the key, fixing the prompt invalidates the entry by itself. Nobody has to
remember to clear it.

A provider *failure* is never cached. That is infrastructure, not an answer:
the key says nothing about whether the network is up, and a cached outage
would outlive the outage.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from domain.insights.generated import GeneratedInsights


@dataclass(frozen=True)
class InsightCacheKey:
    """Everything that determines the answer, and nothing that does not.

    Notably absent: the filters. Two different filter strings that select
    the same calls produce the same figures and deserve the same answer, and
    `FactSet.digest` is what says so.
    """

    facts_digest: str
    prompt_version: str
    provider: str
    model: str
    #: How many sentences were asked for. Part of the key because asking for
    #: two is a different request from asking for four, not a truncation of
    #: it — the model chooses differently when it has fewer to spend.
    limit: int


class InsightCache(ABC):
    """Reads and writes generated surfaces."""

    @abstractmethod
    async def get(self, key: InsightCacheKey) -> GeneratedInsights | None:
        """The cached surface, or ``None`` on a miss."""

    @abstractmethod
    async def put(self, key: InsightCacheKey, value: GeneratedInsights) -> None:
        """Store a surface, replacing any already cached for this key."""
