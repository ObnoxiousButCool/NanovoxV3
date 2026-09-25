"""Version 1 of the HTTP API."""

from __future__ import annotations

from fastapi import APIRouter

from frameworks_drivers.api.v1 import health, ingest, providers, reference, runs
from frameworks_drivers.api.v1.insights import (
    accounts,
    actions,
    agents,
    calls,
    demand,
    exec_scorecard,
    filters,
    hierarchy,
    playbooks,
    risk,
    rules,
)

router = APIRouter()
router.include_router(health.router)
router.include_router(reference.router)
router.include_router(ingest.router)
router.include_router(providers.router)
router.include_router(runs.router)
router.include_router(filters.router)
router.include_router(exec_scorecard.router)
router.include_router(risk.router)
router.include_router(accounts.router)
router.include_router(hierarchy.router)
router.include_router(calls.router)
router.include_router(demand.router)
router.include_router(actions.router)
router.include_router(playbooks.router)
router.include_router(rules.router)
router.include_router(agents.router)

__all__ = ["router"]
