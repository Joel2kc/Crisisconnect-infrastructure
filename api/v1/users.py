from fastapi import APIRouter, Request, Depends, Query
from services.user_service import (
  login_service,
  forgot_password_service,
  confirm_reset_otp_service,
  reset_password_service,
  rotate_token,
)
from schemas.user import (
    ForgotPasswordDetails,
    ConfirmResetOtpDetails,
    ResetPasswordDetails,
    RefreshTokenDetails,
    LoginDetails,
    UserListResponse,
)
from core.session_dependency import sessionDep
from rate_limiter.rate_limiter import limiter
from typing import Annotated
from core.dependencies import require_role
from enums.user import UserRole
from db.models.user_model import User

user_router = APIRouter(
  prefix="/api/v1/users",
  tags=["Authentication"],
)

AdminUser = Annotated[
  User,
  Depends(require_role(UserRole.crisis_connect_admin))
]

@user_router.post("/login")
async def login(login_details: LoginDetails, session: sessionDep):
  return await login_service(login_details, session)

@user_router.post("/forgot-password")
async def forgot_password(forgot_details: ForgotPasswordDetails, session: sessionDep):
  return await forgot_password_service(forgot_details.email, session)

@user_router.post("/confirm-otp")
@limiter.limit("3/hour")
async def confirm_otp(request: Request, otp_details: ConfirmResetOtpDetails, session: sessionDep):
  return await confirm_reset_otp_service(otp_details.otp, session)

@user_router.post("/reset-password/{reset_token}")
@limiter.limit("3/hour")
async def reset_password(request: Request, reset_token: str, reset_details: ResetPasswordDetails, session: sessionDep):
  return await reset_password_service(reset_token, reset_details.new_password, session)

@user_router.post("/refresh-token")
def refresh_token(refresh_details: RefreshTokenDetails, session: sessionDep):
  return rotate_token(refresh_details.refresh_token, session)
