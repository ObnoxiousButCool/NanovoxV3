"""Model provider listing (plan §8 Phase 3).

Every registered provider is reported, including an unusable one — hiding
it would leave the caller with no idea why their choice is absent.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import BaseModel

from frameworks_drivers.api.dependencies import ListProvidersDep

router = APIRouter(prefix="/providers", tags=["providers"])


class ProviderResponse(BaseModel):
    name: str
    model: str
    configured: bool
    reachable: bool
    implemented: bool
    is_default: bool
    selectable: bool
    billable: bool
    local: bool
    detail: str | None = None


class ListProvidersResponse(BaseModel):
    default: str
    providers: list[ProviderResponse]


@router.get(
    "",
    response_model=ListProvidersResponse,
    status_code=status.HTTP_200_OK,
    summary="List every configured model provider and whether it is usable now",
)
async def list_providers(use_case: ListProvidersDep) -> ListProvidersResponse:
    descriptions = await use_case.execute()
    return ListProvidersResponse(
        default=use_case.default_name,
        providers=[
            ProviderResponse(
                name=item.name,
                model=item.model,
                configured=item.configured,
                reachable=item.reachable,
                implemented=item.implemented,
                is_default=item.is_default,
                selectable=item.selectable,
                billable=item.billable,
                local=item.local,
                detail=item.detail,
            )
            for item in descriptions
        ],
    )
