"""FastAPI dependencies.

The container is attached to application state during startup; these
helpers are the only place that reads it, so route handlers depend on use
cases rather than on the wiring. Grows with each phase as new use cases are
added to the container.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Request

from application.ports.llm_provider import LLMProvider
from application.ports.session_issuer import Session
from application.use_cases.auth import Login
from application.use_cases.generate_insights import GenerateInsights
from application.use_cases.get_health import GetHealth
from application.use_cases.import_reference_data import ImportReferenceData
from application.use_cases.ingest_transcripts import IngestTranscripts
from application.use_cases.list_calls import ListCalls
from application.use_cases.list_providers import ListProviders
from application.use_cases.manage_actions import (
    ActionContext,
    CreateAction,
    GetAction,
    ListActions,
    UpdateAction,
)
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
)
from application.use_cases.run_extraction_over_corpus import RunExtractionOverCorpus
from domain.dashboard_config import DashboardConfig
from domain.errors import AuthenticationError
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


def get_generate_insights_use_case(container: ContainerDep) -> GenerateInsights:
    return container.generate_insights()


def get_insight_provider(container: ContainerDep) -> LLMProvider | None:
    return container.insight_provider()


def get_list_providers_use_case(container: ContainerDep) -> ListProviders:
    return container.list_providers()


def get_run_extraction_over_corpus_use_case(container: ContainerDep) -> RunExtractionOverCorpus:
    return container.run_extraction_over_corpus()


def get_filter_options_use_case(container: ContainerDep) -> GetFilterOptions:
    return container.get_filter_options()


def get_exec_scorecard_use_case(container: ContainerDep) -> GetExecScorecard:
    return container.get_exec_scorecard()


def get_account_risk_use_case(container: ContainerDep) -> GetAccountRisk:
    return container.get_account_risk()


def get_account_detail_use_case(container: ContainerDep) -> GetAccountDetail:
    return container.get_account_detail()


def get_hierarchy_use_case(container: ContainerDep) -> GetHierarchy:
    return container.get_hierarchy()


def get_list_calls_use_case(container: ContainerDep) -> ListCalls:
    return container.list_calls()


def get_read_call_evidence_use_case(container: ContainerDep) -> ReadCallEvidence:
    return container.read_call_evidence()


def get_demand_use_case(container: ContainerDep) -> GetDemand:
    return container.get_demand()


def get_actions_use_case(container: ContainerDep) -> GetActions:
    return container.get_actions()


def get_list_playbooks_use_case(container: ContainerDep) -> ListPlaybooks:
    return container.list_playbooks()


def get_playbook_use_case(container: ContainerDep) -> GetPlaybook:
    return container.get_playbook()


def get_create_action_use_case(container: ContainerDep) -> CreateAction:
    return container.create_action()


def get_update_action_use_case(container: ContainerDep) -> UpdateAction:
    return container.update_action()


def get_action_use_case(container: ContainerDep) -> GetAction:
    return container.get_action()


def get_list_actions_use_case(container: ContainerDep) -> ListActions:
    return container.list_actions()


def get_action_context(container: ContainerDep) -> ActionContext:
    return ActionContext(lifecycle=container.action_lifecycle, today=container.clock.now().date())


def get_rules_use_case(container: ContainerDep) -> GetRules:
    return container.get_rules()


def get_agents_use_case(container: ContainerDep) -> GetAgents:
    return container.get_agents()


def get_dashboard_config(container: ContainerDep) -> DashboardConfig:
    """The Metrics sheet's thresholds, for endpoints that label a figure
    with the window or the name its metric was defined with.
    """
    return container.dashboard_config


def get_login_use_case(container: ContainerDep) -> Login:
    return container.login()


_BEARER_PREFIX = "Bearer "


def require_session(
    container: ContainerDep, authorization: Annotated[str | None, Header()] = None
) -> Session:
    """Every router but `auth` and `health` depends on this.

    Raised as `AuthenticationError`, not a bare 401: the same RFC 9457 body
    every other rejection gets, rather than a special case in the delivery
    layer (`frameworks_drivers/api/errors.py` is the one place that maps it
    to a status code).
    """
    if authorization is None or not authorization.startswith(_BEARER_PREFIX):
        raise AuthenticationError("Sign in to continue.")
    token = authorization.removeprefix(_BEARER_PREFIX)
    return container.session_issuer.verify(token)


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
GetHealthDep = Annotated[GetHealth, Depends(get_health_use_case)]
ImportReferenceDataDep = Annotated[ImportReferenceData, Depends(get_import_reference_data_use_case)]
IngestTranscriptsDep = Annotated[IngestTranscripts, Depends(get_ingest_transcripts_use_case)]
ListProvidersDep = Annotated[ListProviders, Depends(get_list_providers_use_case)]
GenerateInsightsDep = Annotated[GenerateInsights, Depends(get_generate_insights_use_case)]
InsightProviderDep = Annotated[LLMProvider | None, Depends(get_insight_provider)]
RunExtractionOverCorpusDep = Annotated[
    RunExtractionOverCorpus, Depends(get_run_extraction_over_corpus_use_case)
]
GetExecScorecardDep = Annotated[GetExecScorecard, Depends(get_exec_scorecard_use_case)]
GetFilterOptionsDep = Annotated[GetFilterOptions, Depends(get_filter_options_use_case)]
GetAccountRiskDep = Annotated[GetAccountRisk, Depends(get_account_risk_use_case)]
DashboardConfigDep = Annotated[DashboardConfig, Depends(get_dashboard_config)]
GetAccountDetailDep = Annotated[GetAccountDetail, Depends(get_account_detail_use_case)]
GetHierarchyDep = Annotated[GetHierarchy, Depends(get_hierarchy_use_case)]
ListCallsDep = Annotated[ListCalls, Depends(get_list_calls_use_case)]
ReadCallEvidenceDep = Annotated[ReadCallEvidence, Depends(get_read_call_evidence_use_case)]
GetDemandDep = Annotated[GetDemand, Depends(get_demand_use_case)]
GetActionsDep = Annotated[GetActions, Depends(get_actions_use_case)]
ListPlaybooksDep = Annotated[ListPlaybooks, Depends(get_list_playbooks_use_case)]
GetPlaybookDep = Annotated[GetPlaybook, Depends(get_playbook_use_case)]
CreateActionDep = Annotated[CreateAction, Depends(get_create_action_use_case)]
UpdateActionDep = Annotated[UpdateAction, Depends(get_update_action_use_case)]
GetActionDep = Annotated[GetAction, Depends(get_action_use_case)]
ListActionsDep = Annotated[ListActions, Depends(get_list_actions_use_case)]
ActionContextDep = Annotated[ActionContext, Depends(get_action_context)]
GetRulesDep = Annotated[GetRules, Depends(get_rules_use_case)]
GetAgentsDep = Annotated[GetAgents, Depends(get_agents_use_case)]
LoginDep = Annotated[Login, Depends(get_login_use_case)]
SessionDep = Annotated[Session, Depends(require_session)]
