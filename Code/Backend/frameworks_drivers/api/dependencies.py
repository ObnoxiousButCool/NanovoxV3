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


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
GetHealthDep = Annotated[GetHealth, Depends(get_health_use_case)]
ImportReferenceDataDep = Annotated[ImportReferenceData, Depends(get_import_reference_data_use_case)]
IngestTranscriptsDep = Annotated[IngestTranscripts, Depends(get_ingest_transcripts_use_case)]
ListProvidersDep = Annotated[ListProviders, Depends(get_list_providers_use_case)]
