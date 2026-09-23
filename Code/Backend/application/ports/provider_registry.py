"""Port for resolving a configured model provider by name (plan §8 Phase 4).

Distinct from `ProviderProbe` (`application/use_cases/list_providers.py`):
that one reports every registered provider's status for a picker; this one
builds exactly the one provider a run will actually use.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from application.ports.llm_provider import LLMProvider


class ProviderSource(ABC):
    """Builds a live provider adapter from a name and an optional model
    override, or the configured default when neither is given."""

    @abstractmethod
    def create(self, name: str | None = None, model: str | None = None) -> LLMProvider: ...
