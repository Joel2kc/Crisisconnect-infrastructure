from typing import Annotated

from fastapi import APIRouter, Depends, Query

from core.dependencies import require_role
from core.session_dependency import sessionDep
from db.models.user_model import User
from enums.user import UserRole
from schemas.emergency import (
    EmergencyCategoryCreate,
    EmergencyCategoryRead,
    EmergencyCategoryUpdate,
    EmergencyCategoryWithContacts,
    EmergencyContactCreate,
    EmergencyContactRead,
    EmergencyContactUpdate,
)
from services.emergency_service import (
    create_category,
    update_category,
    deactivate_category,
    get_categories,
    create_contact,
    update_contact,
    deactivate_contact,
    get_contacts_by_category,
)


emergency_router = APIRouter(
    prefix="/api/v1/emergency",
    tags=["Emergency"],
)

AdminUser = Annotated[User, Depends(require_role(UserRole.crisis_connect_admin))]

@emergency_router.post(
    "/categories",
    response_model=EmergencyCategoryRead,
    status_code=201,
)
def create_emergency_category(
    payload: EmergencyCategoryCreate,
    session: sessionDep,
    admin: AdminUser,
):
    """Crisis Connect Admin only. Create a new emergency category."""
    return create_category(session, payload)


@emergency_router.get(
    "/categories",
    response_model=list[EmergencyCategoryRead],
)
def list_emergency_categories(
    session: sessionDep,
    admin: AdminUser,
):
    """Crisis Connect Admin only. List all categories (including inactive)."""
    return get_categories(session)


@emergency_router.patch(
    "/categories/{category_id}",
    response_model=EmergencyCategoryRead,
)
def update_emergency_category(
    category_id: int,
    payload: EmergencyCategoryUpdate,
    session: sessionDep,
    admin: AdminUser,
):
    """Crisis Connect Admin only. Partially update a category."""
    return update_category(session, category_id, payload)


@emergency_router.patch(
    "/categories/{category_id}/deactivate",
    response_model=EmergencyCategoryRead,
)
def deactivate_emergency_category(
    category_id: int,
    session: sessionDep,
    admin: AdminUser,
):
    """Crisis Connect Admin only. Soft-delete (deactivate) a category."""
    return deactivate_category(session, category_id)


@emergency_router.post(
    "/contacts",
    response_model=EmergencyContactRead,
    status_code=201,
)
def create_emergency_contact(
    payload: EmergencyContactCreate,
    session: sessionDep,
    admin: AdminUser,
):
    """Crisis Connect Admin only. Create a new emergency contact."""
    return create_contact(session, payload)


@emergency_router.patch(
    "/contacts/{contact_id}",
    response_model=EmergencyContactRead,
)
def update_emergency_contact(
    contact_id: int,
    payload: EmergencyContactUpdate,
    session: sessionDep,
    admin: AdminUser,
):
    """Crisis Connect Admin only. Partially update a contact."""
    return update_contact(session, contact_id, payload)


@emergency_router.patch(
    "/contacts/{contact_id}/deactivate",
    response_model=EmergencyContactRead,
)
def deactivate_emergency_contact(
    contact_id: int,
    session: sessionDep,
    admin: AdminUser,
):
    """Crisis Connect Admin only. Soft-delete (deactivate) a contact."""
    return deactivate_contact(session, contact_id)


@emergency_router.get(
    "/contacts",
    response_model=list[EmergencyCategoryWithContacts],
)
def list_emergency_contacts(
    session: sessionDep,
    category_name: str | None = Query(None),
):
    return get_contacts_by_category(session, category_name)
