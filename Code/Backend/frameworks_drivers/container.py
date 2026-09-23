"""Composition root.

Every concrete adapter is chosen here and nowhere else. Use cases receive
their dependencies through constructors, so no module reaches out for a
global.

Long-lived resources (the engine, the session factory) are built once per
process and held on the container; use cases are cheap and are built per
request. Grows with each phase: Phase 1 added reference-data repositories,
Phase 3 adds the LLM provider registry and audit log, and so on — nothing
here anticipates a phase before it lands.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from application.ports.call_repository import CallRepository
from application.ports.clock import Clock
from application.ports.health_probe import HealthProbe
from application.ports.reference_lookup import ReferenceLookup
from application.ports.reference_repository import ReferenceRepository
from application.ports.reference_source import ReferenceSource
from application.ports.transcript_source import TranscriptSource
from application.use_cases.get_health import GetHealth
from application.use_cases.import_reference_data import ImportReferenceData
from application.use_cases.ingest_transcripts import IngestTranscripts
from application.use_cases.list_providers import ListProviders, ProviderProbe
from infrastructure.config.settings import Settings
from infrastructure.corpus.pdf_corpus_source import PdfCorpusSource
from infrastructure.llm.provider_probe import RegistryProviderProbe
from infrastructure.llm.registry import PROVIDER_NAMES, ProviderRegistry
from infrastructure.logging.llm_audit import LlmAuditLog
from infrastructure.persistence.engine import create_database_engine, create_session_factory
from infrastructure.persistence.health_probe import DatabaseHealthProbe
from infrastructure.persistence.repositories.call_repository import SqlCallRepository
from infrastructure.persistence.repositories.reference_lookup import SqlReferenceLookup
from infrastructure.persistence.repositories.reference_repository import SqlReferenceRepository
from infrastructure.reference.xlsx_reference_source import XlsxReferenceSource
from infrastructure.system_clock import SystemClock


@dataclass(frozen=True)
class Container:
    """Holds the process-wide dependencies and builds use cases on demand."""

    settings: Settings
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    clock: Clock
    health_probes: tuple[HealthProbe, ...]
    reference_source: ReferenceSource
    reference_repository: ReferenceRepository
    transcript_source: TranscriptSource
    reference_lookup: ReferenceLookup
    call_repository: CallRepository
    provider_registry: ProviderRegistry
    provider_probe: ProviderProbe

    def get_health(self) -> GetHealth:
        return GetHealth(probes=self.health_probes, clock=self.clock)

    def import_reference_data(self) -> ImportReferenceData:
        return ImportReferenceData(
            source=self.reference_source, repository=self.reference_repository
        )

    def ingest_transcripts(self) -> IngestTranscripts:
        return IngestTranscripts(
            source=self.transcript_source,
            lookup=self.reference_lookup,
            repository=self.call_repository,
        )

    def list_providers(self) -> ListProviders:
        return ListProviders(
            probe=self.provider_probe,
            names=PROVIDER_NAMES,
            default_name=self.settings.llm_provider,
        )


def build_container(settings: Settings) -> Container:
    """Wire the object graph for a running application."""
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    clock = SystemClock()
    audit = LlmAuditLog(include_bodies=settings.log_llm_prompts)
    provider_registry = ProviderRegistry(settings, audit)
    return Container(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        clock=clock,
        health_probes=(DatabaseHealthProbe(engine),),
        reference_source=XlsxReferenceSource(settings.workbook_path),
        reference_repository=SqlReferenceRepository(session_factory),
        transcript_source=PdfCorpusSource(settings.transcripts_path),
        reference_lookup=SqlReferenceLookup(session_factory),
        call_repository=SqlCallRepository(session_factory, clock),
        provider_registry=provider_registry,
        provider_probe=RegistryProviderProbe(
            provider_registry, settings.llm_provider, settings.llm_probe_timeout_seconds
        ),
    )


async def dispose_container(container: Container) -> None:
    """Release the resources held by the container."""
    await container.engine.dispose()
