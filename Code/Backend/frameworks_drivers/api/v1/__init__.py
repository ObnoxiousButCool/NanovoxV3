"""Version 1 of the HTTP API."""

from __future__ import annotations

from fastapi import APIRouter

from frameworks_drivers.api.v1 import health, ingest, providers, reference, runs
from frameworks_drivers.api.v1.insights import exec_scorecard, risk

router = APIRouter()
router.include_router(health.router)
router.include_router(reference.router)
router.include_router(ingest.router)
router.include_router(providers.router)
router.include_router(runs.router)
router.include_router(exec_scorecard.router)
router.include_router(risk.router)

__all__ = ["router"]
