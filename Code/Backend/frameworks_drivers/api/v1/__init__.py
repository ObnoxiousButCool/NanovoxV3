"""Version 1 of the HTTP API."""

from __future__ import annotations

from fastapi import APIRouter

from frameworks_drivers.api.v1 import health, ingest, providers, reference, runs

router = APIRouter()
router.include_router(health.router)
router.include_router(reference.router)
router.include_router(ingest.router)
router.include_router(providers.router)
router.include_router(runs.router)

__all__ = ["router"]
