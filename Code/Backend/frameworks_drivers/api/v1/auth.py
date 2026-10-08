"""Email-OTP sign-in.

- `POST /auth/otp/request` — ask for a code. Answers the same way whether or
  not the address is approved, and whether or not a code was actually sent
  (`application.use_cases.auth.RequestOtp`'s whole point) — this is the one
  endpoint in the API that is deliberately uninformative about its own
  outcome, because being informative here is an enumeration oracle.
- `POST /auth/otp/verify` — redeem a code for a bearer session token.

Neither route depends on `SessionDep`: these are how a session is obtained
in the first place. Every other router does.
"""

from __future__ import annotations

from fastapi import APIRouter, status
from pydantic import field_validator

from frameworks_drivers.api.camel import CamelModel
from frameworks_drivers.api.dependencies import RequestOtpDep, VerifyOtpDep

router = APIRouter(prefix="/auth", tags=["auth"])


def _validated_email(value: str) -> str:
    candidate = value.strip()
    if "@" not in candidate or candidate.startswith("@") or candidate.endswith("@"):
        raise ValueError("That does not look like an email address.")
    return candidate


class RequestOtpBody(CamelModel):
    email: str

    @field_validator("email")
    @classmethod
    def _email_is_plausible(cls, value: str) -> str:
        return _validated_email(value)


class RequestOtpResponse(CamelModel):
    message: str = "If that address is approved, a code is on its way."


class VerifyOtpBody(CamelModel):
    email: str
    code: str

    @field_validator("email")
    @classmethod
    def _email_is_plausible(cls, value: str) -> str:
        return _validated_email(value)

    @field_validator("code")
    @classmethod
    def _code_is_six_digits(cls, value: str) -> str:
        candidate = value.strip()
        if not (candidate.isdigit() and len(candidate) == 6):
            raise ValueError("A code is six digits.")
        return candidate


class VerifyOtpResponse(CamelModel):
    token: str
    email: str


@router.post(
    "/otp/request",
    response_model=RequestOtpResponse,
    status_code=status.HTTP_200_OK,
    summary="Request a one-time sign-in code",
)
async def request_otp(body: RequestOtpBody, use_case: RequestOtpDep) -> RequestOtpResponse:
    await use_case.execute(body.email)
    return RequestOtpResponse()


@router.post(
    "/otp/verify",
    response_model=VerifyOtpResponse,
    summary="Redeem a one-time code for a session",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "The code is wrong, used or expired."}
    },
)
async def verify_otp(body: VerifyOtpBody, use_case: VerifyOtpDep) -> VerifyOtpResponse:
    token = await use_case.execute(body.email, body.code)
    return VerifyOtpResponse(token=token, email=body.email.strip().lower())
