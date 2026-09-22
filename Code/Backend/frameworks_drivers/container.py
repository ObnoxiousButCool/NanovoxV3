"""Composition root.

Every concrete adapter is chosen here and nowhere else. Use cases receive
their dependencies through constructors, so no module reaches out for a
global.

Long-lived resources (the engine, the session factory) are built once per
process and held on the container; use cases are cheap and are built per
request. Grows with each phase: Phase 1 adds reference-data repositories,
Phase 3 the LLM provider registry, and so on — nothing here anticipates them.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from application.ports.clock import Clock
from application.ports.health_probe import HealthProbe
from application.use_cases.get_health import GetHealth
from infrastructure.config.settings import Settings
from infrastructure.persistence.engine import create_database_engine, create_session_factory
from infrastructure.persistence.health_probe import DatabaseHealthProbe
from infrastructure.system_clock import SystemClock


@dataclass(frozen=True)
class Container:
    """Holds the process-wide dependencies and builds use cases on demand."""

    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    clock: Clock
    health_probes: tuple[HealthProbe, ...]

    def get_health(self) -> GetHealth:
        return GetHealth(probes=self.health_probes, clock=self.clock)


def build_container(settings: Settings) -> Container:
    """Wire the object graph for a running application."""
    engine = create_database_engine(settings)
    return Container(
        settings=settings,
        engine=engine,
        session_factory=create_session_factory(engine),
        clock=SystemClock(),
        health_probes=(DatabaseHealthProbe(engine),),
    )


async def dispose_container(container: Container) -> None:
    """Release the resources held by the container."""
    await container.engine.dispose()
