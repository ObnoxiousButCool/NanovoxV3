"""Composition root.

Every concrete adapter is chosen here and nowhere else. Use cases receive
their dependencies through constructors, so no module reaches out for a
global.

Long-lived resources (the engine, the session factory) are built once per
process and held on the container; use cases are cheap and are built per
request. Grows with each phase: Phase 1 added reference-data repositories,
Phase 3 the LLM provider registry and audit log, Phase 4 the extraction
pipeline's own storage and prompts — nothing here anticipates a phase
before it lands.

L1 has no builder method of its own: it is a pure function
(`domain.extraction.l1_deterministic.run_l1`) with no ports to inject, so
`ClassifyCallL2` calls it directly rather than the container wiring it
separately.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from application.ports.action_repository import ActionRepository
from application.ports.answer_key_source import AnswerKeySource
from application.ports.call_extraction_repository import CallExtractionRepository
from application.ports.call_repository import CallRepository
from application.ports.clock import Clock
from application.ports.diagnostics_source import DiagnosticsSource
from application.ports.ground_truth_repository import GroundTruthRepository
from application.ports.ground_truth_source import GroundTruthSource
from application.ports.health_probe import HealthProbe
from application.ports.insight_cache import InsightCache
from application.ports.insights_source import InsightsSource
from application.ports.llm_provider import LLMProvider
from application.ports.prompts import PromptSource
from application.ports.reference_lookup import ReferenceLookup
from application.ports.reference_repository import ReferenceRepository
from application.ports.reference_source import ReferenceSource
from application.ports.run_repository import RunRepository
from application.ports.stage_cache import StageCache
from application.ports.transcript_source import TranscriptSource
from application.use_cases.classify_call_l2 import ClassifyCallL2
from application.use_cases.classify_call_l3 import ClassifyCallL3
from application.use_cases.classify_call_l4 import ClassifyCallL4
from application.use_cases.evaluate_extraction import EvaluateExtraction
from application.use_cases.generate_insights import GenerateInsights
from application.use_cases.get_health import GetHealth
from application.use_cases.import_answer_key import ImportAnswerKey
from application.use_cases.import_reference_data import ImportReferenceData
from application.use_cases.ingest_transcripts import IngestTranscripts
from application.use_cases.list_calls import ListCalls
from application.use_cases.list_providers import ListProviders, ProviderProbe
from application.use_cases.manage_actions import CreateAction, GetAction, ListActions, UpdateAction
from application.use_cases.playbooks import GetPlaybook, ListPlaybooks
from application.use_cases.read_call_evidence import ReadCallEvidence
from application.use_cases.read_insights import (
    GetAccountDetail,
    GetAccountRisk,
    GetActions,
    GetAgents,
    GetDemand,
    GetExecScorecard,
    GetFilterOptions,
    GetHierarchy,
    GetRules,
    InsightsReader,
)
from application.use_cases.run_extraction_over_corpus import RunExtractionOverCorpus
from application.use_cases.run_extraction_pipeline import ExtractionPipeline
from application.use_cases.seed_actions import SeedActions
from domain.actions import Lifecycle
from domain.dashboard_config import DashboardConfig
from domain.errors import ConfigurationError, NotFoundError
from domain.playbooks import PlaybookCatalogue
from domain.scoring.rubric import Rubric
from infrastructure.cache.insight_cache import InMemoryInsightCache
from infrastructure.config.action_lifecycle_loader import load_action_lifecycle
from infrastructure.config.dashboard_config import load_dashboard_config
from infrastructure.config.playbook_loader import load_playbooks
from infrastructure.config.rubric_loader import load_rubric
from infrastructure.config.settings import Settings
from infrastructure.corpus.pdf_answer_key_source import PdfAnswerKeySource
from infrastructure.corpus.pdf_corpus_source import PdfCorpusSource
from infrastructure.llm.prompt_source import FilePromptSource
from infrastructure.llm.prompts import PromptLibrary
from infrastructure.llm.provider_probe import RegistryProviderProbe
from infrastructure.llm.registry import PROVIDER_NAMES, ProviderRegistry
from infrastructure.logging.llm_audit import LlmAuditLog
from infrastructure.persistence.engine import create_database_engine, create_session_factory
from infrastructure.persistence.health_probe import DatabaseHealthProbe
from infrastructure.persistence.repositories.action_repository import SqlActionRepository
from infrastructure.persistence.repositories.call_extraction_repository import (
    SqlCallExtractionRepository,
)
from infrastructure.persistence.repositories.call_repository import SqlCallRepository
from infrastructure.persistence.repositories.diagnostics_source import SqlDiagnosticsSource
from infrastructure.persistence.repositories.ground_truth_repository import (
    SqlGroundTruthRepository,
)
from infrastructure.persistence.repositories.insights_source import SqlInsightsSource
from infrastructure.persistence.repositories.reference_lookup import SqlReferenceLookup
from infrastructure.persistence.repositories.reference_repository import SqlReferenceRepository
from infrastructure.persistence.repositories.run_repository import SqlRunRepository
from infrastructure.persistence.repositories.stage_cache import SqlStageCache
from infrastructure.reference.xlsx_ground_truth_source import XlsxGroundTruthSource
from infrastructure.reference.xlsx_reference_source import XlsxReferenceSource
from infrastructure.runner.background_runner import BackgroundRunner
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
    stage_cache: StageCache
    call_extraction_repository: CallExtractionRepository
    prompt_source: PromptSource
    rubric: Rubric
    run_repository: RunRepository
    #: One instance for the process's lifetime — the set of in-flight run
    #: tasks is itself state, not something a new instance could rebuild.
    background_runner: BackgroundRunner
    # Answer key (plan §8 Phase 2). Held here like any other adapter; the
    # import-linter contract, not the composition root, is what keeps
    # extraction away from it.
    diagnostics_source: DiagnosticsSource
    ground_truth_source: GroundTruthSource
    ground_truth_repository: GroundTruthRepository
    answer_key_source: AnswerKeySource
    # Stream B's read side (plan §8 Phase 6). The dashboard thresholds are
    # loaded once at startup rather than per request: they are the Metrics
    # sheet transcribed, and a figure whose min n changed between two
    # panels of one screen would be unexplainable.
    insights_source: InsightsSource
    dashboard_config: DashboardConfig
    #: Loaded at startup so a broken catalogue stops the application
    #: rather than rendering an empty panel (Revised plan I3).
    playbook_catalogue: PlaybookCatalogue
    #: Held on the container, not built per request: a cache rebuilt for
    #: every call would be a miss every time and quietly bill for it.
    insight_cache: InsightCache
    #: The action centre's lanes (D14, U3: config until the client confirms).
    action_lifecycle: Lifecycle
    action_repository: ActionRepository

    def insights_reader(self) -> InsightsReader:
        return InsightsReader(
            source=self.insights_source, config=self.dashboard_config, clock=self.clock
        )

    def get_exec_scorecard(self) -> GetExecScorecard:
        return GetExecScorecard(self.insights_reader(), self.dashboard_config)

    def get_filter_options(self) -> GetFilterOptions:
        # Takes the source directly, not the reader: the reader applies
        # filters, and applying them here is the bug this endpoint exists
        # to prevent.
        return GetFilterOptions(self.insights_source)

    def get_account_risk(self) -> GetAccountRisk:
        return GetAccountRisk(self.insights_reader(), self.dashboard_config)

    def get_account_detail(self) -> GetAccountDetail:
        return GetAccountDetail(self.insights_reader(), self.dashboard_config)

    def get_hierarchy(self) -> GetHierarchy:
        return GetHierarchy(self.insights_reader(), self.dashboard_config)

    def list_calls(self) -> ListCalls:
        # The same reader every figure uses, so the workbench cannot select
        # a different set of calls than the screen that linked to it.
        return ListCalls(self.insights_reader())

    def read_call_evidence(self) -> ReadCallEvidence:
        return ReadCallEvidence(self.call_repository, self.call_extraction_repository)

    def get_demand(self) -> GetDemand:
        return GetDemand(self.insights_reader(), self.dashboard_config)

    def get_actions(self) -> GetActions:
        return GetActions(self.insights_reader(), self.dashboard_config, self.playbook_catalogue)

    def get_rules(self) -> GetRules:
        return GetRules(self.insights_reader(), self.dashboard_config)

    def get_agents(self) -> GetAgents:
        return GetAgents(self.insights_reader(), self.dashboard_config)

    def generate_insights(self) -> GenerateInsights:
        return GenerateInsights(
            prompts=self.prompt_source,
            catalogue=self.playbook_catalogue,
            cache=self.insight_cache,
        )

    def insight_provider(self) -> LLMProvider | None:
        """The provider the insight surface will use, or nothing.

        Nothing is a legitimate answer, not an error: a deployment with no
        model configured shows an explicit unavailable panel (U2) and every
        figure on the screen still renders. A provider that exists but is
        rejected at call time is a different state, and is reported as one.
        """
        try:
            return self.provider_registry.create()
        except (ConfigurationError, NotFoundError):
            return None

    def list_playbooks(self) -> ListPlaybooks:
        return ListPlaybooks(self.playbook_catalogue)

    def get_playbook(self) -> GetPlaybook:
        return GetPlaybook(self.playbook_catalogue, self.reference_lookup)

    def create_action(self) -> CreateAction:
        return CreateAction(
            actions=self.action_repository,
            lifecycle=self.action_lifecycle,
            catalogue=self.playbook_catalogue,
            reference_lookup=self.reference_lookup,
            clock=self.clock,
        )

    def update_action(self) -> UpdateAction:
        return UpdateAction(
            actions=self.action_repository, lifecycle=self.action_lifecycle, clock=self.clock
        )

    def get_action(self) -> GetAction:
        return GetAction(actions=self.action_repository)

    def list_actions(self) -> ListActions:
        return ListActions(
            actions=self.action_repository,
            lifecycle=self.action_lifecycle,
            catalogue=self.playbook_catalogue,
            clock=self.clock,
        )

    def seed_actions(self) -> SeedActions:
        """Phase 4's seeding CLI. Reuses `create_action()` unmodified — a
        seeded card is created exactly as a human raising one from a
        playbook link would be, just looped over every signal type raised
        anywhere in the corpus."""
        return SeedActions(
            reader=self.insights_reader(),
            actions=self.action_repository,
            create_action=self.create_action(),
            catalogue=self.playbook_catalogue,
        )

    def get_health(self) -> GetHealth:
        return GetHealth(probes=self.health_probes, clock=self.clock)

    def import_reference_data(self) -> ImportReferenceData:
        return ImportReferenceData(
            source=self.reference_source, repository=self.reference_repository
        )

    def import_answer_key(self) -> ImportAnswerKey:
        return ImportAnswerKey(
            source=self.ground_truth_source,
            repository=self.ground_truth_repository,
            pdf_source=self.answer_key_source,
        )

    def evaluate_extraction(self) -> EvaluateExtraction:
        """Phase 5's harness. Holds both sides — the answers and the
        pipeline's output — which is why it and everything under it are
        forbidden to extraction by the import-linter contract, not merely
        kept apart by convention.
        """
        return EvaluateExtraction(
            ground_truth=self.ground_truth_repository,
            extractions=self.call_extraction_repository,
            diagnostics=self.diagnostics_source,
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

    def classify_call_l2(self) -> ClassifyCallL2:
        return ClassifyCallL2(
            calls=self.call_repository,
            reference_lookup=self.reference_lookup,
            prompts=self.prompt_source,
            stage_cache=self.stage_cache,
            extractions=self.call_extraction_repository,
            clock=self.clock,
        )

    def classify_call_l3(self) -> ClassifyCallL3:
        return ClassifyCallL3(
            calls=self.call_repository,
            reference_lookup=self.reference_lookup,
            prompts=self.prompt_source,
            stage_cache=self.stage_cache,
            extractions=self.call_extraction_repository,
            rubric=self.rubric,
            clock=self.clock,
        )

    def classify_call_l4(self) -> ClassifyCallL4:
        return ClassifyCallL4(
            calls=self.call_repository,
            reference_lookup=self.reference_lookup,
            prompts=self.prompt_source,
            stage_cache=self.stage_cache,
            extractions=self.call_extraction_repository,
            clock=self.clock,
        )

    def run_extraction_pipeline(self) -> ExtractionPipeline:
        return ExtractionPipeline(
            l2=self.classify_call_l2(),
            l3=self.classify_call_l3(),
            l4=self.classify_call_l4(),
            extractions=self.call_extraction_repository,
        )

    def run_extraction_over_corpus(self) -> RunExtractionOverCorpus:
        return RunExtractionOverCorpus(
            calls=self.call_repository,
            runs=self.run_repository,
            pipeline=self.run_extraction_pipeline(),
            provider_registry=self.provider_registry,
            background_runner=self.background_runner,
            clock=self.clock,
        )


def build_container(settings: Settings) -> Container:
    """Wire the object graph for a running application."""
    engine = create_database_engine(settings)
    session_factory = create_session_factory(engine)
    clock = SystemClock()
    audit = LlmAuditLog(include_bodies=settings.log_llm_prompts)
    provider_registry = ProviderRegistry(settings, audit)
    prompt_source = FilePromptSource(PromptLibrary())
    return Container(
        settings=settings,
        engine=engine,
        session_factory=session_factory,
        clock=clock,
        health_probes=(DatabaseHealthProbe(engine),),
        reference_source=XlsxReferenceSource(settings.workbook_path),
        reference_repository=SqlReferenceRepository(session_factory),
        transcript_source=PdfCorpusSource(settings.transcripts_dir),
        reference_lookup=SqlReferenceLookup(session_factory),
        call_repository=SqlCallRepository(session_factory, clock),
        provider_registry=provider_registry,
        provider_probe=RegistryProviderProbe(
            provider_registry, settings.llm_provider, settings.llm_probe_timeout_seconds
        ),
        stage_cache=SqlStageCache(session_factory, clock),
        call_extraction_repository=SqlCallExtractionRepository(session_factory),
        prompt_source=prompt_source,
        rubric=load_rubric(settings.rubric_path),
        run_repository=SqlRunRepository(session_factory),
        background_runner=BackgroundRunner(),
        diagnostics_source=SqlDiagnosticsSource(session_factory),
        ground_truth_source=XlsxGroundTruthSource(settings.workbook_path),
        ground_truth_repository=SqlGroundTruthRepository(session_factory, clock),
        answer_key_source=PdfAnswerKeySource(settings.transcripts_dir),
        insights_source=SqlInsightsSource(session_factory),
        dashboard_config=load_dashboard_config(settings.dashboard_config_path),
        playbook_catalogue=load_playbooks(settings.playbooks_path),
        insight_cache=InMemoryInsightCache(),
        action_lifecycle=load_action_lifecycle(settings.action_lifecycle_path),
        action_repository=SqlActionRepository(session_factory),
    )


async def dispose_container(container: Container) -> None:
    """Release the resources held by the container."""
    await container.engine.dispose()
