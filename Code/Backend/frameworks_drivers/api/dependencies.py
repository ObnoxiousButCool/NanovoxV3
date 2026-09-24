"""FastAPI dependencies.

The container is attached to application state during startup; these
helpers are the only place that reads it, so route handlers depend on use
cases rather than on the wiring. Grows with each phase as new use cases are
added to the container.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from application.use_cases.get_health import GetHealth
from application.use_cases.import_reference_data import ImportReferenceData
from application.use_cases.ingest_transcripts import IngestTranscripts
from application.use_cases.list_providers import ListProviders
from application.use_cases.read_insights import (
    GetAccountDetail,
    GetAccountRisk,
    GetActions,
    GetAgents,
    GetDemand,
    GetExecScorecard,
    GetHierarchy,
    GetRules,
)
from application.use_cases.run_extraction_over_corpus import RunExtractionOverCorpus
from domain.dashboard_config import DashboardConfig
from frameworks_drivers.container import Container
from infrastructure.config.settings import Settings


def get_container(request: Request) -> Container:
    container = getattr(request.app.state, "container", None)
    if container is None:  # pragma: no cover - only reachable if startup was skipped
        raise RuntimeError("Application container is not initialised.")
    if not isinstance(container, Container):  # pragma: no cover - defensive
        raise TypeError("Application state holds an unexpected container type.")
    return container


ContainerDep = Annotated[Container, Depends(get_container)]


def get_settings_dep(container: ContainerDep) -> Settings:
    return container.settings


def get_health_use_case(container: ContainerDep) -> GetHealth:
    return container.get_health()


def get_import_reference_data_use_case(container: ContainerDep) -> ImportReferenceData:
    return container.import_reference_data()


def get_ingest_transcripts_use_case(container: ContainerDep) -> IngestTranscripts:
    return container.ingest_transcripts()


def get_list_providers_use_case(container: ContainerDep) -> ListProviders:
    return container.list_providers()


def get_run_extraction_over_corpus_use_case(container: ContainerDep) -> RunExtractionOverCorpus:
    return container.run_extraction_over_corpus()


def get_exec_scorecard_use_case(container: ContainerDep) -> GetExecScorecard:
    return container.get_exec_scorecard()


def get_account_risk_use_case(container: ContainerDep) -> GetAccountRisk:
    return container.get_account_risk()


def get_account_detail_use_case(container: ContainerDep) -> GetAccountDetail:
    return container.get_account_detail()


def get_hierarchy_use_case(container: ContainerDep) -> GetHierarchy:
    return container.get_hierarchy()


def get_demand_use_case(container: ContainerDep) -> GetDemand:
    return container.get_demand()


def get_actions_use_case(container: ContainerDep) -> GetActions:
    return container.get_actions()


def get_rules_use_case(container: ContainerDep) -> GetRules:
    return container.get_rules()


def get_agents_use_case(container: ContainerDep) -> GetAgents:
    return container.get_agents()


def get_dashboard_config(container: ContainerDep) -> DashboardConfig:
    """The Metrics sheet's thresholds, for endpoints that label a figure
    with the window or the name its metric was defined with.
    """
    return container.dashboard_config


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
GetHealthDep = Annotated[GetHealth, Depends(get_health_use_case)]
ImportReferenceDataDep = Annotated[ImportReferenceData, Depends(get_import_reference_data_use_case)]
IngestTranscriptsDep = Annotated[IngestTranscripts, Depends(get_ingest_transcripts_use_case)]
ListProvidersDep = Annotated[ListProviders, Depends(get_list_providers_use_case)]
RunExtractionOverCorpusDep = Annotated[
    RunExtractionOverCorpus, Depends(get_run_extraction_over_corpus_use_case)
]
GetExecScorecardDep = Annotated[GetExecScorecard, Depends(get_exec_scorecard_use_case)]
GetAccountRiskDep = Annotated[GetAccountRisk, Depends(get_account_risk_use_case)]
DashboardConfigDep = Annotated[DashboardConfig, Depends(get_dashboard_config)]
GetAccountDetailDep = Annotated[GetAccountDetail, Depends(get_account_detail_use_case)]
GetHierarchyDep = Annotated[GetHierarchy, Depends(get_hierarchy_use_case)]
GetDemandDep = Annotated[GetDemand, Depends(get_demand_use_case)]
GetActionsDep = Annotated[GetActions, Depends(get_actions_use_case)]
GetRulesDep = Annotated[GetRules, Depends(get_rules_use_case)]
GetAgentsDep = Annotated[GetAgents, Depends(get_agents_use_case)]
