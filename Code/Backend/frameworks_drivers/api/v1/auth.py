"""Sign-in against the one configured username and password.

Replaces the email-OTP flow this branch started with (leadership, 2026-10-08
— see `Documents/notes/Decisions-and-Questions.md`). A single route, no
session state to request first: `POST /auth/login` either issues a bearer
session or answers 401 with one generic message for a wrong username, a
wrong password, or both.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from frameworks_drivers.api.camel import CamelModel
from frameworks_drivers.api.dependencies import LoginDep

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginBody(CamelModel):
    username: str
    password: str


class LoginResponse(CamelModel):
    token: str
    username: str


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Sign in with the configured username and password",
    responses={status.HTTP_401_UNAUTHORIZED: {"description": "Incorrect username or password."}},
)
async def login(body: LoginBody, use_case: LoginDep) -> LoginResponse:
    token = await use_case.execute(body.username, body.password)
    return LoginResponse(token=token, username=body.username)
