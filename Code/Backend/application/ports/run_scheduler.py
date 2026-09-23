"""Port for running a coroutine in the background of this process
(plan §8 Phase 3, "run orchestration").
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Coroutine
from typing import Any


class RunScheduler(ABC):
    """Begins working a run without blocking the caller."""

    @abstractmethod
    def start(self, run_id: int, work: Coroutine[Any, Any, None]) -> bool:
        """Begin working a run. Returns False if one is already in flight."""
