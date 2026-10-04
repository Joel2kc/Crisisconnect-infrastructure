from typing import Annotated

from fastapi import APIRouter, Depends, Query

from core.dependencies import require_role
from core.session_dependency import sessionDep
from db.models.user_model import User
from enums.responder import ResponderAssignmentFilter
from enums.user import UserRole
from schemas.responder_dashboard import (
    ResponderAssignmentDetails,
    ResponderAssignmentsResponse,
    ResponderDashboardResponse,
)
from services.responder_dashboard_service import (
    get_my_assignment_details,
    get_responder_dashboard,
    list_my_assignments,
)

responder_router = APIRouter(
    prefix="/api/v1/responders",
    tags=["Responders"],
)


ResponderUser = Annotated[
    User,
    Depends(require_role(UserRole.responder)),
]


@responder_router.get(
    "/me/dashboard",
    response_model=ResponderDashboardResponse,
)
def responder_dashboard(
    session: sessionDep,
    current_user: ResponderUser,
):
    return get_responder_dashboard(
        session=session,
        current_user=current_user,
    )


@responder_router.get(
    "/me/assignments",
    response_model=ResponderAssignmentsResponse,
)
def my_assignments(
    session: sessionDep,
    current_user: ResponderUser,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    status_filter: ResponderAssignmentFilter | None = Query(None),
):
    return list_my_assignments(
        session=session,
        current_user=current_user,
        page=page,
        limit=limit,
        status_filter=status_filter,
    )


@responder_router.get(
    "/me/assignments/{assignment_id}",
    response_model=ResponderAssignmentDetails,
)
def my_assignment_details(
    assignment_id: int,
    session: sessionDep,
    current_user: ResponderUser,
):
    return get_my_assignment_details(
        session=session,
        current_user=current_user,
        assignment_id=assignment_id,
    )
