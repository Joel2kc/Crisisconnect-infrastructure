from fastapi import APIRouter, BackgroundTasks, Request, Depends, Query
from services.admin_service import (
    get_users,
    get_agencies,
    awaiting_verification,
    verified_accounts,
    get_account_by_id,
    verify_agency,
    reject_agency,
    verify_volunteer,
    suspend_volunteer,
)
from enums.user import UserRole
from typing import Annotated
from db.models.user_model import User
from schemas.user import UserListResponse
from schemas.user import UserRead
from schemas.admin import VerificationAccountsResponse
from core.session_dependency import sessionDep
from core.dependencies import require_role
from sqlmodel import select
from schemas.agency import (
    AgencyListResponse,
    AgencyRead,
    AgencyRejectRequest,
    AgencyType,
    AgencyVerificationStatus
)
from schemas.volunteer import VolunteerProfileRead
from services.agency_email_service import (
    send_agency_verified_email,
    send_agency_rejected_email,
)
from services.volunteer_email_service import (
    send_volunteer_verified_email,
    send_volunteer_suspended_email,
)

admin_router = APIRouter(
  prefix="/api/v1/admin",
  tags=["Admin"],
)

AdminUser = Annotated[
  User,
  Depends(require_role(UserRole.crisis_connect_admin))
]

@admin_router.get(
    "/accounts/awaiting-verification",
    response_model=VerificationAccountsResponse,
)
def list_accounts_awaiting_verification(
    session: sessionDep,
    admin: AdminUser,
):
    return awaiting_verification(session, admin)


@admin_router.get(
    "/accounts/verified",
    response_model=VerificationAccountsResponse,
)
def list_verified_accounts(
    session: sessionDep,
    admin: AdminUser,
):
    return verified_accounts(session, admin)


@admin_router.get("/accounts/{user_id}", response_model=UserRead)
def get_admin_account(
    user_id: int,
    session: sessionDep,
    admin: AdminUser,
):
    return get_account_by_id(session, user_id, admin)

@admin_router.get("/users", response_model=UserListResponse)
def list_users(
    session: sessionDep,
    admin: AdminUser,

    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),

    role: UserRole | None = Query(None),
    is_active: bool | None = Query(None),
    agency_id: int | None = Query(None, ge=1),
):
    return get_users(
        session=session,
        page=page,
        page_size=page_size,
        role=role,
        is_active=is_active,
        agency_id=agency_id,
    )
    
@admin_router.get("/agencies", response_model=AgencyListResponse)
def list_agencies(
    session: sessionDep,
    admin: AdminUser,

    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),

    verification_status: AgencyVerificationStatus | None = Query(None),
    agency_type: AgencyType | None = Query(None),
    region: str | None = Query(None),
):
    return get_agencies(
        session=session,
        page=page,
        page_size=page_size,
        verification_status=verification_status,
        agency_type=agency_type,
        region=region,
    )


@admin_router.post("/agencies/{agency_id}/verify", response_model=AgencyRead)
def verify_agency_application(
    agency_id: int,
    session: sessionDep,
    background_tasks: BackgroundTasks,
    admin: AdminUser,
):
    agency = verify_agency(session, agency_id, admin)
    agency_admin_user = session.exec(
        select(User).where(
            User.agency_id == agency.id,
            User.role == UserRole.agency_admin,
        )
    ).first()
    if agency_admin_user:
        background_tasks.add_task(
            send_agency_verified_email, agency_admin_user.email, agency.name
        )
    return agency


@admin_router.post("/agencies/{agency_id}/reject", response_model=AgencyRead)
def reject_agency_application(
    agency_id: int,
    payload: AgencyRejectRequest,
    session: sessionDep,
    background_tasks: BackgroundTasks,
    admin: AdminUser,
):
    agency = reject_agency(session, agency_id, payload.reason, admin)
    agency_admin_user = session.exec(
        select(User).where(
            User.agency_id == agency.id,
            User.role == UserRole.agency_admin,
        )
    ).first()
    if agency_admin_user:
        background_tasks.add_task(
            send_agency_rejected_email,
            agency_admin_user.email,
            agency.name,
            payload.reason,
        )
    return agency


@admin_router.post(
    "/volunteers/{volunteer_id}/verify",
    response_model=VolunteerProfileRead,
)
def verify_volunteer_application(
    volunteer_id: int,
    session: sessionDep,
    background_tasks: BackgroundTasks,
    admin: AdminUser,
):
    profile = verify_volunteer(session, volunteer_id, admin)
    volunteer_user = session.get(User, profile.user_id)
    if volunteer_user:
        background_tasks.add_task(
            send_volunteer_verified_email,
            volunteer_user.email,
            volunteer_user.full_name,
        )
    return profile


@admin_router.post(
    "/volunteers/{volunteer_id}/suspend",
    response_model=VolunteerProfileRead,
)
def suspend_volunteer_application(
    volunteer_id: int,
    session: sessionDep,
    background_tasks: BackgroundTasks,
    admin: AdminUser,
):
    profile = suspend_volunteer(session, volunteer_id, admin)
    volunteer_user = session.get(User, profile.user_id)
    if volunteer_user:
        background_tasks.add_task(
            send_volunteer_suspended_email,
            volunteer_user.email,
            volunteer_user.full_name,
        )
    return profile
