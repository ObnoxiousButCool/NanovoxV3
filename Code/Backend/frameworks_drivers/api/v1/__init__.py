"""Version 1 of the HTTP API."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from frameworks_drivers.api.dependencies import require_session
from frameworks_drivers.api.v1 import auth, health, ingest, providers, reference, runs
from frameworks_drivers.api.v1.insights import (
    accounts,
    action_board,
    actions,
    agents,
    calls,
    demand,
    exec_scorecard,
    filters,
    generated,
    hierarchy,
    playbooks,
    risk,
    rules,
)

router = APIRouter()
# `health` is how an orchestrator checks the process is up, before anyone has
# signed in — it carries no session. `auth` is how a session is obtained in
# the first place. Every other router requires one (feature/email-otp-login,
# not on main).
router.include_router(health.router)
router.include_router(auth.router)

_authenticated = [Depends(require_session)]
router.include_router(reference.router, dependencies=_authenticated)
router.include_router(ingest.router, dependencies=_authenticated)
router.include_router(providers.router, dependencies=_authenticated)
router.include_router(runs.router, dependencies=_authenticated)
router.include_router(filters.router, dependencies=_authenticated)
router.include_router(exec_scorecard.router, dependencies=_authenticated)
router.include_router(risk.router, dependencies=_authenticated)
router.include_router(accounts.router, dependencies=_authenticated)
router.include_router(hierarchy.router, dependencies=_authenticated)
router.include_router(calls.router, dependencies=_authenticated)
router.include_router(demand.router, dependencies=_authenticated)
router.include_router(action_board.router, dependencies=_authenticated)
router.include_router(actions.router, dependencies=_authenticated)
router.include_router(playbooks.router, dependencies=_authenticated)
router.include_router(rules.router, dependencies=_authenticated)
router.include_router(agents.router, dependencies=_authenticated)
router.include_router(generated.router, dependencies=_authenticated)

__all__ = ["router"]
