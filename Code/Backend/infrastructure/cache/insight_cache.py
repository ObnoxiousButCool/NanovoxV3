"""An in-process, bounded cache of generated insight surfaces.

## Why in-process is enough, and where it stops being enough

D14 records the deployment as trusted-network and single-tenant, so one
process *is* the deployment: a cache held in it is shared by every reader,
and the default `/exec` view — by far the most requested, and the one whose
facts change only when the corpus does — is generated once rather than once
per page load.

Two limits, stated rather than discovered:

- **It does not survive a restart.** The first request after a deploy pays
  again. Under `--reload` in development that is most requests, which is
  worth knowing before concluding the cache is not working.
- **It is not shared between processes.** The day this runs behind more
  than one worker, each pays once. That is the day it becomes a table.

## Bounded, and evicted oldest-first

Unbounded would be a slow leak: every distinct filter combination a reader
tries is a new key, and nothing ever removes one. The cap is on entries
rather than bytes because the entries are uniform — a handful of sentences
each — so counting them is an honest proxy for size and a much cheaper one.

Insertion order is the eviction order. Not true LRU: a read does not
refresh an entry's position. For this workload the distinction is not worth
the bookkeeping — the hot key (no filters) is regenerated the moment the
corpus changes anyway, and the cold ones are a reader's one-off
combinations, which are exactly what should fall off the end.
"""

from __future__ import annotations

from collections import OrderedDict

from application.ports.insight_cache import InsightCache, InsightCacheKey
from domain.insights.generated import GeneratedInsights

#: Roughly: every screen, times a reader's filter combinations, with room
#: to spare. Small enough that the whole cache is a rounding error in
#: memory; large enough that ordinary use never evicts.
DEFAULT_MAX_ENTRIES = 256


class InMemoryInsightCache(InsightCache):
    """Holds surfaces for the life of the process."""

    def __init__(self, max_entries: int = DEFAULT_MAX_ENTRIES) -> None:
        if max_entries < 1:
            raise ValueError("An insight cache must hold at least one entry.")
        self._max_entries = max_entries
        self._entries: OrderedDict[InsightCacheKey, GeneratedInsights] = OrderedDict()

    async def get(self, key: InsightCacheKey) -> GeneratedInsights | None:
        return self._entries.get(key)

    async def put(self, key: InsightCacheKey, value: GeneratedInsights) -> None:
        self._entries[key] = value
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)
